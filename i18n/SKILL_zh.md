

## 系统与机器推荐

- 系统：宿主机推荐 **Ubuntu 24.04 LTS**，也可用 Ubuntu 22.04、Debian 12/13（Debian 宿主机尚未实测）。必须是 KVM 或物理机，不支持 OpenVZ/LXC/Docker 类 VPS。
- LXD：推荐 **5.21 LTS**，内核 5.15 以上。
- 配置：1 个容器 1 核 1G 内存 10G 硬盘；2 个容器 2 核 2G 20G；4 个容器 2-4 核 4G 30G，并配置 1-2G Swap。
- 实测：容器空闲约 100 MB 内存，Ubuntu 与 Debian 镜像基本相同，保持默认镜像即可。
- 客户端：Mihomo 需要 **v1.19.9 或更新版本**。
- 检查：运行 `--check-host` 可在不做任何修改的情况下评估机器。详见 [Host Requirements](../docs/host-requirements.md)。
