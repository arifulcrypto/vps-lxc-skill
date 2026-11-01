#!/usr/bin/env python3
"""
Provisioning and container generation logic for VPS LXC Skill.
Manages host LXD setup, dynamic resource allocation/auto-split,
clean Linux container configuration, 3X-UI pre-requisites, and secure credential generation.
"""
import json
import secrets
import shlex
import string
from typing import Any, Dict, List, Optional, Tuple

from scripts.remote import RemoteError, TargetRunner

PASSWORD_CHARS = string.ascii_letters + string.digits + "@#%="


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


def get_container_port_definitions(container_idx: int, ssh_port: int, is_primary: bool = False) -> List[Dict[str, Any]]:
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
    if container_idx == 1:
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
        cf_ports = [2087, 2096]
        cf_p = cf_ports[(container_idx - 5) % len(cf_ports)]
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
        4: "233boy VMess-WS / Trojan 极高兼容协议",
        5: "预留扩展端口 (FastAPI / Web 应用)",
        6: "预留扩展端口 (MySQL / Redis / 数据库)",
        7: "预留扩展端口 (Docker 服务 / API)",
        8: "预留扩展端口 (自定义业务 1)",
        9: "预留扩展端口 (自定义业务 2)",
    }
    for offset in range(1, 10):
        p = base + offset
        ports.append({"name": f"p{p}", "ext": p, "int": p, "proto": "tcp", "role": pool_roles.get(offset, "预留业务端口")})

    return ports


