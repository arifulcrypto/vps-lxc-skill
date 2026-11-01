#!/usr/bin/env python3
"""The guard is real bash: run it with fake vnstat, tc and logger on PATH."""
import json
import os
import stat
import subprocess
import time

import pytest

from scripts import traffic_guard
from scripts.traffic_guard import install_script, render_config

FAKE_TC = r"""#!/bin/bash
S=$STATE_DIR
if [ "$1" = qdisc ] && [ "$2" = show ]; then cat "$S/qdisc" 2>/dev/null || echo "qdisc fq 0: root"; exit 0; fi
if [ "$1" = qdisc ] && [ "$2" = replace ]; then
    echo "$*" >> "$S/calls"
    case "$*" in
        *rate*) echo "qdisc tbf 8001: root rate $(echo "$*" | sed -E 's/.*rate ([0-9]+)mbit.*/\1/')Mbit" > "$S/qdisc" ;;
        *) echo "qdisc fq 0: root" > "$S/qdisc" ;;
    esac
fi
"""


@pytest.fixture
def box(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, body in {"tc": FAKE_TC, "logger": "#!/bin/bash\necho \"$*\" >> \"$STATE_DIR/log\"\n",
                       "vnstat": '#!/bin/bash\ncat "$STATE_DIR/vnstat.json"\n'}.items():
        path = bin_dir / name
        path.write_text(body)
        path.chmod(path.stat().st_mode | stat.S_IEXEC)
    (tmp_path / "conf").write_text(render_config("eth9", 100))
    script = traffic_guard.GUARD_SCRIPT.replace("/etc/vps-lxc/traffic-guard.conf", str(tmp_path / "conf")) \
        .replace("/var/lib/vps-lxc/traffic-status", str(tmp_path / "status")) \
        .replace('export PATH="$PATH:/usr/sbin:/sbin"', f'export PATH="{bin_dir}:$PATH"')
    (tmp_path / "guard.sh").write_text(script)

    def run(gb, version="2"):
        now = time.localtime()
        month = {"date": {"year": now.tm_year, "month": now.tm_mon}, "rx": int(gb * 5e8), "tx": int(gb * 5e8)}
        (tmp_path / "vnstat.json").write_text(json.dumps(
            {"jsonversion": version, "interfaces": [{"traffic": {"month": [month]}}]}))
        return subprocess.run(["bash", str(tmp_path / "guard.sh")], capture_output=True, text=True,
                              env=dict(os.environ, STATE_DIR=str(tmp_path)))

    obj = type("Box", (), {})()
    obj.run, obj.path = run, tmp_path
    obj.status = lambda: (tmp_path / "status").read_text()
    obj.qdisc = lambda: (tmp_path / "qdisc").read_text() if (tmp_path / "qdisc").exists() else "fq"
    return obj


@pytest.mark.parametrize("gb,state,rate", [(10, "OK", "0"), (80, "WARN", "0"), (90, "SLOW1", "50"), (98, "SLOW2", "5"),
                                           (130, "SLOW2", "5")])
def test_states_follow_the_monthly_allowance(box, gb, state, rate):
    assert box.run(gb).returncode == 0
    assert box.status().startswith(state + " ") and f"rate_mbit={rate}" in box.status()


def test_rate_is_applied_only_at_the_limits(box):
    box.run(10)
    assert "tbf" not in box.qdisc()
    box.run(90)
    assert "rate 50Mbit" in box.qdisc()
    box.run(98)
    assert "rate 5Mbit" in box.qdisc()


def test_new_month_removes_the_limit(box):
    box.run(98)
    box.run(0)
    assert "tbf" not in box.qdisc() and box.status().startswith("OK ")


def test_repeat_runs_do_not_touch_a_matching_limit(box):
    box.run(90)
    box.run(90)
    assert (box.path / "calls").read_text().count("rate") == 1


def test_state_changes_are_logged_once(box):
    box.run(85)
    box.run(85)
    assert (box.path / "log").read_text().count("WARN") == 1


def test_unusable_data_changes_nothing(box):
    box.run(98)
    (box.path / "vnstat.json").write_text("not json")
    subprocess.run(["bash", str(box.path / "guard.sh")], env=dict(os.environ, STATE_DIR=str(box.path)), capture_output=True)
    assert box.status().startswith("UNKNOWN") and "rate 5Mbit" in box.qdisc()


def test_config_validation():
    with pytest.raises(ValueError):
        render_config("eth0;reboot", 100)
    with pytest.raises(ValueError):
        render_config("eth0", 0)
    with pytest.raises(ValueError):
        install_script("eth0", 100, reset_day=31)


def test_install_script_parses_and_enables_the_timer():
    script = install_script("ens3", 1500, reset_day=5)
    assert "LIMIT_GB=1500" in script and "MonthRotate 5" in script and "vps-lxc-traffic-guard.timer" in script
    assert subprocess.run(["bash", "-n"], input=script, text=True).returncode == 0
