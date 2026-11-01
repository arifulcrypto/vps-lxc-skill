#!/usr/bin/env python3
"""The boot self-check is real bash: run it with fake lxc, lxd and systemctl on PATH."""
import os
import shlex
import stat
import subprocess

import pytest

from scripts import boot_check
from scripts.boot_check import discover_container, install_script, parse_upstreams, render_config, upstreams_script


FAKE_LXC = r"""#!/bin/bash
S=$STATE_DIR
case "$1" in
query) [ -f "$S/running" ] && echo '{"status": "Running"}' || echo '{"status": "Stopped"}' ;;
start) echo "start" >> "$S/actions"; touch "$S/running" ;;
restart) echo "restart" >> "$S/actions"; touch "$S/forward_ok" ;;
exec)
    shift 3
    if [ "$1" = systemctl ] && [ "$2" = is-system-running ]; then echo running; exit 0; fi
    if [ "$1" = sysctl ] && [ "$2" = -n ]; then cat "$S/cc" 2>/dev/null || echo cubic; exit 0; fi
    if [ "$1" = sysctl ]; then echo bbr > "$S/cc"; echo "set-bbr" >> "$S/actions"; exit 0; fi
    if [ "$1" = systemctl ] && [ "$2" = is-active ]; then [ -f "$S/unit_up" ]; exit; fi
    if [ "$1" = systemctl ] && [ "$2" = restart ]; then echo "restart-unit $3" >> "$S/actions"; touch "$S/unit_up"; exit 0; fi
    ;;
esac
"""
FAKE_SYSTEMCTL = r"""#!/bin/bash
S=$STATE_DIR
case "$1" in
is-active) [ -f "$S/host_up" ] ;;
restart) echo "host-restart $2" >> "$S/actions"; touch "$S/host_up" ;;
esac
"""
FAKE_TIMEOUT = r"""#!/bin/bash
[ -f "$STATE_DIR/forward_ok" ]
"""


@pytest.fixture
def box(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, body in {"lxc": FAKE_LXC, "systemctl": FAKE_SYSTEMCTL, "timeout": FAKE_TIMEOUT,
                       "lxd": "#!/bin/bash\nexit ${LXD_RC:-0}\n", "sysctl": "#!/bin/bash\n"}.items():
        path = bin_dir / name
        path.write_text(body)
        path.chmod(path.stat().st_mode | stat.S_IEXEC)
    script = boot_check.CHECK_SCRIPT.replace("/etc/vps-lxc/boot-check.conf", str(tmp_path / "conf")) \
        .replace("/var/lib/vps-lxc/boot-status", str(tmp_path / "status")) \
        .replace("/var/log/vps-lxc-bootcheck.log", str(tmp_path / "log")) \
        .replace('export PATH="$PATH:/snap/bin:/usr/sbin:/sbin"', f'export PATH="{bin_dir}:$PATH"') \
        .replace("/proc/sys/net/ipv4/tcp_available_congestion_control", str(tmp_path / "avail"))
    (tmp_path / "avail").write_text("cubic bbr\n")
    (tmp_path / "conf").write_text("host x-ui\ncontainer c1 203.0.113.10 2201 x-ui ssh\n")
    (tmp_path / "check.sh").write_text(script)

    def run(env=None, attempts="4"):
        full = dict(os.environ, STATE_DIR=str(tmp_path), BOOTCHECK_ATTEMPTS=attempts, BOOTCHECK_WAIT="0", **(env or {}))
        return subprocess.run(["bash", str(tmp_path / "check.sh")], env=full, capture_output=True, text=True)

    box_obj = type("Box", (), {})()
    box_obj.run, box_obj.path = run, tmp_path
    box_obj.actions = lambda: (tmp_path / "actions").read_text().split("\n") if (tmp_path / "actions").exists() else []
    return box_obj


def ready(box):
    for name in ("running", "host_up", "unit_up", "forward_ok"):
        (box.path / name).touch()
    (box.path / "cc").write_text("bbr\n")


def test_healthy_boot_reports_ok_and_changes_nothing(box):
    ready(box)
    assert box.run().returncode == 0
    assert (box.path / "status").read_text().startswith("OK ")
    assert box.actions() == []


def test_stopped_container_and_service_are_brought_back(box):
    (box.path / "forward_ok").touch()
    assert box.run().returncode == 0
    actions = box.actions()
    assert "start" in actions and "host-restart x-ui" in actions and "restart-unit x-ui" in actions


def test_container_bbr_is_reapplied(box):
    ready(box)
    (box.path / "cc").write_text("cubic\n")
    assert box.run().returncode == 0
    assert "set-bbr" in box.actions()


def test_dead_forward_restarts_the_container_once(box):
    ready(box)
    (box.path / "forward_ok").unlink()
    assert box.run(attempts="8").returncode == 0
    assert box.actions().count("restart") == 1


def test_a_problem_that_stays_is_reported_as_failed(box):
    ready(box)
    (box.path / "forward_ok").unlink()
    result = box.run(attempts="2")
    assert result.returncode == 1
    assert (box.path / "status").read_text().startswith("FAILED ")
    assert "forward 2201" in (box.path / "status").read_text()


def test_lxd_that_never_starts_is_reported(box):
    ready(box)
    assert box.run(env={"LXD_RC": "1"}).returncode == 1
    assert "LXD did not start" in (box.path / "status").read_text()


def test_config_rejects_shell_metacharacters():
    with pytest.raises(ValueError):
        render_config(["x-ui"], [{"name": "c1;reboot", "ip": "203.0.113.10", "ssh_port": 2201, "units": []}])


def test_install_enables_timer_and_autostart():
    script = install_script(["x-ui"], [{"name": "c1", "ip": "203.0.113.10", "ssh_port": 2201, "units": ["x-ui"]}])
    assert "systemctl enable vps-lxc-bootcheck.timer" in script
    assert "lxc config set c1 boot.autostart true" in script
    assert "OnBootSec=30s" in script
    assert subprocess.run(["bash", "-n"], input=script, text=True).returncode == 0


def test_existing_cluster_ssh_forward_is_discovered():
    inst = {"name": "c1-proxy", "devices": {
        "ssh2201": {"type": "proxy", "listen": "tcp:0.0.0.0:2201", "connect": "tcp:127.0.0.1:22"},
        "p8443": {"type": "proxy", "listen": "tcp:203.0.113.10:8443"}}}
    assert discover_container(inst, "203.0.113.10") == {"name": "c1-proxy", "ip": "127.0.0.1", "ssh_port": 2201, "units": []}


def test_upstream_failure_is_noted_without_failing_the_boot(box):
    ready(box)
    with open(box.path / "conf", "a") as f:
        f.write("upstream c3-exit1 198.51.100.7 24446\n")
    (box.path / "bin" / "timeout").write_text('#!/bin/bash\ncase "$*" in *198.51.100.7*) exit 1;; esac\nexit 0\n')
    assert box.run().returncode == 0
    assert "upstream-down=c3-exit1" in (box.path / "status").read_text()


def test_upstreams_are_parsed_safely():
    found = parse_upstreams("c3", "198.51.100.7 24446\nbad;host 1\nnoport\n")
    assert found == [{"name": "c3-exit1", "host": "198.51.100.7", "port": 24446}]


def test_upstream_discovery_code_compiles():
    script = upstreams_script("c3")
    code = shlex.split(script)[6]
    compile(code, "upstreams", "exec")
