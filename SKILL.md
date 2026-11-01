---
name: vps-lxc-creator
description: >-
  Deploys and manages isolated LXC containers (2-4 containers, 2 vCPU, 1-2GB RAM,
  10GB disk, distinct secure root passwords, independent SSH port forwardings,
  Cloudflare CDN port matrix, RDP remote desktop, and Docker nesting) on a Linux VPS over SSH or directly on localhost.
---

# VPS LXC Creator Skill

> Automated LXC Container Provisioning Engine for Linux VPS Instances.

[English](./SKILL.md) | [中文说明](./i18n/SKILL_zh.md)

---

## 1. Overview & Capabilities

Source of truth for every agent adapter (`claude/`, `openai/`, `gemini/`). The engine is `scripts/vps_lxc.py`; agents should invoke it instead of improvising remote bash commands.

- **Automated Host Setup**: Auto-detects and installs snap LXD on Ubuntu/Debian/CentOS, initializes storage pools (`dir`), and provisions a managed bridge (`lxdbr0`) with IPv4/IPv6 NAT out of the box.
- **Hardware Isolation & Auto-Split**:
  - **Fixed Specification Mode (Default)**: 2 vCPU, 1024MB RAM (strict cgroup memory quota, swap enabled), 10GB disk quota.
  - **Auto-Split Mode (`--auto-split`)**: Auto-detects host RAM and disk, reserves host OS headroom, and fairly divides resources equally among containers.
- **SSH Connectivity & Key Support**:
  - Supports non-standard SSH ports (`--ssh-port`).
  - Supports SSH private keys (`--ssh-key`) for key-based authentication (no `sshpass` required).
  - Supports password authentication (`--ssh-pass`).
- **Clean & Isolated Environment**:
  - Truthful, genuine environment reporting (zero virtualization spoofing or deceptive wrappers).
  - Clean unified hostname configuration (`vps`) and clean standard login banner (MOTD without numbered suffixes or hardware leaks).
  - Cryptographically generated independent root passwords (guaranteed distinct from host).
- **Primary Node 3X-UI Ready (`--prepare-3xui`)**:
  - Container 1 is pre-equipped with prerequisites for `17_vps_skill` (`curl, socat, cron, openssl, python3, iptables`).
  - Automatically maps public ports 80 and 443 to Container 1 for instant proxy deployment.
- **Independent SSH Management**:
  - Maps host ports (default `2201`, `2202`, `2203`, `2204`) directly to container SSH port 22 using LXD proxy devices (zero impact on host SSH port 22).
- **Nested Container Support**:
  - Pre-enables `security.nesting=true` for running Docker, Docker Compose, and containerd seamlessly inside LXC.
- **Kernel-Level Swap Support**:
  - Sets `limits.memory.swap=true` so containers under burst workloads (desktop environments, Chrome, compilations) page gracefully to host swap rather than getting killed by OOM.
- **Central Host Information Archive (`/root/02project/01LXD_vps_info/<IP>/`)**:
  - Centralizes all connection credentials, port mapping matrices, Cloudflare Origin Rules, and container guides into a dedicated host directory (`/root/02project/01LXD_vps_info/<IP>/`).
  - **Strict Container Cleanliness**: Containers remain completely clean, untainted official Linux installations. Zero internal guide files or markdown notes are placed inside tenant containers.

---

## 2. Multi-Container Topologies & Port Matrix

### 4-Container Standard Architecture

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

### Complete Port Allocation Matrix (All Containers Full-VPN & Relay Ready)

| Container ID | Internal IP | SSH Port | Cloudflare HTTPS CDN Port | 3X-UI & Direct Proxies | Realm Relays & Residential | Extra Port Pool | Primary Role |
| :--- | :--- | :---: | :---: | :--- | :--- | :--- | :--- |
| **`c1-proxy`** | `10.0.43.10` | `2201` | **`80, 443`** (Primary) | `54840` (3X-UI), `20159` (REALITY), `42972` (HY2 UDP) | `10011-12` (Realm), `10013` (Res), `10014` (233boy) | `10015~10019` | Primary Gateway & Multi-Node |
| **`c2-app`** | `10.0.43.20` | `2202` | **`8443`** | `54841` (3X-UI), `20160` (REALITY), `42973` (HY2 UDP) | `10021-22` (Realm), `10023` (Res), `10024` (233boy) | `10025~10029` | Full Proxy Node & Web App |
| **`c3-backup`**| `10.0.43.30` | `2203` | **`2053`** | `54842` (3X-UI), `20161` (REALITY), `42974` (HY2 UDP) | `10031-32` (Realm), `10033` (Res), `10034` (233boy) | `10035~10039` | Standby Microservice & Relay |
| **`c4-desktop`**| `10.0.43.40` | `2204` | **`2083`** | `54843` (3X-UI), `20162` (REALITY), `42975` (HY2 UDP) | `10041-42` (Realm), `10043` (Res), `10044` (233boy) | `10045~10049`, `3389` (RDP), `8088` | Desktop & Full Proxy Node |


