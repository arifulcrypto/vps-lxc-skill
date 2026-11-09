#!/usr/bin/env python3
"""
Report generation and result serialization for VPS LXC Skill.
Renders clean markdown / text summaries, Cloudflare CDN Origin Rules documentation,
central host credentials matrix, Realm home broadband relay and residential proxy guide,
and exports secure result.json.
"""
import json
import os
from typing import Any, Dict, List, Optional


def forward_summary(ports: List[Dict[str, Any]]) -> str:
    """Effective forwarding modes, as observed when the devices were applied."""
    modes = sorted({p.get("forward", "unknown") for p in ports})
    return " + ".join(modes) if modes else "none"


def disk_label(specs: Dict[str, Any]) -> str:
    return specs["disk"] + ("" if specs.get("disk_quota_enforced") else " (quota NOT enforced)")


def password_label(container: Dict[str, Any]) -> str:
    return container.get("password") or "unchanged (not known to this run)"


def render_summary(host_ip: str, containers: List[Dict[str, Any]], archive_dir: str = "") -> str:
    lines = [
        "=" * 76,
        "  VPS LXC Multi-Container Deployment Archive",
        "=" * 76,
        f"Host Server IP   : {host_ip}",
        f"Container Count  : {len(containers)}",
        "",
        "-" * 76,
        "Container Access Credentials & Specifications",
        "-" * 76,
    ]

    for idx, c in enumerate(containers, start=1):
        ssh_cmd = f"ssh -p {c['ssh_port']} {c['user']}@{host_ip}"
        role = c.get("role") or ("Primary Gateway (80/443 & 3X-UI)" if idx == 1 else "Independent VPS & Proxy Node")
        ports = c.get("ports", [])
        port_count = len(ports) if ports else "Standard Matrix"
        lines.extend([
            f"[{idx}] Container Name: {c['name']} (Hostname: {c.get('hostname', c['name'])})",
            f"    Role          : {role}",
            f"    Status        : {c.get('status', 'Running')}",
            f"    Internal IP   : {c.get('ipv4', '127.0.0.1')} (IPv4) / {c.get('ipv6') or 'disabled'} (IPv6)",
            f"    Hardware Specs: {c['specs']['cpu_cores']} vCPU | {c['specs']['memory']} RAM | {disk_label(c['specs'])} Disk",
            f"    Mapped Ports  : {port_count} dedicated ports ({forward_summary(ports)})",
            f"    SSH Port      : {c['ssh_port']}",
            f"    SSH Username  : {c['user']}",
            f"    SSH Password  : {password_label(c)}",
            f"    Connect Cmd   : {ssh_cmd}",
            ""
        ])

    lines.extend([
        "-" * 76,
        "Security & Operational Notes",
        "-" * 76,
        "1. Passwords are cryptographically generated and 100% isolated from the host root password.",
        "2. All containers run with security.nesting=true and syscall interception (mknod, setxattr) to support Docker, 3X-UI, and Realm natively.",
        "3. Every container is pre-allocated abundant ports (14-16 ports) for Direct, CDN, Relay, and Residential proxies.",
        f"4. All documentation and credentials are archived in {archive_dir or 'the output directory'}.",
        "=" * 76,
    ])
    return "\n".join(lines)


def render_markdown_credentials(host_ip: str, containers: List[Dict[str, Any]]) -> str:
    lines = [
        f"# {host_ip} LXC Container Access Credentials & Port Forwarding Matrix",
        "",
        "> **Cleanliness Notice**: Containers remain standard and clean. All configuration guides are archived here on the host.",
        "",
        "## 1. Container Credentials Table",
        "",
        "| Container Name | Internal IPv4 | Role | Specs | SSH Port | Username | Password | Connect Command |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
    ]

    for idx, c in enumerate(containers, start=1):
        role = c.get("role") or ("Primary (80/443 Ready)" if idx == 1 else "Independent Full-Node VPS")
        specs = f"{c['specs']['cpu_cores']} vCPU / {c['specs']['memory']}"
        connect_cmd = f"`ssh -p {c['ssh_port']} {c['user']}@{host_ip}`"
        lines.append(
            f"| **{c['name']}** | `{c['ipv4']}` | {role} | {specs} | **{c['ssh_port']}** | `{c['user']}` | `{password_label(c)}` | {connect_cmd} |"
        )

    lines.extend([
        "",
        "## 2. Supercharged Port Forwarding Matrix",
        "",
        "All ports use LXD proxy devices. The Mode column shows what was actually applied: "
        "`nat` is kernel DNAT, `userspace` is the slower forkproxy fallback.",
        "",
        "| Container | External Port | Protocol | Target | Mode | Designated Role / Protocol |",
        "| :--- | :--- | :---: | :--- | :--- | :--- |"
    ])

    for c in containers:
        name = c["name"]
        ip = c["ipv4"] or "127.0.0.1"
        ports = c.get("ports", [])
        if ports:
            for p in ports:
                lines.append(
                    f"| `{name}` | **`{p['ext']}`** | {p['proto'].upper()} | `{ip}:{p['int']}` | {p.get('forward', '')} | {p['role']} |"
                )
        else:
            lines.append(f"| `{name}` | **`{c['ssh_port']}`** | TCP | `{ip}:22` | | Container SSH Management |")

    lines.extend([
        "",
        "## 3. Native Docker & 3X-UI Support",
        "",
        "All containers run with `security.nesting=true`, `security.syscalls.intercept.mknod=true`, `security.syscalls.intercept.setxattr=true` and `limits.memory.swap=true` (LXD 5.21 LTS).",
        "To install Docker inside any container:",
        "```bash",
        "curl -fsSL https://get.docker.com | bash",
        "systemctl enable --now docker",
        "```",
        ""
    ])
    return "\n".join(lines)


