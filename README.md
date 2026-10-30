# VPS LXC Deployer Skill

> Automated LXC Container Provisioning Engine for Linux VPS Instances.
> Deploy high-density, isolated containers (2 vCPU, 1GB RAM, 10GB disk, or auto-split) with independent SSH ports, secure random passwords, clean environment, and 3X-UI / Docker nesting support.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-brightgreen.svg)](https://www.python.org/)

[English](./README.md) | [中文说明](./i18n/README_zh.md)

---

## Key Features

- **Automated Host Setup**: Auto-detects and installs LXD, configures lightweight `dir` storage pool, and provisions `lxdbr0` managed bridge with IPv4/IPv6 NAT out of the box.
- **Resource Allocation Flexibility**:
  - **Default Fixed Specs**: 2 vCPU, 1GB RAM (strict cgroup memory limit, swap isolation), 10GB disk quota.
  - **Auto-Split Mode (`--auto-split`)**: Fairly divides available host RAM and disk space equally between containers while reserving headroom for host OS.
- **SSH Connectivity & Compatibility**:
  - Supports custom SSH ports (`--ssh-port 2222`).
  - Supports SSH private keys (`--ssh-key ~/.ssh/id_rsa`) without requiring `sshpass`.
  - Supports password authentication (`--ssh-pass` or `VPS_SSH_PASS`).
- **Clean & Isolated Environment**:
  - Truthful, genuine environment reporting (zero virtualization spoofing or deceptive wrappers).
  - Clean unified hostnames (`vps`) and minimal standard login banner (MOTD without numbered suffixes or hardware leaks).
  - Cryptographically generated independent root passwords (guaranteed distinct from host).
- **Primary Node 3X-UI Ready (`--prepare-3xui`)**:
  - Container 1 is pre-equipped with the complete package stack needed for [vps-deploy-skill](https://github.com/arifulcrypto/vps-deploy-skill) (`curl, socat, cron, openssl, python3, iptables`).
  - Automatically maps public ports `80` and `443` to Container 1 for instant HTTPS / REALITY proxy deployment.
- **Independent SSH Management**:
  - Forwards host high ports (`2201`, `2202`, etc.) to container port `22` via LXD proxy devices.
  - Host SSH on port `22` remains 100% untouched and safe.
- **Docker Nesting**:
  - Enables `security.nesting=true` for running Docker and Docker Compose inside containers out of the box.

---

## Quick Start

### Prerequisites
- Python 3.8+
- OpenSSH client (and `sshpass` if using password authentication)

```bash
git clone https://github.com/arifulcrypto/vps-lxc-skill.git
cd vps-lxc-skill
```

### Usage Examples

```bash
# 1. Dry run (preview the plan without remote changes)
python3 scripts/vps_lxc.py --ip 198.51.100.1 --ssh-pass 'your_vps_password' --dry-run

# 2. Deploy default 2 containers with password authentication
python3 scripts/vps_lxc.py --ip 198.51.100.1 --ssh-pass 'your_vps_password'

# 3. Custom SSH port and SSH private key authentication
python3 scripts/vps_lxc.py --ip 198.51.100.1 --ssh-port 2222 --ssh-key ~/.ssh/id_ed25519

# 4. Auto-split host RAM & Disk fairly between 2 containers
python3 scripts/vps_lxc.py --ip 198.51.100.1 --ssh-pass 'your_vps_password' --auto-split

# 5. Custom container count, names, and starting SSH port
python3 scripts/vps_lxc.py --ip 198.51.100.1 --ssh-pass 'your_vps_password' \
  --count 2 --names vps-alice,vps-bob --ssh-base-port 2210

# 6. Run directly on local VPS host
python3 scripts/vps_lxc.py --local --count 2
```

---

## Architecture

```
                       ┌──────────────────────────────────────────────┐
                       │          Host VPS (IPv4 / IPv6)              │
                       │          Host SSH: port 22 (untouched)       │
                       └──────────────────────┬───────────────────────┘
                                              │
                                Managed Bridge lxdbr0 (NAT)
                                              │
                      ┌───────────────────────┴───────────────────────┐
                      │                                               │
        ┌─────────────▼───────────────┐                 ┌─────────────▼───────────────┐
        │    LXC Container: vps-01    │                 │    LXC Container: vps-02    │
        │ - 2 vCPU | 1GB RAM | 10GB   │                 │ - 2 vCPU | 1GB RAM | 10GB   │
        │ - Role: 3X-UI / Web Ready   │                 │ - Role: General Purpose VPS │
        │ - Ports :80, :443 mapped    │                 │ - Clean Standard Linux Env  │
        │ - User: root                │                 │ - User: root                │
        │ - Distinct Random Password  │                 │ - Distinct Random Password  │
        │ - Host Port :2201 -> :22    │                 │ - Host Port :2202 -> :22    │
        │ - Docker Nesting: Enabled   │                 │ - Docker Nesting: Enabled   │
        └─────────────────────────────┘                 └─────────────────────────────┘
```

---

## Output Artifacts

Upon completion, output files are created under `./output/<IP>/`:
- `vps_lxc_<IP>_summary.txt`: Human-readable summary containing connection commands and passwords.
- `result.json`: Machine-readable JSON metadata for orchestration.

---

## License

MIT License. See [LICENSE](LICENSE) for details.
