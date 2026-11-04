---
name: vps-lxc-creator
description: >-
  在 Linux VPS 上通过 SSH 或本地自动化部署并管理高密度隔离的 LXC 容器（支持 1-6 个容器，2核CPU、1-2GB内存、
  10GB硬盘、支持宿主机资源智能平分、各容器专属强随机密码、独立 SSH 端口映射、Cloudflare CDN 端口矩阵、RDP 远程桌面直连，以及 Docker 嵌套容器支持）。
---

# VPS LXC Creator Skill（中文）

英文版 [`SKILL.md`](../SKILL.md) 为准。核心自动化引擎为 `scripts/vps_lxc.py`，智能体应优先调用该脚本，而不是自行拼接零散的远程 shell 命令。

[English](../SKILL.md) | [中文说明](./SKILL_zh.md)

---

## 一、核心定位与特性

- **宿主机自动适配**：自动探测并按需安装配置 snap LXD 服务，配置高效轻量的 `dir` 瘦分配存储池，初始化 `lxdbr0` 隔离网桥（自动开启 IPv4 / IPv6 NAT）。
- **灵活的资源分配模式**：
  - **默认固定规格**：默认每容器分配 2 核 vCPU、`1024MB` 内存（支持内核级 Swap 分页）、`10GB` 磁盘配额。
  - **宿主机资源智能平分（`--auto-split`）**：自动探测宿主机实际物理内存与磁盘空间，预留系统底座开销后，平均平分给所有容器。
- **高兼容性 SSH 认证**：
  - 支持非标 SSH 端口（`--ssh-port`）。
  - 支持 SSH 密钥免密登录（`--ssh-key`，无需 `sshpass`）。
  - 支持密码登录（`--ssh-pass`）。
- **干净独立的环境规范（真实透明）**：
  - **真实环境输出**：不伪造虚拟化二进制，不篡改检测命令，环境干净透明。
  - 统一规范的主机名（`vps`）与纯净标准登录欢迎横幅（不携带 `01`/`02` 编号后缀与硬件限额信息）。
  - 每个容器使用密码学级随机算法自动生成独立高强度 root 密码，**绝对不与宿主机相同**。
- **首个容器 3X-UI 极速就绪（`--prepare-3xui`）**：
  - 容器 1 预装 `17_vps_skill` 所需全套依赖，并自动转发公网 `80` 与 `443` 端口，实现开箱即用。
- **独立 SSH 访问管理**：
  - 自动通过 LXD 内置 proxy 设备映射宿主机高位端口（默认 `2201`, `2202`, `2203`, `2204`）至容器内部的 `22` 端口。
  - **绝对不动宿主机默认 22 端口与既有网络，保障 VPS 绝不失联**。
- **内置 Docker 嵌套支持**：
  - 预开启 `security.nesting=true`，容器内可直接原生安装并运行 Docker 与 Docker Compose。
- **内核级 Swap 弹性支持**：
  - 默认开启 `limits.memory.swap=true`，面对桌面环境、Google Chrome、编译等突发内存开销，内核平滑分页至宿主机 Swap，彻底杜绝进程被 OOM 强杀。
- **宿主机集中信息归档中心（`/root/02project/01LXD_vps_info/<IP>/`）**：
  - 将所有容器的访问凭据、端口映射表、Cloudflare 回源规则统一集中归档于宿主机专用目录，便于统一运维与检索。
  - **严守容器纯净原则**：所有容器内部均保持标准纯净官方 Linux 环境，严禁在租户容器内乱塞维护说明或 markdown 文件（不生成 `/root/CONTAINER_GUIDE.md`）。

---

## 二、多容器标准架构与公网端口分配矩阵

### 4 容器标准拓扑架构图

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

## 三、Cloudflare 纯域名建站指南 (Origin Rules 免端口访问)

Cloudflare 官方免费套餐支持通过以下 6 个端口代理 HTTPS 流量：`443, 8443, 2053, 2083, 2087, 2096`。  
利用 Cloudflare 的 **Origin Rules（回源规则）**，全世界访客在浏览器地址栏直接输入纯域名（如 `https://myweb.com`，默认 443 端口），即可自动回源到容器对应的独立端口，**地址栏无需携带任何端口号尾缀**：

