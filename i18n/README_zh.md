# VPS LXC 容器自动化部署 Skill

> Linux VPS 高密度 LXC 容器自动拆分与管理引擎。
> 快速部署相互隔离的 Linux 容器（支持 1-6 个容器，2核CPU、1-2GB内存、10GB硬盘，或支持宿主机资源智能平分），具备独立 SSH 端口转发、强随机 root 密码、干净独立的环境规范、Cloudflare CDN 端口矩阵、Windows 原生 RDP 远程桌面直连，以及 3X-UI / Docker 嵌套支持。

[English](../README.md) | [中文说明](./README_zh.md)

---

## 核心功能

- **自动化宿主机环境就绪**：自动检测并安装配置 LXD 守护进程，配置高效的 `dir` 瘦分配存储池，初始化 `lxdbr0` 隔离网桥（集成 IPv4 / IPv6 NAT）。
- **多种资源分配模式**：
  - **默认固定规格**：2核 CPU、1024MB 内存、10GB 磁盘空间配额。
  - **宿主机资源智能平分（`--auto-split`）**：自动探测宿主机实际 CPU、RAM 和磁盘，预留宿主机系统底座开销后，将剩余算力与存储平均分配给各容器。
- **高兼容性 SSH 连接体系**：
  - 支持非标 SSH 端口（`--ssh-port 2222`）。
  - 支持 SSH 密钥免密认证（`--ssh-key ~/.ssh/id_rsa`，使用密钥时无需依赖 `sshpass`）。
  - 支持标准密码认证（`--ssh-pass` 或环境变量 `VPS_SSH_PASS`）。
- **干净独立的环境规范（真实透明）**：
  - **真实环境输出**：不伪造虚拟化二进制，不篡改检测命令，环境干净透明。
  - 统一规范的主机名（`vps`）与纯净标准欢迎横幅（不携带 `01`/`02` 编号后缀与硬件限额信息）。
  - 每个容器使用密码学级随机算法自动生成独立高强度 root 密码，**绝不与宿主机相同**。
- **全容器 Cloudflare CDN 端口矩阵**：
  - 为每台容器预开通 Cloudflare 官方支持的专属 HTTPS 端口（`443, 8443, 2053, 2083`）。
  - 支持通过 Cloudflare Origin Rules（回源规则）实现**浏览器纯域名免输端口号**的顶级体验。
- **原生远程桌面（Windows RDP 3389 直连）**：
  - 第 4 台专机原生绑定宿主机公网 `3389` 端口（TCP & UDP），分配 2GB 内存并开启 Swap，Windows 自带远程桌面客户端（`mstsc`）直连秒开。
- **原生 Docker 嵌套与系统调用拦截**：
  - 默认开启 `security.nesting=true`，并配合 LXD 5.21 LTS 配置 `security.syscalls.intercept.mknod=true` 与 `setxattr=true`，完美兼容 Docker、Docker Compose 与 overlay2。
- **内核级 Swap 分页支持**：
  - 默认开启 Swap 支持，防止 Chrome、编译或高并发应用遭遇 Linux OOM 强杀。
- **宿主机集中归档与容器纯净保障**：
  - 所有集群凭据、端口映射矩阵与 Cloudflare 回源指南统一保存在宿主机 `/root/02project/01LXD_vps_info/<IP>/`。
  - 严守容器纯净原则，容器内部为标准官方系统，不注入任何 markdown 说明文件。

---

## 标准架构拓扑（4 容器矩阵）

```
                        ┌────────────────────────────────────────────────────────┐
                        │             宿主机 (1 个公网 IPv4 / IPv6)              │
                        │             宿主机 SSH 端口: 22 (绝不修改)             │
                        └──────────────────────────┬─────────────────────────────┘
                                                   │
                         Managed Bridge: 10.0.43.1/24 (自带 IPv4/IPv6 NAT)
                                                   │
     ┌──────────────────────┬──────────────────────┴──────────────────────┬──────────────────────┐
     │                      │                                             │                      │
┌────▼─────────────┐   ┌────▼─────────────┐                         ┌─────▼────────────┐   ┌─────▼────────────┐
│ c1-proxy (vps)   │   │ c2-app (vps)     │                         │ c3-backup (vps)  │   │ c4-desktop (vps) │
│ - 内网:10.0.43.10│   │ - 内网:10.0.43.20│                         │ - 内网:10.0.43.30│   │ - 内网:10.0.43.40│
│ - 内存: 1GB+Swap │   │ - 内存: 1GB+Swap │                         │ - 内存: 768M+Swap│   │ - 内存: 2GB+Swap │
│ - SSH: 2201      │   │ - SSH: 2202      │                         │ - SSH: 2203      │   │ - SSH: 2204      │
│ - CF CDN: 443    │   │ - CF CDN: 8443   │                         │ - CF CDN: 2053   │   │ - CF CDN: 2083   │
│ - 3X-UI: 54840   │   │ - 3X-UI: 54841   │                         │ - 面板: 54842    │   │ - RDP: 3389(直连)│
│ - REALITY: 20159 │   │ - REALITY: 20160 │                         │ - REALITY: 20161 │   │ - Web: 8088      │
│ - HY2: 42972(UDP)│   │ - HY2: 42973(UDP)│                         │ - HY2: 42974(UDP)│   │ - 通用: 10041-42 │
└──────────────────┘   └──────────────────┘                         └──────────────────┘   └──────────────────┘
```

