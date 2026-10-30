# Gemini / Google Antigravity Skill 指南 (中文)

该 Skill 会通过 [`.agents/skills/vps-lxc-creator/SKILL.md`](../.agents/skills/vps-lxc-creator/SKILL.md) 自动发现并关联到根目录下的 [`SKILL.md`](../SKILL.md)。

## 会话中执行流程
1. 提取目标 VPS 的 `ip`、SSH 凭据及容器自定义需求；
2. 默认创建 2 台独立的 LXC 容器，每台规格为 2核 CPU、1GB 内存、10GB 磁盘、独立强随机 root 密码、开启 Docker 嵌套，SSH 映射端口从 2201 开始递增；
3. 生成配置 JSON，先执行 `python3 scripts/vps_lxc.py --config <file> --dry-run` 向用户展示规划并等待确认；
4. 获得确认后，通过 `run_command` 调用 `python3 scripts/vps_lxc.py --config <file>` 完成部署；
5. 执行完成后读取 `result.json`，呈现各容器的连接方式与独立密码。

默认语言为英文（`en`），用户使用中文时切换为中文。
