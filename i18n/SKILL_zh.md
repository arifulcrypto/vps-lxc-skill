

## 系统选择（实测）

- 新宿主机首选 **Debian 13**（支持到 2030 年 6 月）；服务商只提供 Ubuntu 时用 **Ubuntu 24.04**，最好是 minimal 镜像。
- 4G 内存 KVM 实测（LXD + 2 个容器）：Debian 13 约 565 MB，Ubuntu 24.04 minimal 约 583 MB，Ubuntu 24.04 约 624 MB，Ubuntu 26.04 约 747 MB。Debian 只比 Ubuntu 省约 60 MB，差距很小。
- 月流量限制：`--traffic-limit-gb 1500`，80% 记录警告，90% 限速 50 Mbit/s，98% 限速 5 Mbit/s，新月份自动解除，绝不停止服务。
- 软件版本与官方下载链接见 [Software Versions](../docs/software-versions.md)，运行 `python3 scripts/check_versions.py` 可检查新版本。
