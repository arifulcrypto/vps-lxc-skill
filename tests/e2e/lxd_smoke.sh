#!/usr/bin/env bash
# Real LXD test: runs the tool twice on one host, then proves TCP and UDP forwarding.
# Needs root and an initialized LXD. Never prints result.json, which holds passwords.
set -euo pipefail
OUT="${1:?usage: lxd_smoke.sh <output-dir>}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HOST_IP="$(ip -4 route get 1.1.1.1 | sed -n 's/.* src \([0-9.]*\).*/\1/p')"
run() { python3 "$ROOT/scripts/vps_lxc.py" --local --count 2 --memory 512 --disk 5 --output-dir "$OUT" ${LXC_IMAGE:+--image "$LXC_IMAGE"} "$@"; }
field() { python3 - "$OUT/result.json" "$1" <<'PY'
import json, sys
print(eval(sys.argv[2], {"r": json.load(open(sys.argv[1]))}))
PY
}

echo "::group::First run"; time run; echo "::endgroup::"
test "$(field 'r["status"]')" = success
test "$(field 'sorted({p["forward"] for c in r["containers"] for p in c["ports"]})')" = "['nat']"
test "$(field '[c["ipv4"].rsplit(".",1)[1] for c in r["containers"]]')" = "['10', '20']"
test "$(field 'all(c["is_3xui_ready"] for c in r["containers"])')" = True
PASS1="$(field '[c["password"] for c in r["containers"]]')"
DEV1="$(lxc query /1.0/instances/vps-01 | python3 -c 'import json,sys; print(sorted(json.load(sys.stdin)["devices"].items()))')"

echo "::group::Second run"; time run; echo "::endgroup::"
test "$(field '[c["password"] for c in r["containers"]]')" = "$PASS1"
DEV2="$(lxc query /1.0/instances/vps-01 | python3 -c 'import json,sys; print(sorted(json.load(sys.stdin)["devices"].items()))')"
test "$DEV1" = "$DEV2"

echo "TCP forward"
lxc exec vps-02 -- sh -c 'nohup python3 -m http.server 20160 >/dev/null 2>&1 &'
for _ in 1 2 3 4 5 6 7 8 9 10; do curl -fsS -o /dev/null --max-time 3 "http://$HOST_IP:20160/" && break; sleep 1; done
curl -fsS -o /dev/null --max-time 5 "http://$HOST_IP:20160/"

echo "UDP forward"
lxc file push "$ROOT/tests/e2e/udp_echo.py" vps-02/root/udp_echo.py
lxc exec vps-02 -- sh -c 'nohup python3 /root/udp_echo.py 42973 >/dev/null 2>&1 &'
sleep 1
python3 "$ROOT/tests/e2e/udp_echo.py" "$HOST_IP" 42973

echo "Container egress and client address"
lxc exec vps-02 -- curl -fsS -o /dev/null --max-time 15 https://www.gstatic.com/generate_204

echo "A busy planned port fails before any change"
python3 -m http.server 10019 --bind 0.0.0.0 >/dev/null 2>&1 &
BUSY=$!
sleep 1
if run --output-dir "$OUT-busy" >"$OUT-busy.log" 2>&1; then echo "expected failure"; exit 1; fi
grep -q '10019/tcp' "$OUT-busy.log"
kill "$BUSY"
echo "All LXD checks passed"
