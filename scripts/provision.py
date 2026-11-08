#!/usr/bin/env python3
"""
Provisioning and container generation logic for VPS LXC Skill.
Validates the complete plan before touching the host, then reconciles LXD state:
every step reads what exists, changes only what differs, and fails on errors.
A run reports success only for mappings and packages it actually observed.
"""
import ipaddress
import json
import re
import secrets
import shlex
import string
from typing import Any, Dict, List, Optional, Sequence, Tuple

from scripts import boot_check, traffic_guard
from scripts.remote import RemoteError, TargetRunner

PASSWORD_CHARS = string.ascii_letters + string.digits + "@#%="
MAX_CONTAINERS = 6
MIN_MEMORY_MB = 512
MIN_DISK_GB = 5
HOST_RESERVED_RAM_MB = 512
HOST_RESERVED_DISK_GB = 3
PROFILE_NAME = "vps-lxc"
DEFAULT_IMAGE = "ubuntu-minimal:24.04"
PASSWORD_KEY = "user.vps-lxc.password"
WEB_BACKEND_PORT = 18443
SUPPORTED_INSTALL_OS = ("ubuntu", "debian")
PACKAGES = "curl socat cron python3 openssl iproute2 tar ca-certificates ufw iptables openssh-server unzip"
BASE_PACKAGES = "openssh-server iproute2 ca-certificates"
RECOMMENDED_OS = {"ubuntu": ("24.04",), "debian": ("13",)}
MIN_KERNEL = (5, 15)
MIN_LXD = (5, 21)
NAME_RE = re.compile(r"^[a-zA-Z](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$")


def generate_secure_password(length: int = 16) -> str:
    """Generates a cryptographically strong, random password distinct from host."""
    specials = "@#%="
    pwd = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        secrets.choice(specials),
    ]
    all_chars = string.ascii_letters + string.digits + specials
    pwd += [secrets.choice(all_chars) for _ in range(length - 4)]
    secrets.SystemRandom().shuffle(pwd)
    return "".join(pwd)