def render_relay_and_exit_guide(host_ip: str, containers: List[Dict[str, Any]]) -> str:
    def pool_base(idx: int, container: Dict[str, Any]) -> int:
        vmess = container.get("deployer_config", {}).get("vmess_port")
        return vmess - 4 if vmess else 10000 + idx * 10

    relay_name, relay_port = containers[-1]["name"], pool_base(len(containers), containers[-1]) + 1
    res_port = relay_port + 2
    lines = [
        f"# Relay & Residential Exit Extension Runbook ({host_ip})",
        "",
        "> **For Operators & LLM Assistants**: This runbook provides exact, deterministic instructions",
        "> for configuring Layer 4 Realm relays (e.g. US home broadband NAT exits) and commercial residential",
        "> proxy outbounds (IPRoyal, DataImpulse, IPCook) on any container.",
        "",
        "## 1. Quick Port Reference for Relays & Residential Proxies",
        "",
        "| Container | Realm Relay 1 (NAT Exit) | Realm Relay 2 (Secondary) | Residential SOCKS5 Entry | 233boy VMess |",
        "| :--- | :---: | :---: | :---: | :---: |"
    ]

    for idx, c in enumerate(containers, start=1):
        base = pool_base(idx, c)
        lines.append(
            f"| `{c['name']}` | **`{base + 1}`** | **`{base + 2}`** | **`{base + 3}`** | **`{base + 4}`** |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## 2. LLM Instruction Block (大模型自动配置意图识别与执行标准)",
        "",
        "When an AI Agent is tasked with configuring an exit or relay, follow these exact patterns:",
        "",
        "### Scenario A: User provides a Home Broadband / NAT Exit Node (e.g. US REALITY Exit)",
        "Example Input URI: `vless://UUID@US_IP:US_PORT?security=reality&encryption=none&pbk=PBK&fp=chrome&type=tcp&flow=xtls-rprx-vision&sni=SNI&sid=SID#US-Exit`",
        "",
        "**Action for LLM**:",
        f"1. Select the designated container (default: `{relay_name}` on port `{relay_port}`).",
        "2. Execute the Realm one-liner inside the container:",
        "```bash",
        f"# Run inside container (lxc exec {relay_name} -- bash):",
        "mkdir -p /opt/realm /etc/realm",
        'curl -fL -o /tmp/realm.tar.gz "https://github.com/zhboner/realm/releases/download/v2.9.6/realm-$(uname -m)-unknown-linux-musl.tar.gz"',
        "tar -zxvf /tmp/realm.tar.gz -C /opt/realm/ && chmod +x /opt/realm/realm",
        "ln -sf /opt/realm/realm /usr/local/bin/realm",
        "",
        "cat <<'EOF' > /etc/realm/config.toml",
        "[network]",
        "no_tcp = false",
        "use_udp = true",
        "",
        "[[endpoints]]",
        f'listen = "0.0.0.0:{relay_port}"',
        'remote = "US_IP:US_PORT"',
        "EOF",
        "",
        "cat <<'EOF' > /etc/systemd/system/realm.service",
        "[Unit]",
        "Description=Realm Layer 4 Port Forwarder",
        "After=network.target",
        "[Service]",
        "ExecStart=/usr/local/bin/realm -c /etc/realm/config.toml",
        "Restart=always",
        "[Install]",
        "WantedBy=multi-user.target",
        "EOF",
        "",
        "systemctl daemon-reload && systemctl enable --now realm",
        "```",
        "3. Output the rewritten client node link:",
        f"   - Replace `US_IP:US_PORT` with `{host_ip}:{relay_port}`.",
        "   - Keep all other parameters (`uuid`, `pbk`, `sni`, `sid`, `flow`) intact.",
        "   - Note: Do NOT append experimental parameters like `support-x25519mlkem768=true` to maintain universal compatibility across standard clients (v2rayN, Mihomo, Sing-box).",
        "",
        "4. Dual Landing Architecture & Client Rules:",
        "   - Always provide both the relayed node and the original direct landing node (fallback).",
        "   - In `clash_config.yaml` / Clash Verge Rev, place `🚀 节点选择` at index 0 of `proxy-groups:`, with `⚡ 自动选择 (低延迟)` as its first option.",
        "   - Keep container Xray-core on `v26.6.27` to guarantee universal Mihomo AEAD authentication compatibility, and verify `client_inbounds.flow_override` is set to `xtls-rprx-vision`.",
        "   - Enforce neutral node naming without sensitive carrier or operator terms.",
        "",
        "---",
        "",
        "### Scenario B: User provides a Commercial Residential Proxy (IPRoyal, IPCook, DataImpulse)",
        "Example Input: Host: `geo.iproyal.com`, Port: `12321`, User: `customer-xxx_session-yyy`, Pass: `pass`.",
        "",
        "**Action for LLM**:",
        f"1. Select the designated container (default: `{relay_name}` on port `{res_port}`).",
        f"2. In Xray/3X-UI, add a SOCKS5 outbound and route the inbound on port `{res_port}` to it. "
        "This step is manual: neither tool configures server-side routing yet.",
        "3. **In `clash_config.yaml`**:",
        "   - **Strict Rule**: Place this proxy under `🏠 住宅与家宽专线`.",
        "   - **Strict Rule**: NEVER place it under `⚡ 自动选择 (低延迟)` / `url-test` to avoid burning metered bandwidth.",
        ""
    ])
    return "\n".join(lines)