1. **域名解析**：在 Cloudflare DNS 将二级域名解析至 VPS 宿主机公网 IP，并**开启小黄云（Proxied 代理）**。
2. **在 Cloudflare 配置 Origin Rules**：
   - 进入控制台 -> **Rules (规则)** -> **Origin Rules (回源规则)** -> 点击 **Create Rule**；
   - 规则匹配条件：选择 `Hostname equals <你的完整域名>`；
   - **Destination Port**：勾选 `Rewrite to...`，填入对应容器的 Cloudflare 端口（`c2` 填 `8443`，`c3` 填 `2053`，`c4` 填 `2083`）；
3. **完成与生效**：
   - 访客通过纯域名访问；
   - Cloudflare 在边缘接管并自动重写回源端口，完整享受免费 SSL、DDoS 防御与 CDN 加速。

---

## 四、输入参数表

| 参数名 | 类型 | 默认值 | 详细说明 |
| :--- | :--- | :--- | :--- |
| `--ip` | string | — | 目标 VPS 的公网 IPv4 地址 |
| `--ssh-port` | int | `22` | 宿主机 SSH 端口 |
| `--ssh-user` | string | `root` | 宿主机 SSH 用户名 |
| `--ssh-pass` | string | — | 宿主机 SSH 密码（也可通过环境变量 `VPS_SSH_PASS` 提供） |
| `--ssh-key` | string | — | SSH 私钥文件路径 |
| `--local` | flag | `false` | 直接在当前宿主机本机执行（无需 SSH） |
| `--count` | int | `2` | 欲创建的 LXC 容器数量（支持创建 2 至 4 台） |
| `--names` | string | `vps-01,vps-02` | 自定义容器名称（逗号分隔） |
| `--auto-split` | flag | `false` | 智能平分宿主机内存与磁盘配额 |
| `--cpu` | int | `2` | 每台容器分配的 CPU 核心数 |
| `--memory` | int | `1024` | 每台容器分配的内存（MB） |
| `--disk` | int | `10` | 每台容器分配的磁盘配额（GB） |
| `--ssh-base-port` | int | `2201` | 容器 SSH 端口映射起始端口号 |
| `--prepare-3xui` | bool | `true` | 首个容器预装 3X-UI 基础栈并透传 80/443 |
| `--output-dir` | string | `/root/02project/01LXD_vps_info/<ip>` | 生成凭据档案与结果数据的存储目录 |
| `--dry-run` | flag | `false` | 仅验证参数并预览规划，不进行远程变更 |

---

## 五、智能体（AI Agent）跨层运维运行手册

1. **宿主机视角调度**：
   - 收集 VPS IP 与 root 凭据后调用 `scripts/vps_lxc.py` 自动化建构容器底座与全局 Proxy 设备，严禁手工乱改宿主机 iptables。
2. **凭据与架构检索**：
   - 大模型/Agent 在宿主机上读取 `/root/02project/01LXD_vps_info/<IP>/` 目录即可获取全套凭据表、端口转发矩阵与 Cloudflare 回源指引；
   - 容器内部保持完全纯净，租户体验与真实独立 VPS 完全一致。

---

## 六、交付物与归档清单

所有集群信息统一保存在宿主机 `/root/02project/01LXD_vps_info/<IP>/`：

- `credentials_and_ports.md`：每台容器的 SSH 命令、内网 IP、高强度随机密码与完整端口映射表格。
- `cloudflare_origin_rules.md`：Cloudflare 免费 CDN 免端口回源配置全指南。
- `README.md`：集群全局导航总览与快速连接命令。
- `vps_lxc_<IP>_summary.txt`：纯文本连接速查表格。
- `result.json`：机器可读的结构化配置数据，方便自动化流水线集成。

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

- 新宿主机首选 **Ubuntu 24.04 LTS**（支持 6.8+ 内核与完整 BBR/Socket 激活）或 **Debian 12**（轻量稳定）。必须是 KVM 或物理机，不支持 OpenVZ/LXC/Docker 类 VPS。
- LXD 推荐 **5.21 LTS**，内核 5.15 以上且包含 BBR。
- 4G 内存 KVM 实测（LXD + 2 个容器）：Debian 12 约 572 MB，Ubuntu 24.04 minimal 约 583 MB，两者内存开销差距仅约 10 MB。
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
