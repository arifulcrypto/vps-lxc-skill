# Host Requirements and Recommendations

Check any machine before you start. This changes nothing:

```bash
python3 scripts/vps_lxc.py --ip <IP> --ssh-port <PORT> --count <N> --check-host
```

`FAIL` stops a real run. `WARN` is reported and allowed.

## Recommended setup

| Item | Recommended | Also works | Avoid |
| :--- | :--- | :--- | :--- |
| Virtualization | KVM or bare metal | | OpenVZ, LXC or Docker VPS: LXD can't run inside them |
| Host OS | **Ubuntu 24.04 LTS** | Ubuntu 22.04, Debian 12 or 13 | Ubuntu 20.04 and older: out of standard support |
| Kernel | 6.x | 5.15 or newer | Older than 5.15 |
| LXD | **5.21 LTS** (installed automatically) | 6.x; 4.0 passed a live test but is old | New installs of 4.0 |
| Container image | **`ubuntu-minimal:24.04`** (default) | `images:debian/12`, `images:debian/13` | `images:` needs LXD 5.21 or newer |
| Storage | `btrfs` on new hosts if you need hard disk limits | `dir` (default, simplest) | Relying on `dir` limits without project quotas |

Automatic LXD installation supports Ubuntu and Debian. Debian as a *host* has not been tested yet; Debian as a *container image* has.

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

## Network

- One public IPv4 address. IPv6 is optional and is not forwarded to containers yet.
- The provider firewall must allow the mapped TCP and UDP ports. Hysteria 2 needs UDP.
- Keep the host SSH port away from the matrix, for example `39822`.
- BBR and 16 MB UDP buffers are set on the host automatically. Use `--no-host-tuning` on a host with live services.
- Secondary containers don't receive public port 80, so they need `cert_mode: dns-01`.
- If Docker runs on the host, its `FORWARD DROP` policy is handled by a small persistent unit.

## Cloudflare

- SSL mode: **Full (strict)**.
- Gray cloud for direct REALITY, orange cloud for CDN.
- HTTPS ports Cloudflare proxies: `443`, `2053`, `2083`, `2087`, `2096`, `8443`.
- Token: `Zone: DNS: Edit` on one zone. Add `Zone: Rulesets: Edit` only for Origin Rules. A Global API Key is not needed.

## Software versions

| Software | Version | Notes |
| :--- | :--- | :--- |
| 3X-UI | v3.11.0 | Tested version; pin it with `--xui-version` |
| Xray | 26.10.21 | Bundled with that 3X-UI release |
| Mihomo client | **v1.19.9 or newer** | v1.19.8 and older fail REALITY. v1.19.33 is tested in CI |
| Nginx | 1.19.4 or newer | Older versions use a fallback that also hides the real certificate |
| Python on your machine | 3.10 or newer | With `openssh-client`, plus `sshpass` for password login |

## Upgrading an existing host

`snap refresh lxd --channel=5.21/stable` is a one-way upgrade, and a release upgrade of the OS needs a reboot. Do both in a maintenance window, with a provider snapshot if you can.

A simple path for a small host: create a new VPS on Ubuntu 24.04, confirm it with `--check-host`, deploy, then move traffic over. That avoids changing a live machine.
