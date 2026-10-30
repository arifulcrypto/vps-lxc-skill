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

    def setup_clean_environment(self, name: str, hostname: str, cpu: int, ram_mb: int) -> None:
        """
        Configures a clean, genuine Linux environment inside the container:
        - Sets the designated hostname and /etc/hosts entry.
        - Ensures genuine virtualization detection (removes any fake/spoofed binaries).
        - Sets a clean, standard login banner (MOTD) displaying allocated system resources.
        - Sets standard issue banner.
        """
        clean_script = f"""
set -e
# 1. Set clean hostname
hostnamectl set-hostname {hostname} 2>/dev/null || echo "{hostname}" > /etc/hostname
grep -q "{hostname}" /etc/hosts || echo "127.0.1.1 {hostname}" >> /etc/hosts

# 2. Ensure genuine virtualization detection (never spoof or fake binaries)
rm -f /usr/local/bin/systemd-detect-virt /usr/local/bin/virt-what

# 3. Clean and informative MOTD (truthful resource profile, no fake KVM claims)
cat << 'EOF' > /etc/motd
========================================================================
  Welcome to Ubuntu 22.04 LTS ({hostname})
  Allocated Profile: {cpu} vCPU, {ram_mb}MB RAM
========================================================================
EOF

# 4. Standard issue banner
echo "Ubuntu 22.04 LTS \\n \\l" > /etc/issue
echo "Ubuntu 22.04 LTS" > /etc/issue.net
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
                         is_primary_proxy: bool = False) -> Dict[str, Any]:
        """
        Creates and configures an isolated LXC container according to specifications.
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
            self.runner.run(f"lxc config set {name} limits.memory.swap false")
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

        # Add or update SSH proxy device
        dev_name = f"ssh{ssh_port}"
        self.runner.run(f"lxc config device remove {name} {dev_name} 2>/dev/null || true", check=False)
        self.runner.run(
            f"lxc config device add {name} {dev_name} proxy "
            f"listen=tcp:0.0.0.0:{ssh_port} connect=tcp:127.0.0.1:22"
        )

        # If primary proxy container, map ports 80 and 443 and pre-install prerequisites
        if is_primary_proxy:
            self.runner.run("lxc config device add " + name + " p80 proxy listen=tcp:0.0.0.0:80 connect=tcp:127.0.0.1:80 2>/dev/null || true", check=False)
            self.runner.run("lxc config device add " + name + " p443 proxy listen=tcp:0.0.0.0:443 connect=tcp:127.0.0.1:443 2>/dev/null || true", check=False)
            self.prepare_3xui_pre_requisites(name)

        # Setup clean environment (genuine reporting, clean hostname and MOTD)
        print(f"[*] Configuring clean environment on '{name}'...")
        self.setup_clean_environment(name, hostname, cpu, memory_mb)

        # Fetch container info
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

        return {
            "name": name,
            "hostname": hostname,
            "status": info.get("status", "RUNNING"),
            "ipv4": ip4,
            "ipv6": ip6,
            "ssh_port": ssh_port,
            "user": "root",
            "password": password,
            "is_3xui_ready": is_primary_proxy,
            "specs": {
                "cpu_cores": cpu,
                "memory": f"{memory_mb}MB",
                "disk": f"{disk_gb}GB",
                "docker_nesting": True
            }
        }
