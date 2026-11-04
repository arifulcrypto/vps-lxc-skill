# Host Requirements and Recommendations

Check any machine before you start. This changes nothing:

```bash
python3 scripts/vps_lxc.py --ip <IP> --ssh-port <PORT> --count <N> --check-host
```

`FAIL` stops a real run. `WARN` is reported and allowed.

## Which OS to choose

**Recommended host OS: Ubuntu 24.04 LTS or Debian 12.** Both are fully tested and officially supported. Ubuntu 24.04 (especially the minimal cloud image) provides modern 6.8+ kernels with native BBR and systemd socket support, while Debian 12 provides a proven lightweight footprint.

| OS | Tested Status | Verdict |
| :--- | :--- | :--- |
| **Ubuntu 24.04 LTS** | Fully tested in CI | **Primary choice**, modern kernel 6.8+, full BBR |
| **Debian 12** | Fully tested in CI | **Primary choice**, rock solid, lightweight |
| Legacy / Other | Untested | Use Ubuntu 24.04 or Debian 12 |

### Measured on real 4 GB, 2 vCPU KVM hosts

Each host was installed fresh, got LXD and two containers through this tool, then did a real reboot. CI repeats this in the `Host OS` workflow.

| OS | Memory, fresh boot | Memory, LXD + 2 containers | Disk, fresh | Disk, with stack |
| :--- | :--- | :--- | :--- | :--- |
| Debian 12 | 274 MB | 572 MB | 991 MB | 3.1 GB |
| Ubuntu 24.04 minimal | 314 MB | 583 MB | 481 MB | 2.7 GB |
| Ubuntu 24.04 standard | 370 MB | 624 MB | 1.6 GB | 3.8 GB |

**Does Debian use less than Ubuntu?** Yes, but only a little: about 50 MB less than standard Ubuntu 24.04, and almost identical to the minimal image.

## Recommended setup

| Item | Recommended | Also works | Avoid |
| :--- | :--- | :--- | :--- |
| Virtualization | KVM or bare metal | | OpenVZ, LXC or Docker VPS: LXD can't run inside them |
| Host OS | **Ubuntu 24.04 LTS** or **Debian 12** | | Ubuntu 20.04 and older, unsupported distros |
| Kernel | 6.x with BBR | 5.15 or newer | Kernels with no BBR module |
| LXD | **5.21 LTS** (installed automatically) | 6.x | New installs of 4.0 |
| Container image | **`ubuntu-minimal:24.04`** (default) | `images:debian/12` | `images:` needs LXD 5.21 or newer |
| Storage | `btrfs` on new hosts if you need hard disk limits | `dir` (default, simplest) | Relying on `dir` limits without project quotas |

## Machine size

| Containers | vCPU | RAM | Swap | Disk |
| :--- | :--- | :--- | :--- | :--- |
| 1 | 1 | 1 GB | 1 GB | 10 GB |
| 2 | 2 | 2 GB | 1-2 GB | 20 GB |
| 4 | 2-4 | 4 GB | 2 GB | 30 GB |

These leave headroom for traffic. A busy proxy needs more CPU and memory than an idle one, so scale up for heavy use.

### Measured use

From the CI full-stack job, with each container running 3X-UI v3.11.0 and idle:

| Image | Memory used | Memory available (1 GB limit) | Page cache |
| :--- | :--- | :--- | :--- |
| `ubuntu-minimal:24.04` | 98-109 MB | 866-878 MB | about 750 MB |
| `images:debian/12` | 95-106 MB | 870-881 MB | about 465 MB |
| `images:debian/13` | 99-108 MB | 867-877 MB | about 585 MB |

Main processes in a container: `x-ui` about 90-99 MB, `xray` about 36-42 MB, `fail2ban` about 28-35 MB. The LXD daemon uses about 230 MB on the host.

**Which image uses the least?** They are effectively equal. Page cache is reclaimable, so the lower Debian figure is not a real saving. Keep the default unless you prefer Debian.

