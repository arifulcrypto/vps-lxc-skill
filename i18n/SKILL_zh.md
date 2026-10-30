---
name: vps-lxc-creator
description: >-
  在 Linux VPS 上通过 SSH 或本地自动化部署并管理高密度隔离的 LXC 容器（默认 2 个容器，2核CPU、1GB内存、
  10GB硬盘、支持宿主机资源智能平分、各容器专属强随机密码、独立 SSH 端口映射，以及 Docker 嵌套容器支持）。
---

# VPS LXC Creator Skill（中文）

英文版 [`SKILL.md`](../SKILL.md) 为准。核心自动化引擎为 `scripts/vps_lxc.py`，智能体应优先调用该脚本，而不是自行拼接零散的远程 shell 命令。

[English](../SKILL.md) | [中文说明](./SKILL_zh.md)

---

## 一、核心定位与特性

- **宿主机自动适配**：自动探测并按需安装配置 snap LXD 服务，配置高效轻量的 `dir` 瘦分配存储池，初始化 `lxdbr0` 隔离网桥（自动开启 IPv4 / IPv6 NAT）。
- **灵活的资源分配模式**：
  - **默认固定规格**：默认每容器分配 2 核 vCPU、`1024MB`（1GB）严格 cgroup 内存限额（禁用 Swap 滥用）、`10GB` 磁盘配额。
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
  - 自动通过 LXD 内置 proxy 设备映射宿主机高位端口（默认 `2201`, `2202`, ...）至容器内部的 `22` 端口。
  - **绝对不动宿主机默认 22 端口与既有网络，保障 VPS 绝不失联**。
- **内置 Docker 嵌套支持**：
  - 预开启 `security.nesting=true`，容器内可直接原生安装并运行 Docker 与 Docker Compose。

---

## 二、输入参数表

| 参数名 | 类型 | 默认值 | 详细说明 |
| :--- | :--- | :--- | :--- |
| `--ip` | string | — | 目标 VPS 的公网 IPv4 地址 |
| `--ssh-port` | int | `22` | 宿主机 SSH 端口 |
| `--ssh-user` | string | `root` | 宿主机 SSH 用户名 |
| `--ssh-pass` | string | — | 宿主机 SSH 密码（也可通过环境变量 `VPS_SSH_PASS` 提供） |
| `--ssh-key` | string | — | SSH 私钥文件路径 |
| `--local` | flag | `false` | 直接在当前宿主机本机执行（无需 SSH） |
| `--count` | int | `2` | 欲创建的 LXC 容器数量 |
| `--names` | string | `vps-01,vps-02` | 自定义容器名称（逗号分隔） |
| `--auto-split` | flag | `false` | 智能平分宿主机内存与磁盘配额 |
| `--cpu` | int | `2` | 每台容器分配的 CPU 核心数 |
| `--memory` | int | `1024` | 每台容器分配的内存（MB） |
| `--disk` | int | `10` | 每台容器分配的磁盘配额（GB） |
| `--ssh-base-port` | int | `2201` | 容器 SSH 端口映射起始端口号 |
| `--prepare-3xui` | bool | `true` | 首个容器预装 3X-UI 基础栈并透传 80/443 |
| `--output-dir` | string | `./output/<ip>`| 生成凭据档案与结果数据的存储目录 |
| `--dry-run` | flag | `false` | 仅验证参数并预览规划，不进行远程变更 |

---

## 三、智能体执行步骤规范

1. **输入收集与校验**：提取目标 `ip` 与 SSH 凭据（端口、密钥或密码），确认是否平分宿主机资源或指定规格。
2. **预览确认**：生成配置或命令行，首先执行 `python3 scripts/vps_lxc.py --config <file> --dry-run` 向用户展示拟创建的容器列表、端口分配与资源限制，获得确认。
3. **正式执行**：调用 `python3 scripts/vps_lxc.py --config <file>` 执行部署。
4. **汇报与交付**：读取生成的 `./output/<ip>/vps_lxc_<ip>_summary.txt` 与 `result.json`，向用户交付每台容器的独立连接方式与生成的独立安全密码。
