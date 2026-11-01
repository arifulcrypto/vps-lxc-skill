#!/usr/bin/env python3
"""
Report generation and result serialization for VPS LXC Skill.
Renders clean markdown / text summaries, Cloudflare CDN Origin Rules documentation,
central host credentials matrix, Realm home broadband relay and residential proxy guide,
and exports secure result.json.
"""
import json
import os
from typing import Any, Dict, List


def render_summary(host_ip: str, containers: List[Dict[str, Any]]) -> str:
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
            f"    Status        : {c['status']}",
            f"    Internal IP   : {c['ipv4']} (IPv4) / {c['ipv6']} (IPv6)",
            f"    Hardware Specs: {c['specs']['cpu_cores']} vCPU | {c['specs']['memory']} RAM | {c['specs']['disk']} Disk",
            f"    Mapped Ports  : {port_count} dedicated ports (Kernel NAT)",
            f"    SSH Port      : {c['ssh_port']}",
            f"    SSH Username  : {c['user']}",
            f"    SSH Password  : {c['password']}",
            f"    Connect Cmd   : {ssh_cmd}",
            ""
        ])

    lines.extend([
        "-" * 76,
        "Security & Operational Notes",
        "-" * 76,
        "1. Passwords are cryptographically generated and 100% isolated from the host root password.",
        "2. All containers run with security.nesting=true and support Docker, 3X-UI, and Realm natively.",
        "3. Every container is pre-allocated abundant ports (14-16 ports) for Direct, CDN, Relay, and Residential proxies.",
        "4. All documentation and credentials are centrally archived under /root/02project/01LXD_vps_info/ on the host.",
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
            f"| **{c['name']}** | `{c['ipv4']}` | {role} | {specs} | **{c['ssh_port']}** | `{c['user']}` | `{c['password']}` | {connect_cmd} |"
        )

    lines.extend([
        "",
        "## 2. Supercharged Port Forwarding Matrix",
        "",
        "All ports are forwarded via LXD native proxy devices with kernel-level `nat=true` DNAT.",
        "",
        "| Container | External Port | Protocol | Target | Designated Role / Protocol |",
        "| :--- | :--- | :---: | :--- | :--- |"
    ] )

    for c in containers:
        name = c["name"]
        ip = c["ipv4"] or "127.0.0.1"
        ports = c.get("ports", [])
        if ports:
            for p in ports:
                lines.append(
                    f"| `{name}` | **`{p['ext']}`** | {p['proto'].upper()} | `{ip}:{p['int']}` | {p['role']} |"
                )
        else:
            # Fallback display if ports not populated
            lines.append(f"| `{name}` | **`{c['ssh_port']}`** | TCP | `{ip}:22` | Container SSH Management |")
            if c.get("is_3xui_ready"):
                lines.append(f"| `{name}` | **`80`** | TCP | `{ip}:80` | HTTP Web / Acme.sh |")
                lines.append(f"| `{name}` | **`443`** | TCP | `{ip}:443` | HTTPS Standard CDN Direct |")

    lines.extend([
        "",
        "## 3. Native Docker & 3X-UI Support",
        "",
        "All containers run with `security.nesting=true` and `limits.memory.swap=true`.",
        "To install Docker inside any container:",
        "```bash",
        "curl -fsSL https://get.docker.com | bash",
        "systemctl enable --now docker",
        "```",
        ""
    ])
    return "\n".join(lines)


def render_relay_and_exit_guide(host_ip: str, containers: List[Dict[str, Any]]) -> str:
    lines = [
        f"# Relay & Residential Exit Extension Runbook ({host_ip})",
        "",
        "> **For Operators & LLM Assistants**: This runbook provides exact, deterministic instructions",
        "> for configuring Layer 4 Realm relays (e.g. US home broadband NAT exits) and commercial residential",
        "> proxy outbounds (IPRoyal, DataImpulse, IPCook) on any container.",
        "",
        "## 1. Quick Port Reference for Relays & Residential Proxies",
        "",
        "| Container | Realm Relay 1 (NAT Exit) | Realm Relay 2 (Secondary) | Residential SOCKS5 Entry | 233boy VMess/Trojan |",
        "| :--- | :---: | :---: | :---: | :---: |"
    ]

    for idx, c in enumerate(containers, start=1):
        base = 10000 + idx * 10
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
        "1. Select the designated container (default: `c3-backup` on port `10031` or `c2-app` on port `10021`).",
        "2. Execute the Realm one-liner inside the container:",
        "```bash",
        "# Run inside container (e.g. lxc exec c3-backup -- bash):",
        "mkdir -p /opt/realm /etc/realm",
        "curl -L -o /tmp/realm.tar.gz https://github.com/zhboner/realm/releases/latest/download/realm-x86_64-unknown-linux-musl.tar.gz",
        "tar -zxvf /tmp/realm.tar.gz -C /opt/realm/ && chmod +x /opt/realm/realm",
        "ln -sf /opt/realm/realm /usr/local/bin/realm",
        "",
        "cat <<'EOF' > /etc/realm/config.toml",
        "[network]",
        "no_tcp = false",
        "use_udp = false",
        "",
        "[[endpoints]]",
        'listen = "0.0.0.0:10031"',
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
        f"   - Replace `US_IP:US_PORT` with `{host_ip}:10031`.",
        "   - Keep all other parameters (`uuid`, `pbk`, `sni`, `sid`, `flow`) intact.",
        "",
        "---",
        "",
        "### Scenario B: User provides a Commercial Residential Proxy (IPRoyal, IPCook, DataImpulse)",
        "Example Input: Host: `geo.iproyal.com`, Port: `12321`, User: `customer-xxx_session-yyy`, Pass: `pass`.",
        "",
        "**Action for LLM**:",
        "1. Select the designated container (default: `c2-app` or `c3-backup` on port `10023` / `10033`).",
        "2. In Xray/3X-UI inbound on port `10023` (VLESS-REALITY or Trojan), attach an outbound route to the SOCKS5 upstream.",
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
        f"1. In Cloudflare DNS, create an `A` record pointing your domain (e.g. `c2.domain.com`) to host IP `{host_ip}` with Proxied (Orange Cloud) enabled.",
        "2. Navigate to **Rules -> Origin Rules -> Create rule** in the Cloudflare dashboard.",
        "3. Match Expression: `Hostname equals c2.domain.com`",
        "4. Rewrite destination port to: the assigned container port (e.g. `8443` for c2, `2053` for c3, or `2083` for c4).",
        "5. Deploy rule. Visitors can now browse `https://c2.domain.com` without entering any port number.",
        ""
    ]
    return "\n".join(lines)