def get_container_port_definitions(container_idx: int, ssh_port: int, is_primary: bool = False,
                                   https_override: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Returns the comprehensive, multi-protocol port forwarding matrix for a container.
    Guarantees every container (c1-c4) has abundant ports for:
    - Independent SSH
    - Cloudflare CDN Web / HTTPS
    - 3X-UI visualization panel
    - VLESS-REALITY-Vision direct
    - Hysteria 2 UDP direct
    - Realm Layer 4 relay to US/NAT home broadband
    - Commercial residential SOCKS5 entry
    - 233boy legacy VMess-WS / Trojan
    - Extra pre-mapped port pool (FastAPI, Redis, Docker)
    """
    ports = [
        {"name": f"ssh{ssh_port}", "ext": ssh_port, "int": 22, "proto": "tcp", "role": "SSH 远程管理"}
    ]

    # Cloudflare CDN Web / HTTPS Port
    if https_override:
        ports.append({"name": f"p{https_override}", "ext": https_override, "int": https_override, "proto": "tcp",
                      "role": f"Cloudflare CDN HTTPS ({https_override})"})
        if container_idx == 4:
            ports.append({"name": "prdp_tcp", "ext": 3389, "int": 3389, "proto": "tcp", "role": "Windows RDP 远程桌面"})
            ports.append({"name": "prdp_udp", "ext": 3389, "int": 3389, "proto": "udp", "role": "Windows RDP UDP 传输加速"})
            ports.append({"name": "pweb8088", "ext": 8088, "int": 8088, "proto": "tcp", "role": "Web 桌面 (noVNC)"})
    elif container_idx == 1:
        ports.append({"name": "p80", "ext": 80, "int": 80, "proto": "tcp", "role": "HTTP Web / ACME 验证"})
        ports.append({"name": "p443", "ext": 443, "int": 443, "proto": "tcp", "role": "HTTPS 标准 CDN 直通建站"})
    elif container_idx == 2:
        ports.append({"name": "p8443", "ext": 8443, "int": 8443, "proto": "tcp", "role": "Cloudflare CDN 官方支持 HTTPS (8443)"})
    elif container_idx == 3:
        ports.append({"name": "p2053", "ext": 2053, "int": 2053, "proto": "tcp", "role": "Cloudflare CDN 官方支持 HTTPS (2053)"})
    elif container_idx == 4:
        ports.append({"name": "p2083", "ext": 2083, "int": 2083, "proto": "tcp", "role": "Cloudflare CDN 官方支持 HTTPS (2083)"})
        ports.append({"name": "prdp_tcp", "ext": 3389, "int": 3389, "proto": "tcp", "role": "Windows RDP 远程桌面"})
        ports.append({"name": "prdp_udp", "ext": 3389, "int": 3389, "proto": "udp", "role": "Windows RDP UDP 传输加速"})
        ports.append({"name": "pweb8088", "ext": 8088, "int": 8088, "proto": "tcp", "role": "Web 桌面 (noVNC)"})
    else:
        cf_p = {5: 2087, 6: 2096}[container_idx]
        ports.append({"name": f"p{cf_p}", "ext": cf_p, "int": cf_p, "proto": "tcp", "role": f"Cloudflare CDN 官方支持 HTTPS ({cf_p})"})

    # 3X-UI Panel Port
    panel_port = 54840 + (container_idx - 1)
    ports.append({"name": f"ppanel_{panel_port}", "ext": panel_port, "int": panel_port, "proto": "tcp", "role": "3X-UI 可视化管理面板"})

    # VLESS REALITY Port
    reality_port = 20159 + (container_idx - 1)
    ports.append({"name": f"preality_{reality_port}", "ext": reality_port, "int": reality_port, "proto": "tcp", "role": "VLESS-REALITY-Vision 直连协议"})

    # Hysteria 2 UDP Port
    hy2_port = 42972 + (container_idx - 1)
    ports.append({"name": f"phy2_{hy2_port}", "ext": hy2_port, "int": hy2_port, "proto": "udp", "role": "Hysteria 2 UDP 极速双直连"})

    # Dedicated Port Pool (100x1 ~ 100x9)
    base = 10000 + container_idx * 10
    pool_roles = {
        1: "Realm Layer 4 家宽/NAT 透传中继 1",
        2: "Realm Layer 4 家宽/NAT 透传中继 2",
        3: "商业住宅代理出口 (SOCKS5/HTTP 入站)",
        4: "233boy VMess-WS 兼容协议",
        5: "3X-UI 内置订阅服务 (Subscription)",
        6: "Trojan-TLS 兼容协议",
        7: "预留扩展端口 (Docker 服务 / API)",
        8: "预留扩展端口 (自定义业务 1)",
        9: "预留扩展端口 (自定义业务 2)",
    }
    for offset in range(1, 10):
        p = base + offset
        ports.append({"name": f"p{p}", "ext": p, "int": p, "proto": "tcp", "role": pool_roles.get(offset, "预留业务端口")})

    return ports


def https_port(container_idx: int) -> int:
    """Public HTTPS port of a container. Host and guest port are identical."""
    return {1: 443, 2: 8443, 3: 2053, 4: 2083, 5: 2087, 6: 2096}[container_idx]


def deployer_config(host_ip: str, idx: int, ssh_port: int, password: Optional[str],
                    https_override: Optional[int] = None) -> Dict[str, Any]:
    """Per-container input that vps-deploy-skill accepts directly (`--from-lxc` or `--config`)."""
    base = 10000 + idx * 10
    cfg: Dict[str, Any] = {
        "ip": host_ip,
        "ssh_port": ssh_port,
        "ssh_user": "root",
        "panel_port": 54840 + idx - 1,
        "reality_port": 20159 + idx - 1,
        "hy2_port": 42972 + idx - 1,
        "https_port": https_override or https_port(idx),
        "web_backend_port": WEB_BACKEND_PORT,
        "sub_port": base + 5,
        "exit_port": base + 3,
        "vmess_port": base + 4,
        "trojan_port": base + 6,
        "cert_mode": "http-01" if idx == 1 and not https_override else "dns-01",
    }
    if password:
        cfg["ssh_pass"] = password
    return cfg


def validate_plan(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Validate every input and the complete port matrix. Pure: no host access."""
    names = cfg.get("names") or ""
    if isinstance(names, str):
        names = [n.strip() for n in names.split(",") if n.strip()]
    count = cfg.get("count")
    if names:
        if count is not None and int(count) != len(names):
            raise RemoteError(f"count={count} disagrees with {len(names)} name(s) in names.")
        count = len(names)
    else:
        count = int(count) if count is not None else 2
        names = [f"vps-{i:02d}" for i in range(1, count + 1)]
    first = int(cfg.get("first_index") or 1)
    if not 1 <= count <= MAX_CONTAINERS:
        raise RemoteError(f"Container count must be between 1 and {MAX_CONTAINERS}, got {count}.")
    if first < 1 or first + count - 1 > MAX_CONTAINERS:
        raise RemoteError(f"first_index {first} with {count} container(s) goes past position {MAX_CONTAINERS}.")
    override = int(cfg["https_port"]) if cfg.get("https_port") else None
    if override and count != 1:
        raise RemoteError("https_port applies to a single container: use it with count 1.")
    for name in names:
        if not NAME_RE.match(name):
            raise RemoteError(f"Invalid container name '{name}': use letters, digits and '-', starting with a letter.")
    if len(set(names)) != len(names):
        raise RemoteError(f"Duplicate container names: {', '.join(names)}")

    for key, minimum in (("cpu", 1), ("memory", MIN_MEMORY_MB), ("disk", MIN_DISK_GB)):
        if int(cfg[key]) < minimum:
            raise RemoteError(f"{key} must be at least {minimum}, got {cfg[key]}.")

    base = int(cfg["ssh_base_port"])
    indices = [first + i for i in range(count)]
    ssh_ports = [base + idx - 1 for idx in indices]
    matrix = [get_container_port_definitions(idx, ssh_ports[i], idx == 1, override) for i, idx in enumerate(indices)]
    seen: Dict[Tuple[int, str], str] = {}
    host_ssh = int(cfg.get("ssh_port") or 22)
    for name, defs in zip(names, matrix):
        for p in defs:
            if not 1 <= p["ext"] <= 65535:
                raise RemoteError(f"Port {p['ext']} for {name} is out of range.")
            key = (p["ext"], p["proto"])
            if key in seen:
                raise RemoteError(f"Port {p['ext']}/{p['proto']} is planned for both {seen[key]} and {name}.")
            seen[key] = name
            if p["ext"] == host_ssh and p["proto"] == "tcp":
                raise RemoteError(f"Port {p['ext']} for {name} collides with the host SSH port.")
    return {"names": names, "count": count, "ssh_ports": ssh_ports, "matrix": matrix, "indices": indices,
            "https_override": override}


def _version(text: str) -> Tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", text)[:2])


def grade_host(facts: Dict[str, str], count: int = 1) -> List[Dict[str, str]]:
    """Compare a host with the recommendations. `fail` stops a run, `warn` is reported and allowed."""
    checks: List[Dict[str, str]] = []

    def add(level: str, item: str, value: str, advice: str = "") -> None:
        checks.append({"level": level, "item": item, "value": value, "advice": advice})

    virt = facts.get("VIRT", "unknown")
    if virt in ("openvz", "lxc", "lxc-libvirt", "docker"):
        add("fail", "Virtualization", virt, "LXD needs its own kernel features. Use a KVM VPS or bare metal.")
    else:
        add("ok", "Virtualization", virt)

    os_id, version = facts.get("OS_ID", ""), facts.get("OS_VERSION", "")
    current = RECOMMENDED_OS.get(os_id)
    if current is None:
        add("warn", "Operating system", f"{os_id} {version}", "Use Debian 13 or Ubuntu 24.04 LTS.")
    elif _version(version) < _version(current[0]):
        add("warn", "Operating system", f"{os_id} {version}", "Out of standard support. Move to Debian 13 or Ubuntu 24.04 LTS.")
    else:
        add("ok", "Operating system", f"{os_id} {version}")

    kernel = facts.get("KERNEL", "")
    add("ok" if _version(kernel) >= MIN_KERNEL else "warn", "Kernel", kernel,
        "" if _version(kernel) >= MIN_KERNEL else "Use 5.15 or newer for current BBR and cgroup behavior.")

    if facts.get("BBR") == "no":
        add("warn", "BBR", "not in this kernel", "Install a full kernel. Slim cloud kernels can leave BBR out.")

    lxd = facts.get("LXD", "")
    if not lxd:
        add("ok", "LXD", "not installed yet", "The tool installs the current LTS through snap.")
    elif _version(lxd) < MIN_LXD:
        add("warn", "LXD", lxd, "Upgrade to 5.21 LTS with `snap refresh lxd --channel=5.21/stable`. This is one-way, "
            "so plan a maintenance window.")
    else:
        add("ok", "LXD", lxd)

    ram = int(facts.get("MEM_MB") or 0)
    needed = HOST_RESERVED_RAM_MB + MIN_MEMORY_MB * count
    add("ok" if ram >= needed else "warn", "Memory", f"{ram} MB",
        "" if ram >= needed else f"{count} container(s) need at least {needed} MB.")
    swap = int(facts.get("SWAP_MB") or 0)
    add("ok" if swap or ram >= 4096 else "warn", "Swap", f"{swap} MB",
        "" if swap or ram >= 4096 else "Add 1-2 GB of swap on small hosts.")
    disk = int(facts.get("DISK_FREE_GB") or 0)
    disk_needed = HOST_RESERVED_DISK_GB + MIN_DISK_GB * count
    add("ok" if disk >= disk_needed else "warn", "Free disk", f"{disk} GB",
        "" if disk >= disk_needed else f"{count} container(s) need at least {disk_needed} GB.")
    return checks


def parse_size_mb(value: str) -> int:
    match = re.match(r"^(\d+)\s*(MB|MiB|GB|GiB)?$", str(value).strip())
    if not match:
        return 0
    factor = {"GB": 1000, "GiB": 1024}.get(match.group(2) or "", 1)
    return int(match.group(1)) * factor


def host_firewall_script(bridge: str, ports: Sequence[str]) -> str:
    """
    Open planned ports and allow the bridge on the host firewall, following the LXD firewall guide.
    Docker sets FORWARD to DROP, so a small unit keeps the bridge forwarded across reboots.
    """
    q = shlex.quote
    b = q(bridge)
    wanted = " ".join(q(p) for p in ports)
    forward = f"""#!/bin/sh
chain=FORWARD
iptables -nL DOCKER-USER >/dev/null 2>&1 && chain=DOCKER-USER
for dir in -i -o; do
    iptables -C "$chain" "$dir" {b} -j ACCEPT 2>/dev/null || iptables -I "$chain" "$dir" {b} -j ACCEPT
done
"""
    unit = """[Unit]
Description=Allow forwarding for the vps-lxc bridge
After=network-online.target docker.service snap.lxd.daemon.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/local/sbin/vps-lxc-forward.sh

[Install]
WantedBy=multi-user.target
"""
    return f"""
fail() {{ echo "host firewall: $*" >&2; exit 40; }}
if command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -q '^Status: active'; then
    ufw allow in on {b} >/dev/null || fail "ufw allow in on {bridge}"
    ufw route allow in on {b} >/dev/null || fail "ufw route allow in on {bridge}"
    ufw route allow out on {b} >/dev/null || fail "ufw route allow out on {bridge}"
    for r in {wanted}; do ufw allow "$r" comment vps-lxc >/dev/null || fail "ufw allow $r"; done
    echo HOST_FIREWALL=ufw
elif command -v firewall-cmd >/dev/null 2>&1 && firewall-cmd --state >/dev/null 2>&1; then
    firewall-cmd --zone=trusted --change-interface={b} --permanent >/dev/null || fail "firewalld bridge zone"
    for r in {wanted}; do firewall-cmd --permanent --add-port="$r" >/dev/null || fail "firewalld add $r"; done
    firewall-cmd --reload >/dev/null || fail "firewalld reload"
    echo HOST_FIREWALL=firewalld
else
    echo HOST_FIREWALL=none
fi
if command -v iptables >/dev/null 2>&1 && iptables -S FORWARD 2>/dev/null | grep -q '^-P FORWARD DROP'; then
    cat > /usr/local/sbin/vps-lxc-forward.sh <<'VPS_LXC_EOF'
{forward}VPS_LXC_EOF
    chmod 755 /usr/local/sbin/vps-lxc-forward.sh
    cat > /etc/systemd/system/vps-lxc-forward.service <<'VPS_LXC_EOF'
{unit}VPS_LXC_EOF
    /usr/local/sbin/vps-lxc-forward.sh || fail "could not allow forwarding for {bridge}"
    systemctl daemon-reload && systemctl enable vps-lxc-forward.service >/dev/null 2>&1
    echo HOST_FORWARD=opened
else
    echo HOST_FORWARD=default
fi
"""


def host_tuning_script() -> str:
    """BBR and UDP buffers are host-level: unprivileged containers cannot set them."""
    return """
modprobe tcp_bbr 2>/dev/null || true
: > /etc/sysctl.d/99-vps-lxc.conf
if grep -qw bbr /proc/sys/net/ipv4/tcp_available_congestion_control 2>/dev/null; then
    echo tcp_bbr > /etc/modules-load.d/vps-lxc.conf
    printf 'net.core.default_qdisc=fq\nnet.ipv4.tcp_congestion_control=bbr\n' >> /etc/sysctl.d/99-vps-lxc.conf
fi
printf 'net.core.rmem_max=16777216\nnet.core.wmem_max=16777216\n' >> /etc/sysctl.d/99-vps-lxc.conf
sysctl -p /etc/sysctl.d/99-vps-lxc.conf >/dev/null 2>&1 || true
echo "HOST_CC=$(sysctl -n net.ipv4.tcp_congestion_control 2>/dev/null || echo unknown)"
echo "HOST_RMEM_MAX=$(sysctl -n net.core.rmem_max 2>/dev/null || echo unknown)"
echo "HOST_WMEM_MAX=$(sysctl -n net.core.wmem_max 2>/dev/null || echo unknown)"
"""


def parse_kv(text: str) -> Dict[str, str]:
    return dict(line.split("=", 1) for line in text.splitlines() if "=" in line)


class LXCProvisioner:
    def __init__(self, runner: TargetRunner, bridge_name: str = "lxdbr0",
                 storage_pool: str = "default", image: str = DEFAULT_IMAGE,
                 storage_driver: str = "dir", enable_ipv6: bool = False):
        self.runner = runner
        self.bridge_name = bridge_name
        self.storage_pool = storage_pool
        self.image = image
        self.storage_driver = storage_driver
        self.subnet: Optional[ipaddress.IPv4Network] = None
        self.warnings: List[str] = []
        self.local_image = image
        self.enable_ipv6 = enable_ipv6

    def query(self, path: str, missing_ok: bool = False) -> Any:
        """Read the LXD API. A failed read raises, so it can never look like an empty result."""
        code, stdout, stderr = self.runner.run(f"lxc query {shlex.quote(path)}", check=False)
        if code != 0:
            message = f"{stdout} {stderr}".lower()
            # LXD 4.0 says "No such object"; 5.x and later say "not found".
            if missing_ok and ("not found" in message or "no such object" in message):
                return None
            raise RemoteError(f"LXD query failed for {path}: {stderr or stdout}")
        try:
            return json.loads(stdout)
        except ValueError as e:
            raise RemoteError(f"LXD returned invalid JSON for {path}") from e

    def install_boot_check(self, containers: Sequence[Dict[str, Any]]) -> None:
        """Enable the self-check for these containers and whichever watched host services are running."""
        entries = []
        upstreams: List[Dict[str, Any]] = []
        for c in containers:
            _, stdout, _ = self.runner.run(boot_check.active_units_script(c["name"]), check=False)
            entries.append(dict(c, units=boot_check.clean_units(stdout.split())))
            _, stdout, _ = self.runner.run(boot_check.upstreams_script(c["name"]), check=False)
            upstreams += boot_check.parse_upstreams(c["name"], stdout)
        units = " ".join(boot_check.WATCHED_UNITS)
        _, stdout, _ = self.runner.run(f"for u in {units}; do systemctl is-active --quiet $u && echo $u; done", check=False)
        self.runner.run(boot_check.install_script(boot_check.clean_units(stdout.split()), entries, upstreams))

    def adopt_running_containers(self, host_ip: str) -> List[Dict[str, Any]]:
        """Containers that are running now, so an existing cluster gets the self-check unchanged."""
        return [boot_check.discover_container(inst, host_ip) for inst in self.query("/1.0/instances?recursion=1")
                if inst.get("status") == "Running"]

    def install_traffic_guard(self, limit_gb: int, reset_day: int = 1) -> str:
        _, iface, _ = self.runner.run("ip -4 route show default | awk '{print $5; exit}'")
        self.runner.run(traffic_guard.install_script(iface.strip(), limit_gb, reset_day), timeout=300)
        return iface.strip()

    def boot_status(self) -> str:
        _, stdout, _ = self.runner.run(f"cat {boot_check.STATUS} 2>/dev/null || true", check=False)
        return stdout.strip()

    def collect_host_facts(self) -> Dict[str, str]:
        script = """
. /etc/os-release
echo "OS_ID=$ID"
echo "OS_VERSION=$VERSION_ID"
echo "KERNEL=$(uname -r)"
echo "VIRT=$(systemd-detect-virt 2>/dev/null || echo none)"
echo "MEM_MB=$(free -m | awk '/^Mem:/{print $2}')"
echo "SWAP_MB=$(free -m | awk '/^Swap:/{print $2}')"
d=/var/snap/lxd/common/lxd; [ -d "$d" ] || d=/var/lib/lxd; [ -d "$d" ] || d=/
echo "DISK_FREE_GB=$(df -BG --output=avail "$d" | tail -n1 | tr -dc 0-9)"
echo "LXD=$(command -v lxd >/dev/null 2>&1 && lxd version 2>/dev/null | head -n1)"
if grep -qw bbr /proc/sys/net/ipv4/tcp_available_congestion_control 2>/dev/null || modprobe -n tcp_bbr 2>/dev/null; then
    echo "BBR=yes"
else
    echo "BBR=no"
fi
"""
        _, stdout, _ = self.runner.run(script, check=False)
        return parse_kv(stdout)

    def detect_host_resources(self) -> Dict[str, int]:
        """Detect CPU cores, total RAM in MB, and free disk in GB where LXD stores data."""
        _, cpu_out, _ = self.runner.run("nproc")
        _, mem_out, _ = self.runner.run("free -m | awk '/^Mem:/{print $2}'")
        _, disk_out, _ = self.runner.run(
            "d=/var/snap/lxd/common/lxd; [ -d \"$d\" ] || d=/var/lib/lxd; [ -d \"$d\" ] || d=/; "
            "df -BG --output=avail \"$d\" | tail -n1 | tr -dc 0-9"
        )
        try:
            return {"cpus": int(cpu_out), "total_ram_mb": int(mem_out), "avail_disk_gb": int(disk_out)}
        except ValueError as e:
            raise RemoteError(f"Could not read host resources: {cpu_out!r} {mem_out!r} {disk_out!r}") from e

    def compute_specs(self, count: int, auto_split: bool = False,
                      manual_cpu: int = 2, manual_ram: int = 1024,
                      manual_disk: int = 10) -> Dict[str, int]:
        """Per-container limits. Rejects allocations the host cannot provide."""
        host = self.detect_host_resources()
        ram_budget = host["total_ram_mb"] - HOST_RESERVED_RAM_MB
        if not auto_split:
            # Limits are caps, not reservations, so overcommit is allowed but never silent.
            if manual_ram * count > ram_budget:
                self.warnings.append(f"Memory limits total {manual_ram * count}MB; the host has {ram_budget}MB "
                                     f"after reserving {HOST_RESERVED_RAM_MB}MB.")
            if manual_disk * count > host["avail_disk_gb"]:
                self.warnings.append(f"Disk limits total {manual_disk * count}GB; the host has "
                                     f"{host['avail_disk_gb']}GB free.")
            return {"cpu": manual_cpu, "memory_mb": manual_ram, "disk_gb": manual_disk}

        per_container_ram = ram_budget // count
        per_container_disk = (host["avail_disk_gb"] - HOST_RESERVED_DISK_GB) // count
        if per_container_ram < MIN_MEMORY_MB or per_container_disk < MIN_DISK_GB:
            raise RemoteError(
                f"Host cannot fit {count} containers: {host['total_ram_mb']}MB RAM and "
                f"{host['avail_disk_gb']}GB free disk leave {per_container_ram}MB / {per_container_disk}GB each; "
                f"the minimum is {MIN_MEMORY_MB}MB / {MIN_DISK_GB}GB.")
        return {"cpu": host["cpus"], "memory_mb": per_container_ram, "disk_gb": per_container_disk}

    def existing_specs(self, names: Sequence[str]) -> Optional[Dict[str, int]]:
        """Limits of an already provisioned container, so auto-split stays stable across reruns."""
        for name in names:
            inst = self.query(f"/1.0/instances/{name}", missing_ok=True)
            if not inst:
                continue
            config = inst.get("expanded_config", {})
            memory = parse_size_mb(config.get("limits.memory", ""))
            disk = parse_size_mb(inst.get("expanded_devices", {}).get("root", {}).get("size", "")) // 1000
            cpu = config.get("limits.cpu", "")
            if memory and disk and cpu.isdigit():
                return {"cpu": int(cpu), "memory_mb": memory, "disk_gb": disk}
        return None

    def ensure_lxd(self) -> str:
        """Verifies or installs snap LXD on the host and waits until the daemon answers."""
        _, stdout, _ = self.runner.run("command -v lxc || true", check=False)
        if not stdout:
            _, os_id, _ = self.runner.run(". /etc/os-release && echo \"$ID\"")
            if os_id not in SUPPORTED_INSTALL_OS:
                raise RemoteError(f"Automatic LXD installation supports {', '.join(SUPPORTED_INSTALL_OS)}, "
                                  f"not '{os_id}'. Install LXD yourself, then run this tool again.")
            self.runner.run(
                "export DEBIAN_FRONTEND=noninteractive && apt-get update -y && apt-get install -y snapd && "
                "snap wait system seed.loaded && snap install lxd --channel=5.21/stable",
                timeout=600
            )
        self.runner.run("systemctl enable --now snap.lxd.daemon 2>/dev/null || true", check=False)
        self.runner.run("lxd waitready --timeout=60", timeout=90)
        _, ver, _ = self.runner.run("lxd version")
        return ver.strip()

    def detect_host_ip(self, explicit: Optional[str] = None) -> str:
        """NAT devices need a real address on the host, which can differ from the public IP."""
        if explicit:
            return str(ipaddress.IPv4Address(explicit))
        _, stdout, _ = self.runner.run(
            "ip -4 route get 1.1.1.1 | sed -n 's/.* src \\([0-9.]*\\).*/\\1/p' | head -n1")
        try:
            return str(ipaddress.IPv4Address(stdout.strip()))
        except ValueError as e:
            raise RemoteError("Could not detect the host IPv4 address; pass --listen-ip.") from e

    def nat_conflicts(self, wanted: set, own_names: Sequence[str]) -> List[str]:
        """NAT forwards of other containers have no listening socket, so `ss` can't see them."""
        conflicts = []
        for inst in self.query("/1.0/instances?recursion=1"):
            if inst.get("name") in own_names:
                continue
            for dev, conf in (inst.get("devices") or {}).items():
                if conf.get("type") != "proxy":
                    continue
                proto, _, rest = conf.get("listen", "").partition(":")
                address, _, ports = rest.rpartition(":")
                if address.startswith("["):
                    continue  # IPv6 listeners do not collide with the IPv4 forwards planned here
                for item in ports.split(","):
                    low, _, high = item.partition("-")
                    if low.isdigit() and any((p, proto) in wanted for p in range(int(low), int(high or low) + 1)):
                        conflicts.append(f"{item}/{proto} ({inst['name']} device {dev})")
        return conflicts

    def preflight_host_ports(self, planned: Sequence[Dict[str, Any]], own_names: Sequence[str] = ()) -> None:
        """Refuse before any change when a program or another container owns a planned host port."""
        _, stdout, _ = self.runner.run("ss -Htulnp 2>/dev/null || true", check=False)
        wanted = {(p["ext"], p["proto"]) for p in planned}
        conflicts = []
        for line in stdout.splitlines():
            parts = line.split()
            if len(parts) < 5 or parts[0] not in ("tcp", "udp"):
                continue
            port = parts[4].rpartition(":")[2]
            procs = set(re.findall(r'\("([^"]+)"', line))
            if port.isdigit() and (int(port), parts[0]) in wanted and not procs & {"lxd", "forkproxy"}:
                conflicts.append(f"{port}/{parts[0]} ({', '.join(sorted(procs)) or 'unknown process'})")
        conflicts += self.nat_conflicts(wanted, own_names)
        if conflicts:
            raise RemoteError("Planned host ports are already in use: " + ", ".join(sorted(set(conflicts))))

    def apply_host_network(self, planned: Sequence[Dict[str, Any]], tune: bool = True) -> Dict[str, str]:
        ports = sorted({f"{p['ext']}/{p['proto']}" for p in planned})
        _, stdout, _ = self.runner.run(host_firewall_script(self.bridge_name, ports))
        result = parse_kv(stdout)
        if tune:
            _, stdout, _ = self.runner.run(host_tuning_script())
            result.update(parse_kv(stdout))
        return result

    def ensure_storage_and_network(self) -> None:
        """Create or verify the pool, bridge and a dedicated profile. The default profile is left alone."""
        pools = {p["name"]: p for p in self.query("/1.0/storage-pools?recursion=1")}
        if self.storage_pool not in pools:
            self.runner.run(f"lxc storage create {self.storage_pool} {self.storage_driver}")

        networks = {n["name"]: n for n in self.query("/1.0/networks?recursion=1")}
        network = networks.get(self.bridge_name)
        if network is None:
            v6_flag = "ipv6.address=fd42:43::1/64 ipv6.nat=true" if self.enable_ipv6 else "ipv6.address=none"
            self.runner.run(
                f"lxc network create {self.bridge_name} "
                "ipv4.address=10.0.43.1/24 ipv4.nat=true "
                f"{v6_flag}"
            )
            network = self.query(f"/1.0/networks/{self.bridge_name}")
        config = network.get("config", {})
        address = config.get("ipv4.address", "")
        if not network.get("managed") or "/" not in address or config.get("ipv4.nat") != "true":
            raise RemoteError(f"Bridge {self.bridge_name} must be LXD-managed with an IPv4 subnet and ipv4.nat=true.")
        self.subnet = ipaddress.ip_interface(address).network

        profile = self.query(f"/1.0/profiles/{PROFILE_NAME}", missing_ok=True)
        if profile is None:
            self.runner.run(f"lxc profile create {PROFILE_NAME}")
            self.runner.run(f"lxc profile device add {PROFILE_NAME} root disk path=/ pool={self.storage_pool}")
            self.runner.run(f"lxc profile device add {PROFILE_NAME} eth0 nic network={self.bridge_name} name=eth0")
            return
        devices = profile.get("devices", {})
        if devices.get("root", {}).get("pool") != self.storage_pool or \
                devices.get("eth0", {}).get("network") != self.bridge_name:
            raise RemoteError(f"Profile {PROFILE_NAME} does not use pool {self.storage_pool} and "
                              f"network {self.bridge_name}. Fix it or pass matching options.")

    def ensure_image(self) -> str:
        """Keep one local copy under a stable alias, so every container uses the same image."""
        alias = "vps-lxc-" + re.sub(r"[^a-z0-9]+", "-", self.image.lower())
        if self.query(f"/1.0/images/aliases/{alias}", missing_ok=True) is None:
            print(f"[*] Caching image {self.image}...")
            self.runner.run(f"lxc image copy {shlex.quote(self.image)} local: --alias {alias} < /dev/null", timeout=900)
        self.local_image = alias
        return alias

    def static_ip(self, name: str, container_idx: int) -> str:
        """Stable per-container address: .10, .20, .30 ... of the bridge subnet."""
        if self.subnet is None:
            raise RemoteError("Bridge subnet is unknown; ensure_storage_and_network() must run first.")
        ip = self.subnet.network_address + 10 * container_idx
        if ip not in self.subnet:
            raise RemoteError(f"Bridge subnet {self.subnet} is too small for container {container_idx}.")
        for lease in self.query(f"/1.0/networks/{self.bridge_name}/leases"):
            if lease.get("address") == str(ip) and lease.get("hostname") not in (name, "vps", None):
                raise RemoteError(f"{ip} is already leased to {lease.get('hostname')}.")
        return str(ip)

    def _device_change(self, name: str, inst: Dict[str, Any], device: str, key: str, value: str) -> Optional[str]:
        """Command for one device value, or None when it already matches."""
        if inst.get("expanded_devices", {}).get(device, {}).get(key) == value:
            return None
        action = "set" if device in inst.get("devices", {}) else "override"
        return f"lxc config device {action} {name} {device} {key}={value}"

    def reconcile_limits(self, name: str, inst: Dict[str, Any], cpu: int, memory_mb: int,
                         disk_gb: int, ip: str) -> bool:
        """Apply only differences. Returns True when the static IP changed."""
        config = inst.get("expanded_config", {})
        wanted_keys = [
            ("limits.cpu", str(cpu)),
            ("limits.memory", f"{memory_mb}MB"),
            ("limits.memory.swap", "true"),
            ("security.nesting", "true"),
            ("security.syscalls.intercept.mknod", "true"),
            ("security.syscalls.intercept.setxattr", "true"),
        ]
        commands = [f"lxc config set {name} {key} {value}" for key, value in wanted_keys if config.get(key) != value]
        disk = self._device_change(name, inst, "root", "size", f"{disk_gb}GB")
        address = self._device_change(name, inst, "eth0", "ipv4.address", ip)
        commands += [c for c in (disk, address) if c]
        for command in commands:
            # Syscall interception requires LXD 5.x; ignore if unsupported on older LXD versions
            if "security.syscalls.intercept" in command:
                self.runner.run(command, check=False)
            else:
                self.runner.run(command)
        return address is not None

    def wait_ready(self, name: str, ip: str, timeout: int = 150) -> None:
        """Bounded wait for boot, the static address and DNS, with diagnostics on failure."""
        script = f"""
for i in $(seq 1 {timeout // 2}); do
    state=$(lxc exec {name} -- systemctl is-system-running 2>/dev/null)
    if {{ [ "$state" = running ] || [ "$state" = degraded ]; }} &&
        lxc exec {name} -- ip -4 -o addr show eth0 2>/dev/null | grep -qF ' {ip}/' &&
        lxc exec {name} -- getent hosts archive.ubuntu.com >/dev/null 2>&1; then
        exit 0
    fi
    sleep 2
done
echo "state=$state" >&2
lxc exec {name} -- ip -4 -o addr show eth0 >&2 || true
exit 1
"""
        code, _, stderr = self.runner.run(script, timeout=timeout + 30, check=False)
        if code != 0:
            raise RemoteError(f"Container '{name}' did not get boot, address {ip} and DNS within {timeout}s. "
                              f"Check host forwarding and firewall rules.\n{stderr}")

    def setup_clean_environment(self, name: str, hostname: str = "vps") -> None:
        """Set the hostname and a plain login banner, and keep the container free of guide files."""
        v6_sysctl = """
mkdir -p /etc/sysctl.d
cat << 'VPS_LXC_EOF' > /etc/sysctl.d/99-disable-ipv6.conf
net.ipv6.conf.all.disable_ipv6 = 1
net.ipv6.conf.default.disable_ipv6 = 1
net.ipv6.conf.lo.disable_ipv6 = 1
VPS_LXC_EOF
sysctl -p /etc/sysctl.d/99-disable-ipv6.conf 2>/dev/null || true
""" if not self.enable_ipv6 else """
rm -f /etc/sysctl.d/99-disable-ipv6.conf 2>/dev/null || true
"""
        clean_script = f"""
set -e
hostnamectl set-hostname {hostname} 2>/dev/null || echo "{hostname}" > /etc/hostname
grep -q "127.0.1.1 {hostname}" /etc/hosts || echo "127.0.1.1 {hostname}" >> /etc/hosts
rm -f /usr/local/bin/systemd-detect-virt /usr/local/bin/virt-what
. /etc/os-release
printf '%s\\n' '========================================================================' \\
    "  Welcome to $PRETTY_NAME" \\
    '========================================================================' > /etc/motd
printf '%s \\\\n \\\\l\\n' "$PRETTY_NAME" > /etc/issue
printf '%s\\n' "$PRETTY_NAME" > /etc/issue.net
rm -f /root/CONTAINER_GUIDE.md /etc/vps-container-info.md
{v6_sysctl}
"""
        self.runner.run(f"lxc exec {name} -- bash -c {shlex.quote(clean_script)}")

    def configure_ssh(self, name: str, password: Optional[str]) -> None:
        set_password = f"echo 'root:{password}' | chpasswd" if password else ":"
        setup_script = f"""
set -e
mkdir -p /etc/ssh/sshd_config.d
echo 'PermitRootLogin yes' > /etc/ssh/sshd_config.d/99-root.conf
echo 'PasswordAuthentication yes' >> /etc/ssh/sshd_config.d/99-root.conf
sed -i 's/.*PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config.d/*.conf /etc/ssh/sshd_config
sed -i 's/.*PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config.d/*.conf /etc/ssh/sshd_config
{set_password}
systemctl disable --now ssh.socket 2>/dev/null || true
systemctl enable --now ssh.service 2>/dev/null || systemctl restart ssh 2>/dev/null || systemctl restart sshd 2>/dev/null || true
"""
        self.runner.run(f"lxc exec {name} -- bash -c {shlex.quote(setup_script)}")

    def install_base_packages(self, name: str) -> None:
        """Generic images may not have an SSH server, which everything after this relies on."""
        script = f"""
set -e
export DEBIAN_FRONTEND=noninteractive
if ! dpkg -s {BASE_PACKAGES} >/dev/null 2>&1; then
    apt-get -o Acquire::Retries=3 update -y >/dev/null </dev/null
    apt-get -o Acquire::Retries=3 install -y {BASE_PACKAGES} >/dev/null </dev/null
fi
"""
        self.runner.run(f"lxc exec {name} -- bash -c {shlex.quote(script)}", timeout=600)

    def prepare_3xui_pre_requisites(self, name: str) -> bool:
        """Install what 3X-UI and vps-deploy-skill need. Returns True once packages are observed."""
        print(f"[*] Checking the 3X-UI / vps-deploy-skill stack on '{name}'...")
        script = f"""
set -e
export DEBIAN_FRONTEND=noninteractive
if ! dpkg -s {PACKAGES} >/dev/null 2>&1; then
    apt-get -o Acquire::Retries=3 update -y >/dev/null </dev/null
    apt-get -o Acquire::Retries=3 install -y {PACKAGES} >/dev/null </dev/null
fi
dpkg -s {PACKAGES} >/dev/null
"""
        self.runner.run(f"lxc exec {name} -- bash -c {shlex.quote(script)}", timeout=600)
        return True

    def reconcile_ports(self, name: str, port_defs: List[Dict[str, Any]], host_ip: str, ip: str,
                        inst: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Make each proxy device match the plan. Unchanged devices are not touched, and a failed
        replacement restores the previous device. Userspace is an explicit, reported fallback.
        """
        current = inst.get("devices", {})
        results = [dict(p) for p in port_defs]
        lines = ["e=$(mktemp)"]
        for p in results:
            dev, proto, ext, target = p["name"], p["proto"], p["ext"], p["int"]
            want = {"type": "proxy", "listen": f"{proto}:{host_ip}:{ext}", "connect": f"{proto}:{ip}:{target}", "nat": "true"}
            old = current.get(dev)
            if old == want:
                p["forward"] = "nat"
                continue
            add = f"lxc config device add {name} {dev} proxy listen={want['listen']} connect={want['connect']} nat=true"
            fallback = (f"lxc config device add {name} {dev} proxy listen={proto}:0.0.0.0:{ext} "
                        f"connect={proto}:127.0.0.1:{target}")
            restore = ":"
            if old:
                lines.append(f"lxc config device remove {name} {dev} >/dev/null 2>&1")
                keys = " ".join(f"{k}={v}" for k, v in sorted(old.items()) if k != "type")
                restore = f"lxc config device add {name} {dev} proxy {keys} >/dev/null 2>&1"
            lines.append(
                f"if {add} >/dev/null 2>\"$e\"; then echo 'PORT {dev} nat'; "
                f"elif {fallback} >/dev/null 2>>\"$e\"; then echo 'PORT {dev} userspace'; "
                f"else {restore}; echo \"PORTFAIL {dev} $(tail -n1 \"$e\")\"; fi"
            )
        if len(lines) > 1:
            _, stdout, _ = self.runner.run("\n".join(lines), timeout=300)
            modes = {}
            failures = []
            for line in stdout.splitlines():
                parts = line.split(" ", 2)
                if parts[0] == "PORT":
                    modes[parts[1]] = parts[2]
                elif parts[0] == "PORTFAIL":
                    failures.append(" ".join(parts[1:]))
            if failures:
                raise RemoteError(f"Port forwarding failed on '{name}': " + "; ".join(failures))
            for p in results:
                p.setdefault("forward", modes.get(p["name"], ""))

        applied = self.query(f"/1.0/instances/{name}").get("devices", {})
        missing = [p["name"] for p in results if p["name"] not in applied or not p.get("forward")]
        if missing:
            raise RemoteError(f"Port devices missing on '{name}': {', '.join(missing)}")
        return results

    def verify_ssh_forward(self, name: str, host_ip: str, ssh_port: int) -> None:
        script = (f"for i in 1 2 3 4 5 6 7 8 9 10; do "
                  f"timeout 3 bash -c 'exec 3<>/dev/tcp/{host_ip}/{ssh_port}; head -c 3 <&3' 2>/dev/null | grep -q SSH && exit 0; "
                  "sleep 2; done; exit 1")
        code, _, _ = self.runner.run(script, timeout=60, check=False)
        if code != 0:
            raise RemoteError(f"SSH on {host_ip}:{ssh_port} does not reach '{name}'.")

    def disk_quota_enforced(self, name: str, disk_gb: int) -> bool:
        """True only when the guest actually sees the quota, whatever the storage driver says."""
        code, stdout, _ = self.runner.run(f"lxc exec {name} -- df -BM --output=size / | tail -n1 | tr -dc 0-9", check=False)
        return code == 0 and stdout.isdigit() and int(stdout) <= disk_gb * 1000 * 1.1

    def deploy_container(self, name: str, hostname: str, ssh_port: int,
                         cpu: int = 2, memory_mb: int = 1024, disk_gb: int = 10,
                         custom_pass: Optional[str] = None,
                         is_primary_proxy: bool = False,
                         container_idx: int = 1,
                         prepare_3xui: bool = True,
                         host_ip: str = "",
                         public_ip: str = "",
                         known_password: Optional[str] = None,
                         rotate_password: bool = False,
                         https_override: Optional[int] = None) -> Dict[str, Any]:
        """Create the container if needed, then reconcile limits, access, packages and ports."""
        inst = self.query(f"/1.0/instances/{name}", missing_ok=True)
        is_new = inst is None
        ip = self.static_ip(name, container_idx)
        if is_new:
            print(f"[*] Initializing container '{name}' (Hostname: {hostname})...")
            self.runner.run(f"lxc init {self.local_image} {name} -p {PROFILE_NAME} < /dev/null", timeout=300)
            inst = self.query(f"/1.0/instances/{name}")

        print(f"[*] Reconciling limits for '{name}' (CPU: {cpu}, RAM: {memory_mb}MB, Disk: {disk_gb}GB)...")
        ip_changed = self.reconcile_limits(name, inst, cpu, memory_mb, disk_gb, ip)
        if inst.get("status") != "Running":
            self.runner.run(f"lxc start {name} < /dev/null", timeout=120)
        elif ip_changed:
            self.runner.run(f"lxc restart {name} < /dev/null", timeout=120)
        self.wait_ready(name, ip)
        self.install_base_packages(name)

        stored = inst.get("config", {}).get(PASSWORD_KEY)
        password = custom_pass or (None if rotate_password else stored or known_password)
        change_password = None
        if password is None and (is_new or rotate_password):
            password = generate_secure_password(16)
        if password and (is_new or rotate_password or custom_pass):
            change_password = password
        if password and password != stored:
            self.runner.run(f"lxc config set {name} {PASSWORD_KEY} {shlex.quote(password)}")

        print(f"[*] Configuring SSH and environment on '{name}'...")
        self.configure_ssh(name, change_password)
        self.setup_clean_environment(name, hostname=hostname)
        packages_ready = self.prepare_3xui_pre_requisites(name) if prepare_3xui else False

        port_defs = get_container_port_definitions(container_idx, ssh_port, is_primary_proxy, https_override)
        print(f"[*] Reconciling {len(port_defs)} port mappings for '{name}'...")
        inst = self.query(f"/1.0/instances/{name}")
        ports = self.reconcile_ports(name, port_defs, host_ip, ip, inst)
        self.verify_ssh_forward(name, host_ip, ssh_port)

        if any(p["forward"] == "userspace" for p in ports):
            self.warnings.append(f"{name}: some ports use the userspace fallback, which is slower and hides client IPs.")
        quota_enforced = self.disk_quota_enforced(name, disk_gb)
        if not quota_enforced:
            self.warnings.append(f"{name}: the {disk_gb}GB disk limit is not enforced by this storage pool. "
                                 "Use a btrfs, zfs or lvm pool, or ext4/XFS with project quotas.")

        info = self.query(f"/1.0/instances/{name}?recursion=1")
        ip6 = ""
        for addr in (info.get("state") or {}).get("network", {}).get("eth0", {}).get("addresses", []):
            if addr.get("family") == "inet6" and addr.get("scope") == "global":
                ip6 = addr.get("address", "")

        return {
            "name": name,
            "hostname": hostname,
            "status": info.get("status", ""),
            "ipv4": ip,
            "ipv6": ip6,
            "ssh_port": ssh_port,
            "user": "root",
            "password": password,
            "is_3xui_ready": packages_ready,
            "ports": ports,
            "deployer_config": deployer_config(public_ip or host_ip, container_idx, ssh_port, password, https_override),
            "specs": {
                "cpu_cores": cpu,
                "memory": f"{memory_mb}MB",
                "disk": f"{disk_gb}GB",
                "disk_quota_enforced": quota_enforced,
                "docker_nesting": True,
                "syscall_intercept": True
            }
        }