### 完整公网端口分配对照表

| 容器标识 | 内网静态 IP | SSH 端口 | Cloudflare HTTPS CDN 端口 | 核心代理与面板服务端口 | 预留通用高位端口池 | 推荐定位与分工 |
| :--- | :--- | :---: | :---: | :--- | :--- | :--- |
| **`c1-proxy`** | `10.0.43.10` | `2201` | **`80, 443`** (公网首选入口) | `54840` (3X-UI), `20159` (REALITY), `42972` (HY2 UDP) | `10011`, `10012` | 主力代理节点 & 原生 Web 网关 |
| **`c2-app`** | `10.0.43.20` | `2202` | **`8443`** | `54841` (3X-UI), `20160` (REALITY), `42973` (HY2 UDP) | `10021`, `10022` | 副代理节点 & 独立建站 |
| **`c3-backup`**| `10.0.43.30` | `2203` | **`2053`** | `54842` (备用面板), `20161` (REALITY), `42974` (HY2 UDP) | `10031`, `10032` | 备用节点 / 独立 API / 微服务 |
| **`c4-desktop`**| `10.0.43.40` | `2204` | **`2083`** | **`3389` (Windows MSTSC 远程桌面直连)**, `8088` (Web) | `10041`, `10042` | 图形专机 (XFCE4+XRDP+Chrome) & 建站 |

---

## 快速使用

### 环境要求
- Python 3.8+
- 系统安装有 OpenSSH（如使用密码登录还需 `sshpass`）

```bash
git clone https://github.com/arifulcrypto/vps-lxc-skill.git
cd vps-lxc-skill
```

### 命令示例

```bash
# 1. 预检与计划预览（Dry-run，不改动远程）
python3 scripts/vps_lxc.py --ip 198.51.100.1 --ssh-pass 'your_vps_password' --dry-run

# 2. 部署默认 2 台容器（2核1G，10GB硬盘，独立SSH端口与密码）
python3 scripts/vps_lxc.py --ip 198.51.100.1 --ssh-pass 'your_vps_password'

# 3. 使用非标 SSH 端口与 SSH 密钥免密登录
python3 scripts/vps_lxc.py --ip 198.51.100.1 --ssh-port 2222 --ssh-key ~/.ssh/id_ed25519

# 4. 自动平分宿主机内存与磁盘（扣除宿主机底座后平均划分）
python3 scripts/vps_lxc.py --ip 198.51.100.1 --ssh-pass 'your_vps_password' --auto-split

# 5. 自定义容器数量（最高支持创建 4 台）
python3 scripts/vps_lxc.py --ip 198.51.100.1 --ssh-pass 'your_vps_password' --count 4
```

---

## 部署档案与产物说明

部署完成后，所有集群凭据与文档将保存在宿主机 `/root/02project/01LXD_vps_info/<IP>/`（或 `./output/<IP>/`）：
1. `credentials_and_ports.md`：详细的容器 SSH 命令、内网 IP、各容器专属 root 密码及完整端口映射矩阵。
2. `cloudflare_origin_rules.md`：Cloudflare 免费 CDN 免端口回源配置全指南。
3. `README.md`：集群全局导航总览与快速连接命令。
4. `vps_lxc_<IP>_summary.txt`：清晰整洁的终端连接信息速查文本。
5. `result.json`：供第三方程序或自动化管道调用的结构化 JSON 数据。

---

## 开源协议

MIT License. 详见 [LICENSE](LICENSE)。

## 行为说明

- **可重复执行。** 重新运行时会对比 LXD 现状与计划，只修改差异：应用新的资源限制、启动已停止的容器、保留密码（使用 `--rotate-passwords` 才会更换），未变化的端口设备不会被触碰。
- **先校验后执行。** 名称、数量（1-6）、资源限制和完整端口矩阵都在修改宿主机前检查。计划端口被其他程序占用时直接停止。
- **独立 Profile。** 容器使用 `vps-lxc` profile，不修改宿主机的 `default` profile。
- **静态地址与内核 NAT。** 容器在网桥上获得 `.10`、`.20`、`.30` 等固定地址，端口转发使用 LXD NAT 模式并监听宿主机真实 IPv4。结果中记录每个端口的实际模式，`userspace` 表示使用了较慢的回退方式。
- **宿主机配置。** BBR 和 16 MB UDP 缓冲区在宿主机设置，因为容器无法自行设置。已启用的 UFW 或 firewalld 会添加网桥与计划端口规则，Docker 的 `FORWARD DROP` 策略由一个持久化单元处理。
- **如实报告。** `disk_quota_enforced` 表示容器内是否真实看到磁盘限制。默认 `dir` 存储池仅在启用项目配额的 ext4/XFS 上生效，需要硬限制时请在新存储池上使用 `--storage-driver btrfs`。`c4-desktop` 等名称仅为示例：工具只预留桌面端口，不安装桌面环境。
- **配合 vps-deploy-skill。** 每个容器都会生成 `deploy_<name>.json`，也可在部署工具中使用 `--from-lxc result.json --container <name>`。次级容器没有公网 80 端口，配置域名时使用 `cert_mode: dns-01`。
- **在已有业务的宿主机上新增容器。** 使用 `--first-index N --https-port P --no-host-tuning` 添加单个容器，不占用靠前的位置。端口检查同时覆盖监听程序和其他容器的 NAT 转发（这些转发没有监听套接字）。已在 LXD 4.0.15 的真实宿主机上验证。
- **自动安装 LXD** 支持 Ubuntu 和 Debian，其他系统请先自行安装 LXD。