A 512 MB container limit worked in a live test. A 2 GB host with 3 GB swap ran four existing containers plus a test container. Use that as a floor, not a target.

## Example: 2 vCPU, 4 GB RAM, 22 GB disk, 1,500 GB traffic

This is the layout used on a real host with four containers. CPU, disk and swap are shared. Memory has hard limits.

| Container | Role | `limits.memory` | `limits.cpu.priority` |
| :--- | :--- | :--- | :--- |
| c1 | Proxy | 1024 MB | 8 |
| c2 | Proxy with residential exit | 768 MB | 8 |
| c3 | Realm relay | 384 MB | 8 |
| c4 | Desktop | 1024 MB | 3 |

- Host keeps about 700 MB. Idle proxy containers used about 140 MB and the relay about 60 MB, so these limits leave room for traffic.
- Keep `limits.cpu` at the host's core count. Priority only matters when the CPU is busy, so the desktop can't slow the proxies.
- Swap: 1-2 GB with `vm.swappiness=10`. It's a safety net, shared by everything.
- Cap logs at 100 MB on the host and 64 MB in containers with journald's `SystemMaxUse`.
- With `dir` storage, all containers share the disk. The traffic guard logs a warning at 85% full.

```bash
lxc config set c1 limits.memory 1024MB
lxc config set c1 limits.cpu.priority 8
```

Both commands apply live, with no restart.

## Traffic limit

```bash
python3 scripts/vps_lxc.py --ip <IP> --ssh-port <PORT> --traffic-limit-gb 1500 --traffic-reset-day 1
```

This installs vnStat and a timer that runs every 10 minutes. Services are never stopped, so you can always reach the server.

| Used | Action |
| :--- | :--- |
| 80% | Logged warning |
| 90% | Host upload limited to 50 Mbit/s |
| 98% | Host upload limited to 5 Mbit/s |
| New month | Limit removed automatically |

Status: `cat /var/lib/vps-lxc/traffic-status`

- It counts download plus upload, the cautious reading. Providers differ, so compare it with your control panel.
- Set `--traffic-reset-day` to your billing day.
- Counting starts at install, so earlier use this month isn't included.
- 1,500 GB a month averages about 4.6 Mbit/s, so short bursts are fine. A permanent speed cap isn't needed.
- Metered exits have their own budget. The guard doesn't track them, so set a limit with the provider.

## Network

- One public IPv4 address. IPv6 is optional and is not forwarded to containers yet.
- The provider firewall must allow the mapped TCP and UDP ports. Hysteria 2 needs UDP.
- Keep the host SSH port away from the matrix, for example `39822`.
- BBR and 16 MB UDP buffers are set on the host automatically. Use `--no-host-tuning` on a host with live services.
- Each container keeps its own BBR setting. The boot self-check reapplies it.
- Secondary containers don't receive public port 80, so they need `cert_mode: dns-01`.
- If Docker runs on the host, its `FORWARD DROP` policy is handled by a small persistent unit.

## Cloudflare

- SSL mode: **Full (strict)**.
- Gray cloud for direct REALITY, orange cloud for CDN.
- HTTPS ports Cloudflare proxies: `443`, `2053`, `2083`, `2087`, `2096`, `8443`.
- Token: `Zone: DNS: Edit` on one zone. Add `Zone: Rulesets: Edit` only for Origin Rules. A Global API Key is not needed.

## Software versions

See [Software Versions and Downloads](software-versions.md) for tested versions, official links and upgrade steps.

## Upgrading an existing host

`snap refresh lxd --channel=5.21/stable` is a one-way upgrade, and a release upgrade of the OS needs a reboot. Do both in a maintenance window, with a provider snapshot if you can.

A simple path for a small host: create a new VPS on Debian 13 or Ubuntu 24.04, confirm it with `--check-host`, deploy, then move traffic over. That avoids changing a live machine.
