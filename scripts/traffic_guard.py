#!/usr/bin/env python3
"""
Monthly traffic guard:
Counts host traffic with vnStat and slows the host down as the monthly allowance runs out.
It never stops a service, so SSH and proxies stay reachable. A timer runs it every 10 minutes,
which also restores the limit after a reboot and clears it when a new month starts.
"""
from typing import Dict

CONFIG = "/etc/vps-lxc/traffic-guard.conf"
SCRIPT = "/usr/local/sbin/vps-lxc-traffic-guard"
STATUS = "/var/lib/vps-lxc/traffic-status"
SERVICE = "/etc/systemd/system/vps-lxc-traffic-guard.service"
TIMER = "/etc/systemd/system/vps-lxc-traffic-guard.timer"

GUARD_SCRIPT = r"""#!/bin/bash
# Installed by vps-lxc-skill. Runs every 10 minutes through vps-lxc-traffic-guard.timer.
export PATH="$PATH:/usr/sbin:/sbin"
CONFIG=/etc/vps-lxc/traffic-guard.conf
STATUS=/var/lib/vps-lxc/traffic-status
. "$CONFIG"

used_bytes() {
    vnstat -i "$IFACE" --json m 2>/dev/null | python3 -c '
import json, sys, time
data = json.load(sys.stdin)
now = time.localtime()
months = data["interfaces"][0]["traffic"].get("month") or data["interfaces"][0]["traffic"].get("months") or []
scale = 1 if int(str(data.get("jsonversion", "2"))) >= 2 else 1024
for m in months:
    if m["date"]["year"] == now.tm_year and m["date"]["month"] == now.tm_mon:
        print((m["rx"] + m["tx"]) * scale)
        break
else:
    print(0)
'
}

apply_rate() {
    local mbit=$1 current
    current=$(tc qdisc show dev "$IFACE" | head -n1)
    if [ "$mbit" = 0 ]; then
        case "$current" in *tbf*) tc qdisc replace dev "$IFACE" root fq ;; esac
    else
        case "$current" in
            *"rate ${mbit}Mbit"*) ;;
            *) tc qdisc replace dev "$IFACE" root tbf rate "${mbit}mbit" burst 256kbit latency 400ms ;;
        esac
    fi
}

bytes=$(used_bytes)
case "$bytes" in ''|*[!0-9]*) echo "UNKNOWN $(date -Is) vnstat gave no data" > "$STATUS"; exit 0 ;; esac
limit=$((LIMIT_GB * 1000000000))
percent=$((bytes * 100 / limit))
if [ "$percent" -ge "$STOP_PCT" ]; then
    state=SLOW2; rate=$STOP_MBIT
elif [ "$percent" -ge "$SLOW_PCT" ]; then
    state=SLOW1; rate=$SLOW_MBIT
elif [ "$percent" -ge "$WARN_PCT" ]; then
    state=WARN; rate=0
else
    state=OK; rate=0
fi
apply_rate "$rate"
previous=$(cut -d' ' -f1 "$STATUS" 2>/dev/null)
disk=$(df --output=pcent / 2>/dev/null | tail -n1 | tr -dc 0-9)
echo "$state $(date -Is) used=$((bytes / 1000000000))GB limit=${LIMIT_GB}GB percent=$percent rate_mbit=$rate disk=${disk:-0}%" > "$STATUS"
[ "${disk:-0}" -lt "${DISK_WARN_PCT:-85}" ] || logger -t vps-lxc-traffic "disk is ${disk}% full"
[ "$state" = "$previous" ] || logger -t vps-lxc-traffic "traffic state $previous -> $state ($percent%)"
"""

UNIT = """[Unit]
Description=vps-lxc monthly traffic guard
After=network-online.target vnstat.service

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/vps-lxc-traffic-guard
"""

TIMER_UNIT = """[Unit]
Description=Run the vps-lxc traffic guard every 10 minutes

[Timer]
OnBootSec=2min
OnUnitActiveSec=10min

[Install]
WantedBy=timers.target
"""


def render_config(iface: str, limit_gb: int, warn: int = 80, slow: int = 90, stop: int = 98,
                  slow_mbit: int = 50, stop_mbit: int = 5) -> str:
    if not iface.replace("-", "").replace(".", "").replace("_", "").isalnum():
        raise ValueError(f"unsafe interface name: {iface}")
    if limit_gb < 1 or not 0 < warn < slow < stop <= 100:
        raise ValueError("traffic limit must be positive, with warn < slow < stop <= 100")
    values: Dict[str, object] = {"IFACE": iface, "LIMIT_GB": limit_gb, "WARN_PCT": warn, "SLOW_PCT": slow,
                                 "STOP_PCT": stop, "SLOW_MBIT": slow_mbit, "STOP_MBIT": stop_mbit}
    return "".join(f"{k}={v}\n" for k, v in values.items())


def install_script(iface: str, limit_gb: int, reset_day: int = 1) -> str:
    if not 1 <= reset_day <= 28:
        raise ValueError("reset day must be between 1 and 28")
    return f"""set -e
export DEBIAN_FRONTEND=noninteractive
command -v vnstat >/dev/null 2>&1 || {{ apt-get update -y >/dev/null </dev/null; apt-get install -y vnstat >/dev/null </dev/null; }}
sed -i -E 's/^;?MonthRotate .*/MonthRotate {reset_day}/' /etc/vnstat.conf
systemctl enable --now vnstat >/dev/null 2>&1
systemctl restart vnstat
vnstat --add -i {iface} >/dev/null 2>&1 || true
mkdir -p /etc/vps-lxc /var/lib/vps-lxc
cat > {CONFIG} <<'VPS_LXC_EOF'
{render_config(iface, limit_gb)}VPS_LXC_EOF
cat > {SCRIPT} <<'VPS_LXC_EOF'
{GUARD_SCRIPT}VPS_LXC_EOF
chmod 755 {SCRIPT}
cat > {SERVICE} <<'VPS_LXC_EOF'
{UNIT}VPS_LXC_EOF
cat > {TIMER} <<'VPS_LXC_EOF'
{TIMER_UNIT}VPS_LXC_EOF
systemctl daemon-reload
systemctl enable --now vps-lxc-traffic-guard.timer >/dev/null 2>&1
echo TRAFFIC_GUARD=installed
"""