class LXCProvisioner:
    def __init__(self, runner: TargetRunner, bridge_name: str = "lxdbr0",
                 storage_pool: str = "default", image: str = "ubuntu:22.04"):
        self.runner = runner
        self.bridge_name = bridge_name
        self.storage_pool = storage_pool
        self.image = image

    def detect_host_resources(self) -> Dict[str, int]:
        """Detects host CPU cores, total/available RAM in MB, and available disk in GB."""
        # CPU cores
        _, cpu_out, _ = self.runner.run("nproc || echo 2")
        cpu_cores = int(cpu_out.strip()) if cpu_out.strip().isdigit() else 2

        # Memory in MB
        _, mem_out, _ = self.runner.run("free -m | awk '/^Mem:/{print $2}' || echo 2048")
        total_ram = int(mem_out.strip()) if mem_out.strip().isdigit() else 2048

        # Available Disk in GB on root mount
        _, disk_out, _ = self.runner.run("df -BG / | awk 'NR==2{sub(/G/,\"\",$4); print $4}' || echo 20")
        avail_disk = int(disk_out.strip()) if disk_out.strip().isdigit() else 20

        return {
            "cpus": cpu_cores,
            "total_ram_mb": total_ram,
            "avail_disk_gb": avail_disk
        }

    def compute_specs(self, count: int, auto_split: bool = False,
                      manual_cpu: int = 2, manual_ram: int = 1024,
                      manual_disk: int = 10) -> Dict[str, int]:
        """
        Calculates per-container hardware limits.
        If auto_split is True, divides host RAM and disk fairly among containers.
        """
        if not auto_split:
            return {
                "cpu": manual_cpu,
                "memory_mb": manual_ram,
                "disk_gb": manual_disk
            }

        host = self.detect_host_resources()
        # Reserve 512MB RAM for host OS
        allocatable_ram = max(512 * count, host["total_ram_mb"] - 512)
        per_container_ram = allocatable_ram // count

        # Reserve 3GB Disk for host OS
        allocatable_disk = max(5 * count, host["avail_disk_gb"] - 3)
        per_container_disk = allocatable_disk // count

        return {
            "cpu": host["cpus"],
            "memory_mb": per_container_ram,
            "disk_gb": per_container_disk
        }

    def ensure_lxd(self) -> str:
        """Verifies or installs snap LXD on the host."""
        code, stdout, _ = self.runner.run("which lxc || true", check=False)
        if not stdout:
            self.runner.run(
                "export DEBIAN_FRONTEND=noninteractive && "
                "(command -v apt-get >/dev/null && (apt-get update -y && apt-get install -y snapd) || "
                " command -v dnf >/dev/null && dnf install -y snapd || "
                " command -v yum >/dev/null && yum install -y snapd) && "
                "snap install lxd",
                timeout=300
            )

        self.runner.run("systemctl enable --now snap.lxd.daemon 2>/dev/null || true")
        _, ver, _ = self.runner.run("lxd version")
        return ver.strip()

    def ensure_storage_and_network(self) -> None:
        """Configures default dir storage pool and managed bridge network."""
        # 1. Storage pool
        code, stdout, _ = self.runner.run("lxc storage list --format json", check=False)
        pools = [p["name"] for p in json.loads(stdout or "[]")]
        if self.storage_pool not in pools:
            self.runner.run(f"lxc storage create {self.storage_pool} dir")

        # 2. Bridge network
        code, stdout, _ = self.runner.run("lxc network list --format json", check=False)
        networks = [n["name"] for n in json.loads(stdout or "[]")]
        if self.bridge_name not in networks:
            self.runner.run(
                f"lxc network create {self.bridge_name} "
                "ipv4.address=10.0.43.1/24 ipv4.nat=true "
                "ipv6.address=fd42:43::1/64 ipv6.nat=true"
            )

        # 3. Default profile linkage
        code, stdout, _ = self.runner.run("lxc profile show default --format json", check=False)
        prof = json.loads(stdout or "{}")
        devices = prof.get("devices", {})

        if "root" not in devices:
            self.runner.run(f"lxc profile device add default root disk path=/ pool={self.storage_pool}")
        if "eth0" not in devices:
            self.runner.run(f"lxc profile device add default eth0 nic network={self.bridge_name} name=eth0")

    def cache_base_image(self) -> str:
        """Checks for local minimal Ubuntu image, copies if missing."""
        code, stdout, _ = self.runner.run("lxc image list --format json", check=False)
        images = json.loads(stdout or "[]")
        for img in images:
            for alias in img.get("aliases", []):
                if alias.get("name") in ("ubuntu-minimal/22.04", "ubuntu:22.04", "22.04"):
                    return img["fingerprint"]

        print("[*] Pre-caching lightweight Ubuntu 22.04 LTS minimal image...")
        self.runner.run(
            "lxc image copy ubuntu-minimal:22.04 local: --copy-aliases < /dev/null",
            timeout=300
        )
        code, stdout, _ = self.runner.run("lxc image list ubuntu-minimal:22.04 --format json")
        imgs = json.loads(stdout or "[]")
        return imgs[0]["fingerprint"] if imgs else "ubuntu:22.04"

    def setup_clean_environment(self, name: str, hostname: str = "vps") -> None:
        """
        Configures a clean, genuine Linux environment inside the container:
        - Sets the designated hostname ('vps' by default) and /etc/hosts entry.
        - Ensures genuine virtualization detection (removes any fake/spoofed binaries).
        - Sets a clean, standard login banner (MOTD) without specs or numbered identifiers.
        - Sets standard issue banner.
        - Enforces strict container cleanliness: ensures zero internal guide files or markdown notes
          exist inside the container (/root/CONTAINER_GUIDE.md, /etc/vps-container-info.md).
        """
        clean_script = f"""
set -e
# 1. Set clean hostname
hostnamectl set-hostname {hostname} 2>/dev/null || echo "{hostname}" > /etc/hostname
grep -q "127.0.1.1 {hostname}" /etc/hosts || echo "127.0.1.1 {hostname}" >> /etc/hosts

# 2. Ensure genuine virtualization detection (never spoof or fake binaries)
rm -f /usr/local/bin/systemd-detect-virt /usr/local/bin/virt-what

# 3. Clean standard login banner (no numbered hostnames or resource quotas printed)
cat << 'EOF' > /etc/motd
========================================================================
  Welcome to Ubuntu 22.04 LTS
========================================================================
EOF

# 4. Standard issue banner
echo "Ubuntu 22.04 LTS \\n \\l" > /etc/issue
echo "Ubuntu 22.04 LTS" > /etc/issue.net

# 5. Strict cleanliness: remove any internal guide files so container remains 100% standard
rm -f /root/CONTAINER_GUIDE.md /etc/vps-container-info.md
"""
        self.runner.run(f"lxc exec {name} -- bash -c {shlex.quote(clean_script)}")

    def prepare_3xui_pre_requisites(self, name: str) -> None:
        """
        Pre-installs packages and prerequisites for 3X-UI / vps-deploy-skill:
        curl, socat, cron, openssl, iproute2, python3, ca-certificates, iptables.
        """
        print(f"[*] Pre-installing 3X-UI / vps-deploy-skill stack on '{name}'...")
        script = """
export DEBIAN_FRONTEND=noninteractive
apt-get update -y >/dev/null </dev/null
apt-get install -y curl socat cron python3 openssl iproute2 tar ca-certificates ufw iptables >/dev/null </dev/null

# Persist BBR settings
if modprobe tcp_bbr 2>/dev/null || grep -qw bbr /proc/sys/net/ipv4/tcp_available_congestion_control 2>/dev/null; then
    printf 'net.core.default_qdisc=fq\\nnet.ipv4.tcp_congestion_control=bbr\\n' > /etc/sysctl.d/99-vps-skill.conf
    sysctl -p /etc/sysctl.d/99-vps-skill.conf >/dev/null 2>&1 || true
fi
"""
        self.runner.run(f"lxc exec {name} -- bash -c {shlex.quote(script)}", timeout=180)

    def deploy_container(self, name: str, hostname: str, ssh_port: int,
                         cpu: int = 2, memory_mb: int = 1024, disk_gb: int = 10,
                         custom_pass: Optional[str] = None,
                         is_primary_proxy: bool = False,
                         container_idx: int = 1,
                         prepare_3xui: bool = True) -> Dict[str, Any]:
        """
        Creates and configures an isolated LXC container according to specifications.
        Pre-installs full VPN/3X-UI prerequisites and maps abundant ports (14-16 ports)
        for Direct REALITY, Hy2, Cloudflare CDN, Realm relay, and Residential proxies.
        """
        code, stdout, _ = self.runner.run(f"lxc list {name} --format json", check=False)
        existing = json.loads(stdout or "[]")
        is_new = len(existing) == 0

        password = custom_pass or generate_secure_password(16)

        if is_new:
            print(f"[*] Initializing container '{name}' (Hostname: {hostname})...")
            self.runner.run(f"lxc init ubuntu-minimal:22.04 {name} < /dev/null", timeout=120)

            print(f"[*] Applying resource limits for '{name}' (CPU: {cpu}, RAM: {memory_mb}MB, Disk: {disk_gb}GB)...")
            self.runner.run(f"lxc config set {name} limits.cpu {cpu}")
            self.runner.run(f"lxc config set {name} limits.memory {memory_mb}MB")
            self.runner.run(f"lxc config set {name} limits.memory.swap true")
            self.runner.run(f"lxc config set {name} security.nesting true")

            # Disk quota
            self.runner.run(
                f"lxc config device override {name} root size={disk_gb}GB 2>/dev/null || "
                f"lxc config device set {name} root size {disk_gb}GB 2>/dev/null || true"
            )

            print(f"[*] Starting container '{name}'...")
            self.runner.run(f"lxc start {name} < /dev/null", timeout=60)

        # Configure SSH and password inside container
        print(f"[*] Setting root password and independent SSH for '{name}'...")
        setup_script = f"""
mkdir -p /etc/ssh/sshd_config.d
echo 'PermitRootLogin yes' > /etc/ssh/sshd_config.d/99-root.conf
echo 'PasswordAuthentication yes' >> /etc/ssh/sshd_config.d/99-root.conf
sed -i 's/.*PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config.d/*.conf /etc/ssh/sshd_config 2>/dev/null || true
sed -i 's/.*PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config.d/*.conf /etc/ssh/sshd_config 2>/dev/null || true
echo 'root:{password}' | chpasswd
systemctl restart ssh 2>/dev/null || systemctl restart sshd 2>/dev/null || true
"""
        self.runner.run(f"lxc exec {name} -- bash -c {shlex.quote(setup_script)}")

        # Setup clean environment (genuine reporting, clean hostname and MOTD)
        print(f"[*] Configuring clean environment on '{name}'...")
        self.setup_clean_environment(name, hostname=hostname)

        # Pre-install full 3X-UI / VPN prerequisites on container if prepare_3xui is enabled
        if prepare_3xui:
            self.prepare_3xui_pre_requisites(name)

        # Fetch container info (IP address)
        code, stdout, _ = self.runner.run(f"lxc list {name} --format json")
        info = json.loads(stdout)[0]
        ip4 = ""
        ip6 = ""
        for net_name, net_data in info.get("state", {}).get("network", {}).items():
            if net_name == "eth0":
                for addr in net_data.get("addresses", []):
                    if addr.get("family") == "inet" and addr.get("scope") == "global":
                        ip4 = addr.get("address")
                    elif addr.get("family") == "inet6" and addr.get("scope") == "global":
                        ip6 = addr.get("address")

        # Map all ports for the container
        port_defs = get_container_port_definitions(container_idx, ssh_port, is_primary_proxy)
        print(f"[*] Mapping {len(port_defs)} dedicated ports for container '{name}'...")
        for p in port_defs:
            dev = p["name"]
            proto = p["proto"]
            ext = p["ext"]
            target = p["int"]
            self.runner.run(f"lxc config device remove {name} {dev} 2>/dev/null || true", check=False)
            if dev.startswith("ssh"):
                self.runner.run(
                    f"lxc config device add {name} {dev} proxy "
                    f"listen={proto}:0.0.0.0:{ext} connect={proto}:127.0.0.1:{target}",
                    check=False
                )
            else:
                conn_target = f"{ip4}:{target}" if ip4 else f"127.0.0.1:{target}"
                self.runner.run(
                    f"lxc config device add {name} {dev} proxy "
                    f"listen={proto}:0.0.0.0:{ext} connect={proto}:{conn_target} nat=true 2>/dev/null || "
                    f"lxc config device add {name} {dev} proxy "
                    f"listen={proto}:0.0.0.0:{ext} connect={proto}:127.0.0.1:{target}",
                    check=False
                )

        return {
            "name": name,
            "hostname": hostname,
            "status": info.get("status", "RUNNING"),
            "ipv4": ip4,
            "ipv6": ip6,
            "ssh_port": ssh_port,
            "user": "root",
            "password": password,
            "is_3xui_ready": prepare_3xui,
            "ports": port_defs,
            "specs": {
                "cpu_cores": cpu,
                "memory": f"{memory_mb}MB",
                "disk": f"{disk_gb}GB",
                "docker_nesting": True
            }
        }
