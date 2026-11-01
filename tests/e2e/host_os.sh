#!/usr/bin/env bash
# Boots a real KVM VM with the given OS, uses it as an LXD host, and reboots it.
# Measures idle memory and disk at each stage. Needs an initialized LXD with VM support.
set -euo pipefail
IMAGE="${1:?usage: host_os.sh <image>}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VM=hosttest

in_vm() { lxc exec "$VM" -- "$@"; }
wait_vm() {
    for _ in $(seq 1 90); do
        state=$(lxc exec "$VM" -- systemctl is-system-running 2>/dev/null || true)
        case "$state" in running|degraded) return 0 ;; esac
        sleep 3
    done
    echo "VM did not finish booting: $state"; return 1
}
measure() {
    in_vm sync
    in_vm sh -c 'echo 3 > /proc/sys/vm/drop_caches' || true
    echo "MEASURE $1 mem_used_mb=$(in_vm sh -c "free -m | awk '/^Mem:/{print \$3}'") mem_avail_mb=$(in_vm sh -c "free -m | awk '/^Mem:/{print \$7}'") disk_used_mb=$(in_vm sh -c "df -BM --output=used / | tail -1 | tr -dc 0-9") procs=$(in_vm sh -c 'ps -e --no-headers | wc -l')"
}

lxc launch "$IMAGE" "$VM" --vm -c limits.cpu=2 -c limits.memory=4GiB -c security.secureboot=false -d root,size=30GiB
wait_vm
echo "OS $(in_vm sh -c '. /etc/os-release; echo $PRETTY_NAME') kernel $(in_vm uname -r)"
measure fresh-boot

in_vm sh -c 'export DEBIAN_FRONTEND=noninteractive; apt-get update -y >/dev/null && apt-get install -y python3 iproute2 curl >/dev/null'
tar -C "$ROOT" -cf - scripts | lxc exec "$VM" -- sh -c 'mkdir -p /root/tool && tar -C /root/tool -xf -'

echo "::group::Tool on this host"
in_vm python3 /root/tool/scripts/vps_lxc.py --local --check-host --count 2 || true
time in_vm python3 /root/tool/scripts/vps_lxc.py --local --count 2 --memory 512 --disk 5 --output-dir /root/out
echo "::endgroup::"
measure two-containers-idle

echo "Real host reboot"
lxc stop "$VM" --force --timeout 60 || true
in_vm true 2>/dev/null || lxc start "$VM"
sleep 20
wait_vm
for _ in $(seq 1 80); do
    in_vm sh -c 'test -s /var/lib/vps-lxc/boot-status' && break
    sleep 3
done
in_vm cat /var/lib/vps-lxc/boot-status
in_vm grep -q '^OK ' /var/lib/vps-lxc/boot-status
in_vm sh -c 'PATH=$PATH:/snap/bin lxc list -c ns --format csv'
test "$(in_vm sh -c 'PATH=$PATH:/snap/bin lxc list -c s --format csv | grep -c RUNNING')" = 2
# Slim cloud kernels can leave BBR out, and --check-host reports that.
if in_vm grep -qw bbr /proc/sys/net/ipv4/tcp_available_congestion_control; then
    test "$(in_vm sh -c 'PATH=$PATH:/snap/bin lxc exec vps-01 -- sysctl -n net.ipv4.tcp_congestion_control')" = bbr
fi
measure after-reboot
echo "All host checks passed on $IMAGE"
