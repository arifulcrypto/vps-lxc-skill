# VPS LXC Deployer Skill

> Automated LXC Container Provisioning Engine for Linux VPS Instances.
> Deploy high-density, isolated containers (1-6 containers, 2 vCPU, 1-2GB RAM, 10GB disk, or auto-split) with independent SSH ports, secure random passwords, Cloudflare CDN port matrix, native RDP 3389 direct connection, and 3X-UI / Docker nesting support.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-brightgreen.svg)](https://www.python.org/)

[English](./README.md) | [中文说明](./i18n/README_zh.md)

---


Before setting up a host, read [Host Requirements](docs/host-requirements.md) or run `--check-host`: recommended OS with measured resource use, machine sizes, limits and network settings. [Software Versions](docs/software-versions.md) lists tested versions and official downloads.

## Key Features

- **Automated Host Setup**: Auto-detects and installs LXD, configures a `dir` storage pool by default, and provisions `lxdbr0` managed bridge with IPv4/IPv6 NAT out of the box.
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
- **Native Remote Desktop (RDP 3389) & Pure Western Fonts**:
  - Container 4 features native Windows MSTSC direct connection on host port `3389` (TCP & UDP) with 2GB RAM + Swap.
  - Defaults to pure English locale (`en_US.UTF-8`) with standard Western fonts (`Liberation`, `DejaVu`) without CJK/Chinese fonts to eliminate browser font fingerprint leakage.
- **Docker Nesting & Syscall Interception**:
  - Enables `security.nesting=true` and kernel syscall intercepts (`mknod`, `setxattr`) on LXD 5.21 LTS for unprivileged Docker, Docker Compose, and overlay2 out of the box.
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

# 5. Custom container count (up to 6)
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

## Behavior You Can Rely On

- **Repeatable runs.** A rerun compares LXD state with the plan and changes only the differences. It applies new limits, starts stopped containers, keeps passwords (use `--rotate-passwords` to change them) and leaves matching port devices alone.
- **Validated first.** Names, count (1-6), limits and the whole port matrix are checked before any host change. A planned port held by another program stops the run.
- **Dedicated profile.** Containers use the `vps-lxc` profile. The host's `default` profile is never modified.
- **Static addresses and kernel NAT.** Containers get `.10`, `.20`, `.30` ... on the bridge, and forwards use LXD NAT mode with the host's real IPv4 address. The result records the mode for each port. `userspace` means the slower fallback was needed.
- **Host setup.** BBR and 16 MB UDP buffers are set on the host, because containers cannot set them. Active UFW or firewalld gets the bridge and planned-port rules, and a Docker `FORWARD DROP` policy is handled by a small persistent unit.
- **Honest reports.** `disk_quota_enforced` shows whether the guest really sees the limit. The default `dir` pool only enforces it on ext4/XFS with project quotas, so use `--storage-driver btrfs` on a new pool when you need a hard limit. A name such as `c4-desktop` is only an example: the tool reserves the desktop ports but does not install a desktop.
- **Pair with vps-deploy-skill.** Each container gets `deploy_<name>.json`, or use `--from-lxc result.json --container <name>` in the deployer. Secondary containers do not receive public port 80, so they use `cert_mode: dns-01` when a domain is set.
- **Adding to a busy host.** `--first-index N --https-port P --no-host-tuning` adds one container without reusing the first positions. The port check covers listening programs and NAT forwards of other containers, which have no listening socket. Tested on a live host with LXD 4.0.15.
- **Automatic LXD install** supports Ubuntu and Debian. On other systems, install LXD first.

## Reboot Rules

Reboots need no manual work. Every deployment installs a boot self-check.

**What happens automatically after every boot**

1. `vps-lxc-bootcheck.timer` runs 30 seconds after the host starts.
2. It waits for LXD, starts the listed containers, and starts any watched service that is down.
3. It reapplies BBR inside each container, because each one keeps its own setting.
4. It tests every SSH forward and restarts a container once if its forward stays down.
5. It retries for about 4 minutes, then writes the result to `/var/lib/vps-lxc/boot-status`.

Containers are also set to `boot.autostart=true`. Containers created separately are not touched.

**Rules for agents**

- After a reboot, wait 3 minutes, then read `/var/lib/vps-lxc/boot-status` or run `--check-host`.
- `OK` means finished. Do not restart anything.
- `FAILED` lists what stayed down. Read `/var/log/vps-lxc-bootcheck.log`, fix that item, then run `systemctl start vps-lxc-bootcheck.service`.
- Never reboot again as a first response, and never edit forwarding rules by hand.
- On a cluster created before this feature, run `--install-boot-check`. It adds the check for running containers and changes nothing else.

**Known reboot behavior**

| What you see | Meaning | Action |
| :--- | :--- | :--- |
| `iptables -t nat -S` looks empty, ports still work | LXD may switch to nftables after a boot | None. Check with `nft list ruleset` |
| Manual `iptables` rules are gone | They were never saved | Save them yourself, or use the provider firewall |
| Host BBR is off | The setting was never saved | The tool saves it unless `--no-host-tuning` was used |
| Forwards fail after the provider changes the IP | Forwards are bound to the old address | Re-run the tool, then update DNS |
| Extra disk is not visible | The partition needs growing | Run `growpart` and `resize2fs` |

## Relay, Residential Extensions & Xray Compatibility

When configuring Layer 4 Realm relays or residential exits inside LXC containers (e.g., `c1-proxy` or secondary containers):
- **Realm Layer 4 Relay**: Containers can host both 3X-UI and Realm relay side-by-side without port collisions. Forward local high ports (e.g. `10011`) directly to external residential / ISP landing nodes.
- **Dual Landing Provisioning**: Always provide both the relayed node (intermediate VPS -> landing exit) and the direct landing node (fallback).
- **Client Group Ordering**: In Clash Verge Rev configurations, place `🚀 节点选择` at index 0 of `proxy-groups:`, and set `⚡ 自动选择 (低延迟)` as the first item within it.
- **In-Container Xray Version**: When installing 3X-UI inside containers, pin Xray-core to `v26.6.27` to avoid REALITY AEAD handshake incompatibilities with Mihomo / Clash Verge Rev, and ensure `flow_override: xtls-rprx-vision` in SQLite to prevent v2rayN `-1` timeout.
- **Neutral Naming**: Ensure client-facing configurations are free of sensitive operator/carrier branding.