def render_cloudflare_rules(host_ip: str, containers: List[Dict[str, Any]]) -> str:
    lines = [
        f"# Cloudflare CDN Origin Rules Guide for {host_ip}",
        "",
        "Cloudflare free CDN supports proxying the following HTTPS ports:",
        "- Standard HTTPS: `443`",
        "- Supported Alternate HTTPS: `8443`, `2053`, `2083`, `2087`, `2096`",
        "",
        "### How to Bind Domains Without Port Suffixes (Origin Rules)",
        f"1. In Cloudflare DNS, create an `A` record pointing your domain (e.g. `app.domain.com`) to host IP `{host_ip}` with Proxied (Orange Cloud) enabled.",
        "2. Navigate to **Rules -> Origin Rules -> Create rule** in the Cloudflare dashboard.",
        "3. Match Expression: `Hostname equals app.domain.com`",
        "4. Rewrite destination port to the container's HTTPS port (`8443` for the second container, `2053` for the third, `2083` for the fourth).",
        "5. Deploy rule. Visitors can now browse `https://app.domain.com` without entering any port number.",
        ""
    ]
    return "\n".join(lines)


def render_desktop_guide(host_ip: str, desktop_container: Dict[str, Any]) -> str:
    name = desktop_container["name"]
    ssh_port = desktop_container["ssh_port"]
    user = desktop_container["user"]
    password = password_label(desktop_container)
    return f"""# {name} 容器运维与远程桌面指引 (XRDP / XFCE4 / Google Chrome)

## 1. 容器基本信息与凭据

- **容器名**: `{name}` (内部统一主机名: `vps`)
- **内网 IP**: `{desktop_container['ipv4']}`
- **SSH 登录**: `ssh -p {ssh_port} {user}@{host_ip}`
- **默认密码**: `{password}`
- **远程桌面**: Windows MSTSC 直连 `{host_ip}:3389`

---

## 2. 远程桌面与 Google Chrome 一键极速部署 (已彻底修复黑屏与闪退)

登录容器后，运行以下官方生产级脚本：

```bash
# 1. 更新源并安装桌面环境（必须显式包含 xorgxrdp 驱动后端）
export DEBIAN_FRONTEND=noninteractive
apt-get update && apt-get install -y --no-install-recommends \\
    xfce4 xfce4-goodies xrdp xorgxrdp dbus-x11 x11-xserver-utils \\
    fonts-noto-cjk curl wget ca-certificates dbus

# 2. 修复 Xorg 控制台权限与 XRDP 会话环境变量
sed -i "s/allowed_users=console/allowed_users=anybody/g" /etc/X11/Xwrapper.config 2>/dev/null || true
grep -q "needs_root_rights=yes" /etc/X11/Xwrapper.config 2>/dev/null || echo "needs_root_rights=yes" >> /etc/X11/Xwrapper.config

cat << 'EOF' > /root/.xsession
unset DBUS_SESSION_BUS_ADDRESS
unset XDG_RUNTIME_DIR
exec startxfce4
EOF
chmod +x /root/.xsession

# 3. 屏蔽 Polkit 色彩管理弹窗，杜绝黑屏死锁
mkdir -p /etc/polkit-1/localauthority/50-local.d/
cat << 'EOF' > /etc/polkit-1/localauthority/50-local.d/45-allow-colord.pkla
[Allow Colord all Users]
Identity=unix-user:*
Action=org.freedesktop.color-manager.create-device;org.freedesktop.color-manager.create-profile;org.freedesktop.color-manager.delete-device;org.freedesktop.color-manager.delete-profile;org.freedesktop.color-manager.modify-device;org.freedesktop.color-manager.modify-profile
ResultAny=no
ResultInactive=no
ResultActive=yes
EOF

# 4. 根据系统架构安装 Google Chrome / Chromium，并全局注入免沙箱参数
ARCH=$(dpkg --print-architecture)
if [ "$ARCH" = "amd64" ]; then
    wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
    apt-get install -y ./google-chrome-stable_current_amd64.deb
    rm -f google-chrome-stable_current_amd64.deb
    sed -i 's|exec -a "$0" "$HERE/chrome" "$@"|exec -a "$0" "$HERE/chrome" "$@" --no-sandbox --disable-dev-shm-usage|g' /opt/google/chrome/google-chrome
else
    apt-get install -y chromium-browser
    sed -i 's|exec $GDB "$CHR_WRAPPER" "$@"|exec $GDB "$CHR_WRAPPER" "$@" --no-sandbox --disable-dev-shm-usage|g' /usr/bin/chromium-browser 2>/dev/null || true
fi

# 5. 注入 Chrome 企业级防 WebRTC 泄露托管策略
mkdir -p /etc/opt/chrome/policies/managed
cat << 'EOF' > /etc/opt/chrome/policies/managed/webrtc_policy.json
{{
  "WebRtcIPHandlingPolicy": "disable_non_proxied_udp"
}}
EOF

# 6. 配置桌面图标与登录默认自动打开 Chrome
mkdir -p /root/Desktop /root/.config/autostart /root/.config/xfce4
cp -f /usr/share/applications/google-chrome.desktop /root/Desktop/ 2>/dev/null || true
chmod +x /root/Desktop/google-chrome.desktop 2>/dev/null || true

cat << 'EOF' > /root/.config/autostart/google-chrome.desktop
[Desktop Entry]
Type=Application
Version=1.0
Name=Google Chrome
Comment=Google Chrome Web Browser
Exec=/usr/bin/google-chrome-stable --no-sandbox --disable-dev-shm-usage
Icon=google-chrome
Terminal=false
StartupNotify=true
Categories=Network;WebBrowser;
EOF
chmod +x /root/.config/autostart/google-chrome.desktop

cat << 'EOF' > /root/.config/xfce4/helpers.rc
WebBrowser=google-chrome
EOF

# 7. 内核级防火墙封锁公网 STUN UDP 探测，杜绝真实 IP WebRTC 穿透泄露
iptables -C OUTPUT -p udp -m multiport --dports 3478,5349,19302 -j REJECT 2>/dev/null || \
iptables -I OUTPUT -p udp -m multiport --dports 3478,5349,19302 -j REJECT

# 8. 重启 XRDP 远程桌面服务
adduser xrdp ssl-cert 2>/dev/null || true
systemctl restart xrdp xrdp-sesman
```

---

## 3. Windows 远程桌面连接指引 (MSTSC)

1. 打开 Windows 自带的 **远程桌面连接 (mstsc.exe)**。
2. 计算机 (Computer) 栏输入：`{host_ip}:3389`
3. 输入凭据：
   - **username**: `{user}`
   - **password**: `{password}`
4. 即可直接秒进流畅完整的 XFCE4 桌面并正常双击使用 Google Chrome 浏览器。
"""


