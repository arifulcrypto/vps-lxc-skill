# VPS LXC 容器自动化部署 Skill

> Linux VPS 高密度 LXC 容器自动拆分与管理引擎。
> 快速部署相互隔离的 Linux 容器（默认 2 个，2核CPU、1GB内存、10GB硬盘，或支持宿主机资源智能平分），具备独立 SSH 端口转发、强随机 root 密码、干净独立的环境规范、以及 3X-UI / Docker 嵌套支持。

[English](../README.md) | [中文说明](./README_zh.md)

---

## 核心功能

- **自动化宿主机环境就绪**：自动检测并安装配置 LXD 守护进程，配置高效的 `dir` 瘦分配存储池，初始化 `lxdbr0` 隔离网桥（集成 IPv4 / IPv6 NAT）。
- **多种资源分配模式**：
  - **默认固定规格**：2核 CPU、1024MB 内存硬顶、10GB 磁盘空间配额。
  - **宿主机资源智能平分（`--auto-split`）**：自动探测宿主机实际 CPU、RAM 和磁盘，预留宿主机系统底座开销后，将剩余算力与存储平均分配给各容器。
- **高兼容性 SSH 连接体系**：
  - 支持非标 SSH 端口（`--ssh-port 2222`）。
  - 支持 SSH 密钥免密认证（`--ssh-key ~/.ssh/id_rsa`，使用密钥时无需依赖 `sshpass`）。
  - 支持标准密码认证（`--ssh-pass` 或环境变量 `VPS_SSH_PASS`）。
- **干净独立的环境规范（真实透明）**：
  - **真实环境输出**：不伪造虚拟化二进制，不篡改检测命令，环境干净透明。
  - 统一规范的主机名（`vps`）与纯净标准欢迎横幅（不携带 `01`/`02` 编号后缀与硬件限额信息）。
  - 每个容器使用密码学级随机算法自动生成独立高强度 root 密码，**绝不与宿主机相同**。
- **首个容器 3X-UI 极速就绪（`--prepare-3xui`，默认开启）**：
  - 第一个容器（`vps-01`）自动预装部署 [vps-deploy-skill](https://github.com/arifulcrypto/vps-deploy-skill) 所需的完整基础组件（`curl, socat, cron, openssl, python3, iptables` 等）。
  - 自动向容器 1 透传公网 `80` 和 `443` 端口，方便直接执行 3X-UI / REALITY 代理部署。
- **独立 SSH 端口透传**：
  - 自动通过 LXD 内置 proxy 设备映射宿主机高位端口（如 `2201`、`2202` 等）至容器内部的 22 端口。
  - **绝对不动宿主机默认 22 端口，避免 VPS 失联**。
- **Docker 容器嵌套**：
  - 预开启 `security.nesting=true`，容器内可直接原生安装并运行 Docker 与 Docker Compose。

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

# 5. 自定义容器数量、名称与起始端口
python3 scripts/vps_lxc.py --ip 198.51.100.1 --ssh-pass 'your_vps_password' \
  --count 2 --names vps-alice,vps-bob --ssh-base-port 2210

# 6. 在宿主机本地直接执行
python3 scripts/vps_lxc.py --local --count 2
```

---

## 部署档案与产物说明

部署完成后，脚本将在 `./output/<IP>/` 下生成两份档案：
1. `vps_lxc_<IP>_summary.txt`：清晰整洁的终端连接信息、内网 IP、映射端口及各容器专属 root 密码。
2. `result.json`：供第三方程序或自动化管道调用的结构化 JSON 数据。
