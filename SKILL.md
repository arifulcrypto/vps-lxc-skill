---
name: vps-lxc-creator
description: >-
  Deploys and manages isolated LXC containers (default 2 containers, 2 vCPU, 1GB RAM,
  10GB disk, distinct secure root passwords, independent SSH port forwardings,
  and Docker nesting) on a Linux VPS over SSH or directly on localhost.
---

# VPS LXC Creator Skill

> Automated LXC Container Provisioning Engine for Linux VPS Instances.

[English](./SKILL.md) | [中文说明](./i18n/SKILL_zh.md)

---

## 1. Overview & Capabilities

Source of truth for every agent adapter (`claude/`, `openai/`, `gemini/`). The engine is `scripts/vps_lxc.py`; agents should invoke it instead of improvising remote bash commands.

- **Automated Host Setup**: Auto-detects and installs snap LXD on Ubuntu/Debian/CentOS, initializes storage pools (`dir`), and provisions a managed bridge (`lxdbr0`) with IPv4/IPv6 NAT out of the box.
- **Hardware Isolation & Auto-Split**:
  - **Fixed Specification Mode (Default)**: 2 vCPU, 1024MB RAM (strict cgroup memory quota, swap isolation), 10GB disk quota.
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
  - Maps host ports (default `2201`, `2202`, ...) directly to container SSH port 22 using LXD proxy devices (zero impact on host SSH port 22).
- **Nested Container Support**:
  - Pre-enables `security.nesting=true` for running Docker, Docker Compose, and containerd seamlessly inside LXC.

---

## 2. Architecture

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

## 3. Inputs & Parameters

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `--ip` | string | — | Remote VPS public IPv4 address |
| `--ssh-port` | int | `22` | Host SSH port |
| `--ssh-user` | string | `root` | Host SSH user |
| `--ssh-pass` | string | — | Host SSH password (or `VPS_SSH_PASS` env var) |
| `--ssh-key` | string | — | Path to SSH private key file |
| `--local` | flag | `false` | Execute directly on the local host |
| `--count` | int | `2` | Number of LXC containers to create |
| `--names` | string | `vps-01,vps-02` | Comma-separated custom container names |
| `--auto-split` | flag | `false` | Auto-detect host specs and divide RAM/Disk fairly |
| `--cpu` | int | `2` | vCPU allocation per container |
| `--memory` | int | `1024` | Memory allocation in MB per container |
| `--disk` | int | `10` | Disk allocation in GB per container |
| `--ssh-base-port` | int | `2201` | Starting host port for SSH port mapping |
| `--prepare-3xui` | bool | `true` | Pre-install 3X-UI dependencies & map ports 80/443 on container 1 |
| `--output-dir` | string | `./output/<ip>`| Directory to export credential summary & JSON |
| `--dry-run` | flag | `false` | Validate inputs and preview configuration |

---

## 4. Runbook for Agents

1. **Collect & Validate**: Gather target VPS IP, SSH credentials (password or private key, custom port if any), and container specifications.
2. **Preview (Dry-run)**: Generate a config JSON or CLI invocation and run with `--dry-run`. Present the planned containers, ports, and resource limits to the user.
3. **Execute**: Call `python3 scripts/vps_lxc.py --config <file>`. Do not improvise ad-hoc SSH or iptables commands.
4. **Deliver Credentials**: Read `./output/<ip>/vps_lxc_<ip>_summary.txt` and `result.json`. Present the SSH connection commands and distinct random passwords to the user. Remind the user that these are credentials.

---

## 5. Generated Artifacts

- `vps_lxc_<IP>_summary.txt`: Human-readable summary table containing container IPs, mapped ports, and unique passwords.
- `result.json`: Machine-readable JSON for orchestration and CI/CD pipelines.