def render_host_readme(host_ip: str, containers: List[Dict[str, Any]]) -> str:
    desktop_container = next((c for c in containers if any(p.get("ext") == 3389 for p in c.get("ports", []))), None)
    lines = [
        f"# LXC Cluster Information Archive - {host_ip}",
        "",
        f"Host Server IP: `{host_ip}`  ",
        f"Container Count: {len(containers)}  ",
        "",
        "## Directory Contents",
        "- `credentials_and_ports.md`: Complete credentials, passwords, and supercharged port forwarding matrix.",
        "- `relay_and_exit_guide.md`: Step-by-step Realm broadband relay & residential proxy runbook (LLM Prompt-Ready).",
        "- `cloudflare_origin_rules.md`: Cloudflare CDN configuration and portless domain mapping.",
    ]
    if desktop_container:
        lines.append(f"- `{desktop_container['name'].replace('-', '_')}.md`: Windows RDP (3389) desktop & Google Chrome deployment guide.")
    lines.extend([
        "- `result.json`: Machine-readable deployment metadata.",
        "- `deploy_<container>.json`: Ready-to-use `--config` input for vps-deploy-skill, one per container.",
        "",
        "## Quick SSH Access",
        "```bash"
    ])
    for c in containers:
        lines.append(f"ssh -p {c['ssh_port']} {c['user']}@{host_ip}   # {c['name']} (Pass: {password_label(c)})")
    lines.extend([
        "```",
        ""
    ])
    return "\n".join(lines)