## 系统与机器推荐

- 新宿主机首选 **Debian 13**（支持到 2030 年 6 月）或 **Ubuntu 24.04 LTS**（支持 6.8+ 内核与完整 BBR/Socket 激活，最好是 minimal 镜像）。必须是 KVM 或物理机，不支持 OpenVZ/LXC/Docker 类 VPS。
- LXD 推荐 **5.21 LTS**，内核 5.15 以上且包含 BBR。
- 4G 内存 KVM 实测（LXD + 2 个容器）：Debian 13 约 565 MB，Ubuntu 24.04 minimal 约 583 MB，两者内存开销差距仅约 18 MB。
- 配置：1 个容器 1 核 1G 内存 10G 硬盘；2 个容器 2 核 2G 20G；4 个容器 2-4 核 4G 30G，并配置 1-2G Swap。
- 容器空闲约 100 MB 内存，Ubuntu 与 Debian 镜像基本相同，保持默认镜像即可。
- 客户端：节点链接采用通用标准 X25519，无需添加非标准参数，全面兼容 v2rayN、Mihomo / Clash Verge Rev 及在线转换。
- 运行 `--check-host` 可在不做任何修改的情况下评估机器。详见 [Host Requirements](../docs/host-requirements.md)。
- 软件版本与官方下载链接见 [Software Versions](../docs/software-versions.md)，运行 `python3 scripts/check_versions.py` 可检查新版本。

## 月流量限制

- `--traffic-limit-gb 1500`：80% 记录警告，90% 限速 50 Mbit/s，98% 限速 5 Mbit/s，新月份自动解除，绝不停止服务。
- 状态查看：`cat /var/lib/vps-lxc/traffic-status`。

## 重启规则

重启后无需人工处理。每次部署都会安装开机自检。

- `vps-lxc-bootcheck.timer` 在开机 30 秒后运行：等待 LXD，启动列出的容器和停止的服务，为每个容器重新应用 BBR，测试 SSH 转发（必要时重启容器一次），重试约 4 分钟后把结果写入 `/var/lib/vps-lxc/boot-status`。
- 重启后等待 3 分钟再查看状态。`OK` 表示无需操作；`FAILED` 会列出异常项，查看 `/var/log/vps-lxc-bootcheck.log`，修复后运行 `systemctl start vps-lxc-bootcheck.service`。
- `upstream-down=` 表示外部中转或代理出口没有响应，本机服务正常，请检查对应服务商。
- 不要把再次重启作为第一步，也不要手动修改转发规则。
- 已有集群运行 `--install-boot-check` 即可添加自检，不会改动其他内容。
- 重启后 `iptables -t nat -S` 为空但端口正常时，是 LXD 切换到了 nftables，无需处理。

## 中继转发、住宅出口与 Xray 兼容性规范

在 LXC 容器（如 `c1-proxy` 或其他辅助容器）内配置四层 Realm 中继或住宅出口时遵循：
- **Realm 四层转发并发**：单个容器可同时运行 3X-UI 与 Realm 服务，互不干扰。将外部高端口（如 `10011`）精准转发至外部落地节点（美国家宽/ISP）。
- **双出口部署架构**：中继外部节点时，同时生成中继节点（中转加速）与直连原生节点（直连备用），保证故障容灾。
- **策略组置顶与排序**：在 Clash Verge Rev 配置中，`🚀 节点选择` 置于 `proxy-groups:` 最顶层第一项，组内首项直接选择 `⚡ 自动选择 (低延迟)`。
- **容器内 Xray 版本锁定**：容器内安装 3X-UI 时推荐锁定 Xray-core `v26.6.27`，彻底避免新版核心（v26.7.11+）对 Mihomo REALITY AEAD 握手破坏性变更；并确保 `client_inbounds.flow_override` 设置为 `xtls-rprx-vision`，避免 v2rayN 握手超时报 `-1`。
- **去敏感化命名**：客户端节点名称与说明文档中去除所有运营商敏感标识，保持中立专业。
