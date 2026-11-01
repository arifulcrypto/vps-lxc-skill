#!/usr/bin/env python3
"""
Boot self-check for the host:
A systemd timer runs one static script after every boot. It waits for LXD, then starts
the listed containers and services, reapplies per-container BBR, tests each SSH forward,
and retries. The result goes to a status file, so nobody has to troubleshoot a reboot by hand.
Only what is listed in the config is touched: a container the operator created
separately, or one stopped on purpose before this was installed, is not listed.
"""
import re
import shlex
from typing import Any, Dict, List, Sequence

CONFIG = "/etc/vps-lxc/boot-check.conf"
SCRIPT = "/usr/local/sbin/vps-lxc-bootcheck"
STATUS = "/var/lib/vps-lxc/boot-status"
LOG = "/var/log/vps-lxc-bootcheck.log"
SERVICE = "/etc/systemd/system/vps-lxc-bootcheck.service"
TIMER = "/etc/systemd/system/vps-lxc-bootcheck.timer"
WATCHED_UNITS = ("x-ui", "nginx", "realm", "xrdp", "ssh", "sshd", "docker")
UNIT_RE = re.compile(r"^[A-Za-z0-9_.@-]{1,64}$")

CHECK_SCRIPT = r"""#!/bin/bash
# Installed by vps-lxc-skill. Runs after every boot through vps-lxc-bootcheck.timer.
export PATH="$PATH:/snap/bin:/usr/sbin:/sbin"
CONFIG=/etc/vps-lxc/boot-check.conf
STATUS=/var/lib/vps-lxc/boot-status
ATTEMPTS="${BOOTCHECK_ATTEMPTS:-16}"
WAIT="${BOOTCHECK_WAIT:-15}"
HEAL_AT=6

log() { echo "$(date -Is) $*" | tee -a /var/log/vps-lxc-bootcheck.log; }
report() { mkdir -p "$(dirname "$STATUS")"; echo "$1 $(date -Is) $2" > "$STATUS.tmp" && mv -f "$STATUS.tmp" "$STATUS"; }

in_container() { local c=$1; shift; lxc exec "$c" -- "$@" </dev/null; }

check_host_unit() {
    systemctl is-active --quiet "$1" && return 0
    log "host: starting $1"
    systemctl restart "$1" >/dev/null 2>&1
    systemctl is-active --quiet "$1" || problems+=("host unit $1")
}

check_container() {
    local name=$1 ip=$2 ssh_port=$3; shift 3
    if ! lxc query "/1.0/instances/$name/state" </dev/null | grep -q '"status": "Running"'; then
        log "$name: starting"
        lxc start "$name" </dev/null >/dev/null 2>&1
        problems+=("$name starting")
        return
    fi
    local state; state=$(in_container "$name" systemctl is-system-running 2>/dev/null)
    case "$state" in
        running|degraded) ;;
        *) problems+=("$name booting"); return ;;
    esac
    # Each container keeps its own value, so BBR on the host alone does not reach it.
    if grep -qw bbr /proc/sys/net/ipv4/tcp_available_congestion_control 2>/dev/null; then
        [ "$(in_container "$name" sysctl -n net.ipv4.tcp_congestion_control 2>/dev/null)" = bbr ] ||
            in_container "$name" sysctl -q -w net.ipv4.tcp_congestion_control=bbr >/dev/null 2>&1
    fi
    local unit
    for unit in "$@"; do
        in_container "$name" systemctl is-active --quiet "$unit" && continue
        # A socket-activated SSH server is healthy while its service is idle.
        in_container "$name" systemctl is-active --quiet "$unit.socket" && continue
        log "$name: starting $unit"
        in_container "$name" systemctl restart "$unit" >/dev/null 2>&1
        in_container "$name" systemctl is-active --quiet "$unit" || problems+=("$name unit $unit")
    done
    if [ "$ssh_port" != 0 ] && ! timeout 4 bash -c "exec 3<>/dev/tcp/$ip/$ssh_port" 2>/dev/null; then
        problems+=("$name forward $ssh_port")
        if [ "$attempt" = "$HEAL_AT" ]; then
            log "$name: forward $ssh_port is down, restarting the container"
            lxc restart "$name" </dev/null >/dev/null 2>&1
        fi
    fi
}

run_checks() {
    problems=()
    while read -r kind first second third rest; do
        case "$kind" in
            host) check_host_unit "$first" ;;
            container) check_container "$first" "$second" "$third" $rest ;;
        esac
    done < "$CONFIG"
}

[ -f "$CONFIG" ] || { report FAILED "missing $CONFIG"; exit 1; }
sysctl --system >/dev/null 2>&1
if ! lxd waitready --timeout=180 </dev/null; then
    report FAILED "LXD did not start"
    log "FAILED: LXD did not start"
    exit 1
fi

for attempt in $(seq 1 "$ATTEMPTS"); do
    run_checks
    if [ ${#problems[@]} -eq 0 ]; then
        report OK "attempt $attempt"
        log "OK after attempt $attempt"
        exit 0
    fi
    log "attempt $attempt: ${problems[*]}"
    sleep "$WAIT"
done
report FAILED "${problems[*]}"
log "FAILED: ${problems[*]}"
exit 1
"""

