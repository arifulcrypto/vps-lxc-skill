

## 系统与机器推荐

- 系统：宿主机推荐 **Ubuntu 24.04 LTS**，也可用 Ubuntu 22.04、Debian 12/13（Debian 宿主机尚未实测）。必须是 KVM 或物理机，不支持 OpenVZ/LXC/Docker 类 VPS。
- LXD：推荐 **5.21 LTS**，内核 5.15 以上。
- 配置：1 个容器 1 核 1G 内存 10G 硬盘；2 个容器 2 核 2G 20G；4 个容器 2-4 核 4G 30G，并配置 1-2G Swap。
- 实测：容器空闲约 100 MB 内存，Ubuntu 与 Debian 镜像基本相同，保持默认镜像即可。
- 客户端：Mihomo 需要 **v1.19.9 或更新版本**。
- 检查：运行 `--check-host` 可在不做任何修改的情况下评估机器。详见 [Host Requirements](../docs/host-requirements.md)。

## 重启规则

重启后无需人工处理。每次部署都会安装开机自检。

- `vps-lxc-bootcheck.timer` 在开机 30 秒后运行：等待 LXD，启动列出的容器和停止的服务，为每个容器重新应用 BBR，测试 SSH 转发（必要时重启容器一次），重试约 4 分钟后把结果写入 `/var/lib/vps-lxc/boot-status`。
- 重启后等待 3 分钟再查看状态。`OK` 表示无需操作；`FAILED` 会列出异常项，查看 `/var/log/vps-lxc-bootcheck.log`，修复后运行 `systemctl start vps-lxc-bootcheck.service`。
- 不要把再次重启作为第一步，也不要手动修改转发规则。
- 已有集群运行 `--install-boot-check` 即可添加自检，不会改动其他内容。
- 重启后 `iptables -t nat -S` 为空但端口正常时，是 LXD 切换到了 nftables，无需处理。