---

## 3. Cloudflare Origin Rules Guide (Pure Domain Access)

Cloudflare Free Plan officially supports proxying HTTPS over 6 ports: `443, 8443, 2053, 2083, 2087, 2096`.  
Using Cloudflare **Origin Rules**, visitors access websites via pure standard domains (`https://sub.domain.com`) without specifying port numbers in browser:

1. **DNS Setup**: Point `sub.domain.com` to host public IP with Orange Cloud (Proxied) enabled.
2. **Create Origin Rule** in Cloudflare Dashboard:
   - Navigate to: **Rules** -> **Origin Rules** -> **Create Rule**.
   - Expression: `Hostname equals sub.domain.com`
   - Destination Port: Select **Rewrite to...** and enter the container's designated Cloudflare port (e.g. `8443` for `c2`, `2053` for `c3`, `2083` for `c4`).
3. **Visitor Experience**:
   - Visitors access `https://sub.domain.com` directly over standard port 443.
   - Cloudflare edge proxies and rewrites destination port to your container port.
   - Clean URLs, valid SSL certificates, DDoS protection, and CDN caching out of the box.

---

## 4. Inputs & Parameters

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `--ip` | string | — | Remote VPS public IPv4 address |
| `--ssh-port` | int | `22` | Host SSH port |
| `--ssh-user` | string | `root` | Host SSH user |
| `--ssh-pass` | string | — | Host SSH password (or `VPS_SSH_PASS` env var) |
| `--ssh-key` | string | — | Path to SSH private key file |
| `--local` | flag | `false` | Execute directly on the local host |
| `--count` | int | `2` | Number of LXC containers to create (supports up to 4) |
| `--names` | string | `vps-01,vps-02` | Comma-separated custom container names |
| `--auto-split` | flag | `false` | Auto-detect host specs and divide RAM/Disk fairly |
| `--cpu` | int | `2` | vCPU allocation per container |
| `--memory` | int | `1024` | Memory allocation in MB per container |
| `--disk` | int | `10` | Disk allocation in GB per container |
| `--ssh-base-port` | int | `2201` | Starting host port for SSH port mapping |
| `--prepare-3xui` | bool | `true` | Pre-install 3X-UI dependencies & map ports 80/443 on container 1 |
| `--output-dir` | string | `/root/02project/01LXD_vps_info/<ip>` | Directory to export credential summaries, markdown guides & JSON |
| `--dry-run` | flag | `false` | Validate inputs and preview configuration |

---

## 5. Runbook for Agents

1. **Collect & Validate**: Gather target VPS IP, SSH credentials (password or private key, custom port if any), and container specifications.
2. **Preview (Dry-run)**: Generate a config JSON or CLI invocation and run with `--dry-run`. Present the planned containers, ports, and resource limits to the user.
3. **Execute**: Call `python3 scripts/vps_lxc.py --config <file>`. Do not improvise ad-hoc SSH or iptables commands.
4. **Deliver Credentials**: Read `/root/02project/01LXD_vps_info/<ip>/credentials_and_ports.md` (or `./output/<ip>/`). Present the SSH connection commands and distinct random passwords to the user.
5. **Cluster Documentation & Management**: Read `/root/02project/01LXD_vps_info/<ip>/` on the host to discover all pre-forwarded public ports, Cloudflare Origin Rules, and container parameters. Containers remain standard and clean.

---

## 6. Generated Artifacts

All cluster documentation and credentials are organized cleanly in `/root/02project/01LXD_vps_info/<IP>/`:

- `credentials_and_ports.md`: Comprehensive table of all container SSH commands, unique passwords, and complete port mapping matrix.
- `cloudflare_origin_rules.md`: Step-by-step guide for configuring Cloudflare Free Origin Rules to route standard HTTPS domains to alternate container ports.
- `README.md`: Central cluster navigation index and operational guide.
- `vps_lxc_<IP>_summary.txt`: Plain-text quick reference archive.
- `result.json`: Machine-readable deployment metadata for orchestration and CI/CD pipelines.
