# VPS LXC Deployer Skill

> Automated LXC Container Provisioning Engine for Linux VPS Instances.
> Deploy high-density, isolated containers (2-4 containers, 2 vCPU, 1-2GB RAM, 10GB disk, or auto-split) with independent SSH ports, secure random passwords, Cloudflare CDN port matrix, native RDP 3389 direct connection, and 3X-UI / Docker nesting support.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-brightgreen.svg)](https://www.python.org/)

[English](./README.md) | [中文说明](./i18n/README_zh.md)

---

## Key Features

- **Automated Host Setup**: Auto-detects and installs LXD, configures lightweight `dir` storage pool, and provisions `lxdbr0` managed bridge with IPv4/IPv6 NAT out of the box.
- **Resource Allocation Flexibility**:
  - **Default Fixed Specs**: 2 vCPU, 1GB RAM (strict cgroup memory limit, swap enabled), 10GB disk quota.
  - **Auto-Split Mode (`--auto-split`)**: Fairly divides available host RAM and disk space equally between containers while reserving headroom for host OS.
- **SSH Connectivity & Compatibility**:
  - Supports custom SSH ports (`--ssh-port 2222`).
  - Supports SSH private keys (`--ssh-key ~/.ssh/id_rsa`) without requiring `sshpass`.
  - Supports password authentication (`--ssh-pass` or `VPS_SSH_PASS`).
- **Clean & Isolated Environment**:
  - Truthful, genuine environment reporting (zero virtualization spoofing or deceptive wrappers).
  - Clean unified hostnames (`vps`) and minimal standard login banner (MOTD without numbered suffixes or hardware leaks).
  - Cryptographically generated independent root passwords (guaranteed distinct from host).
- **Multi-Container Port Matrix & Cloudflare CDN**:
  - Dedicated Cloudflare HTTPS CDN ports pre-mapped for each container (`443, 8443, 2053, 2083`).
  - Full support for Cloudflare Origin Rules for pure domain access without port suffixes.
- **Native Remote Desktop (RDP 3389)**:
  - Container 4 features native Windows MSTSC direct connection on host port `3389` (TCP & UDP) with 2GB RAM + Swap.
- **Docker Nesting**:
  - Enables `security.nesting=true` for running Docker and Docker Compose inside containers out of the box.
- **Host Information Archive & Clean Containers**:
  - Centralizes all cluster credentials, port forwarding matrices, and Cloudflare Origin Rules under `/root/02project/01LXD_vps_info/<IP>/` on the host.
  - Strict container cleanliness: containers remain 100% standard and untainted (zero internal guide markdown files).

---

## Architecture (4-Container Standard Topology)

```
                        ┌────────────────────────────────────────────────────────┐
                        │             Host VPS (1 Public IPv4 / IPv6)            │
                        │             Host SSH: port 22 (untouched)              │
                        └──────────────────────────┬─────────────────────────────┘
                                                   │
                         Managed Bridge: 10.0.43.1/24 (IPv4/IPv6 NAT)
                                                   │
     ┌──────────────────────┬──────────────────────┴──────────────────────┬──────────────────────┐
     │                      │                                             │                      │
┌────▼─────────────┐   ┌────▼─────────────┐                         ┌─────▼────────────┐   ┌─────▼────────────┐
│ c1-proxy (vps)   │   │ c2-app (vps)     │                         │ c3-backup (vps)  │   │ c4-desktop (vps) │
│ - IP: 10.0.43.10 │   │ - IP: 10.0.43.20 │                         │ - IP: 10.0.43.30 │   │ - IP: 10.0.43.40 │
│ - RAM: 1GB+Swap  │   │ - RAM: 1GB+Swap  │                         │ - RAM: 768MB+Swap│   │ - RAM: 2GB+Swap  │
│ - SSH: 2201      │   │ - SSH: 2202      │                         │ - SSH: 2203      │   │ - SSH: 2204      │
│ - CF CDN: 443    │   │ - CF CDN: 8443   │                         │ - CF CDN: 2053   │   │ - CF CDN: 2083   │
│ - 3X-UI: 54840   │   │ - 3X-UI: 54841   │                         │ - Panel: 54842   │   │ - RDP: 3389(RDP) │
│ - REALITY: 20159 │   │ - REALITY: 20160 │                         │ - REALITY: 20161 │   │ - Web: 8088      │
│ - HY2: 42972(UDP)│   │ - HY2: 42973(UDP)│                         │ - HY2: 42974(UDP)│   │ - Apps: 10041-42 │
└──────────────────┘   └──────────────────┘                         └──────────────────┘   └──────────────────┘
```

### Complete Port Allocation Matrix

| Container ID | Internal IP | SSH Port | Cloudflare HTTPS CDN Port | Proxy & Core Service Ports | Extra Pre-Mapped Port Pool | Primary Role |
| :--- | :--- | :---: | :---: | :--- | :--- | :--- |
| **`c1-proxy`** | `10.0.43.10` | `2201` | **`80, 443`** (Primary) | `54840` (3X-UI), `20159` (REALITY), `42972` (HY2 UDP) | `10011`, `10012` | Primary Proxy & Web Gateway |
| **`c2-app`** | `10.0.43.20` | `2202` | **`8443`** | `54841` (3X-UI), `20160` (REALITY), `42973` (HY2 UDP) | `10021`, `10022` | Secondary Proxy & Web App |
| **`c3-backup`**| `10.0.43.30` | `2203` | **`2053`** | `54842` (Panel), `20161` (REALITY), `42974` (HY2 UDP) | `10031`, `10032` | Standby Microservice & Backup |
| **`c4-desktop`**| `10.0.43.40` | `2204` | **`2083`** | **`3389` (Windows MSTSC RDP Direct)**, `8088` (Web) | `10041`, `10042` | Desktop (XFCE4+XRDP+Chrome) & Web |

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

# 4. Auto-split host RAM & Disk fairly between containers
python3 scripts/vps_lxc.py --ip 198.51.100.1 --ssh-pass 'your_vps_password' --auto-split

# 5. Custom container count (up to 4)
python3 scripts/vps_lxc.py --ip 198.51.100.1 --ssh-pass 'your_vps_password' --count 4
```

---

## Output Artifacts

Upon completion, all credentials, port forwarding matrices, and guides are organized under `/root/02project/01LXD_vps_info/<IP>/` (or `./output/<IP>/`):
- `credentials_and_ports.md`: Comprehensive table of container SSH commands, unique passwords, and complete port mapping matrix.
- `cloudflare_origin_rules.md`: Guide for setting up Cloudflare Free CDN Origin Rules for portless domain access.
- `README.md`: Central cluster navigation index.
- `vps_lxc_<IP>_summary.txt`: Human-readable summary containing connection commands and passwords.
- `result.json`: Machine-readable JSON metadata for orchestration.

---

## License

MIT License. See [LICENSE](LICENSE) for details.