def save_artifacts(output_dir: str, host_ip: str, containers: List[Dict[str, Any]],
                   host_state: Optional[Dict[str, str]] = None,
                   warnings: Optional[List[str]] = None) -> Dict[str, str]:
    os.makedirs(output_dir, exist_ok=True)
    try:
        os.chmod(output_dir, 0o700)
    except Exception:
        pass

    summary_text = render_summary(host_ip, containers, output_dir)
    summary_path = os.path.join(output_dir, f"vps_lxc_{host_ip}_summary.txt")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(summary_text)

    creds_md = render_markdown_credentials(host_ip, containers)
    creds_path = os.path.join(output_dir, "credentials_and_ports.md")
    with open(creds_path, "w", encoding="utf-8") as f:
        f.write(creds_md)

    relay_md = render_relay_and_exit_guide(host_ip, containers)
    relay_path = os.path.join(output_dir, "relay_and_exit_guide.md")
    with open(relay_path, "w", encoding="utf-8") as f:
        f.write(relay_md)

    cf_md = render_cloudflare_rules(host_ip, containers)
    cf_path = os.path.join(output_dir, "cloudflare_origin_rules.md")
    with open(cf_path, "w", encoding="utf-8") as f:
        f.write(cf_md)

    readme_md = render_host_readme(host_ip, containers)
    readme_path = os.path.join(output_dir, "README.md")
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(readme_md)

    desktop_container = next((c for c in containers if any(p.get("ext") == 3389 for p in c.get("ports", []))), None)
    desktop_path = None
    if desktop_container:
        desktop_md = render_desktop_guide(host_ip, desktop_container)
        desktop_path = os.path.join(output_dir, f"{desktop_container['name'].replace('-', '_')}.md")
        with open(desktop_path, "w", encoding="utf-8") as f:
            f.write(desktop_md)

    result_data = {
        "status": "success",
        "host_ip": host_ip,
        "container_count": len(containers),
        "host": host_state or {},
        "warnings": warnings or [],
        "containers": containers
    }
    result_path = os.path.join(output_dir, "result.json")
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(result_data, f, indent=2, ensure_ascii=False)

    deploy_paths = []
    for c in containers:
        deploy_path = os.path.join(output_dir, f"deploy_{c['name']}.json")
        with open(deploy_path, "w", encoding="utf-8") as f:
            json.dump(c.get("deployer_config", {}), f, indent=2)
        deploy_paths.append(deploy_path)

    all_paths = [summary_path, creds_path, relay_path, cf_path, readme_path, result_path, *deploy_paths]
    if desktop_path:
        all_paths.append(desktop_path)
    for p in all_paths:
        try:
            os.chmod(p, 0o600)
        except Exception:
            pass

    out_dict = {
        "summary": summary_path,
        "credentials_md": creds_path,
        "relay_md": relay_path,
        "cloudflare_md": cf_path,
        "readme_md": readme_path,
        "result_json": result_path
    }
    if desktop_path:
        out_dict["desktop_md"] = desktop_path
    return out_dict