UNIT = """[Unit]
Description=vps-lxc boot self-check
After=network-online.target snap.lxd.daemon.unix.socket snap.lxd.activate.service
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/vps-lxc-bootcheck
TimeoutStartSec=600
"""

TIMER_UNIT = """[Unit]
Description=Run the vps-lxc boot self-check after every boot

[Timer]
OnBootSec=30s
AccuracySec=5s

[Install]
WantedBy=timers.target
"""


def render_config(host_units: Sequence[str], containers: Sequence[Dict[str, Any]]) -> str:
    lines = [f"host {unit}" for unit in host_units]
    for c in containers:
        lines.append(" ".join(["container", c["name"], c["ip"], str(c["ssh_port"]), *c["units"]]))
    for token in " ".join(lines).split():
        if not re.match(r"^[A-Za-z0-9_.:@-]+$", token):
            raise ValueError(f"unsafe value in boot check config: {token}")
    return "\n".join(lines) + "\n"


def install_script(host_units: Sequence[str], containers: Sequence[Dict[str, Any]]) -> str:
    """Install the check and enable it. Running containers are also set to start with LXD."""
    autostart = "\n".join(f"lxc config set {shlex.quote(c['name'])} boot.autostart true </dev/null"
                          for c in containers)
    return f"""set -e
mkdir -p /etc/vps-lxc /var/lib/vps-lxc
cat > {CONFIG} <<'VPS_LXC_EOF'
{render_config(host_units, containers)}VPS_LXC_EOF
cat > {SCRIPT} <<'VPS_LXC_EOF'
{CHECK_SCRIPT}VPS_LXC_EOF
chmod 755 {SCRIPT}
cat > {SERVICE} <<'VPS_LXC_EOF'
{UNIT}VPS_LXC_EOF
cat > {TIMER} <<'VPS_LXC_EOF'
{TIMER_UNIT}VPS_LXC_EOF
systemctl daemon-reload
systemctl enable vps-lxc-bootcheck.timer >/dev/null 2>&1
{autostart}
echo BOOT_CHECK=installed
"""


def active_units_script(name: str) -> str:
    units = " ".join(WATCHED_UNITS)
    return (f"lxc exec {shlex.quote(name)} -- sh -c 'for u in {units}; do "
            "systemctl is-active --quiet $u && echo $u; done' </dev/null")


def discover_container(inst: Dict[str, Any], host_ip: str) -> Dict[str, Any]:
    """Find a container's SSH forward from its devices, so existing clusters can be adopted."""
    ssh_port = 0
    ip = host_ip
    for name, device in (inst.get("devices") or {}).items():
        if device.get("type") == "proxy" and name.startswith("ssh"):
            ssh_port = int(device["listen"].rsplit(":", 1)[1])
            address = device["listen"].split(":")[1]
            ip = "127.0.0.1" if address == "0.0.0.0" else address
    return {"name": inst["name"], "ip": ip, "ssh_port": ssh_port, "units": []}


def clean_units(names: List[str]) -> List[str]:
    return [u for u in names if UNIT_RE.match(u) and u != "sshd"]