def render_host_readme(host_ip: str, containers: List[Dict[str, Any]]) -> str:
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
        "- `result.json`: Machine-readable deployment metadata.",
        "",
        "## Quick SSH Access",
        "```bash"
    ]
    for c in containers:
        lines.append(f"ssh -p {c['ssh_port']} {c['user']}@{host_ip}   # {c['name']} (Pass: {c['password']})")
    lines.extend([
        "```",
        ""
    ])
    return "\n".join(lines)


def save_artifacts(output_dir: str, host_ip: str, containers: List[Dict[str, Any]]) -> Dict[str, str]:
    os.makedirs(output_dir, exist_ok=True)
    try:
        os.chmod(output_dir, 0o700)
    except Exception:
        pass

    summary_text = render_summary(host_ip, containers)
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

    result_data = {
        "status": "success",
        "host_ip": host_ip,
        "container_count": len(containers),
        "containers": containers
    }
    result_path = os.path.join(output_dir, "result.json")
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(result_data, f, indent=2, ensure_ascii=False)

    for p in (summary_path, creds_path, relay_path, cf_path, readme_path, result_path):
        try:
            os.chmod(p, 0o600)
        except Exception:
            pass

    return {
        "summary": summary_path,
        "credentials_md": creds_path,
        "relay_md": relay_path,
        "cloudflare_md": cf_path,
        "readme_md": readme_path,
        "result_json": result_path
    }
