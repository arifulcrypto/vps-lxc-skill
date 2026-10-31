#!/usr/bin/env python3
"""
Report generation and result serialization for VPS LXC Skill.
Renders clean markdown / text summaries, Cloudflare CDN Origin Rules documentation,
central host credentials matrix, and exports secure result.json.
"""
import json
import os
from typing import Any, Dict, List


def render_summary(host_ip: str, containers: List[Dict[str, Any]]) -> str:
    lines = [
        "=" * 72,
        "  VPS LXC Multi-Container Deployment Archive",
        "=" * 72,
        f"Host Server IP   : {host_ip}",
        f"Container Count  : {len(containers)}",
        "",
        "-" * 72,
        "Container Access Credentials & Specifications",
        "-" * 72,
    ]

    for idx, c in enumerate(containers, start=1):
        ssh_cmd = f"ssh -p {c['ssh_port']} {c['user']}@{host_ip}"
        role = "Primary Node (3X-UI & Ports 80/443 Ready)" if c.get("is_3xui_ready") else "Independent VPS"
        lines.extend([
            f"[{idx}] Container Name: {c['name']} (Hostname: {c.get('hostname', c['name'])})",
            f"    Role          : {role}",
            f"    Status        : {c['status']}",
            f"    Internal IP   : {c['ipv4']} (IPv4) / {c['ipv6']} (IPv6)",
            f"    Hardware Specs: {c['specs']['cpu_cores']} vCPU | {c['specs']['memory']} RAM | {c['specs']['disk']} Disk",
            f"    Isolation     : Unprivileged LXC (security.nesting=true)",
            f"    Docker Support: {'Enabled (security.nesting=true)' if c['specs'].get('docker_nesting') else 'Disabled'}",
            f"    SSH Port      : {c['ssh_port']}",
            f"    SSH Username  : {c['user']}",
            f"    SSH Password  : {c['password']}",
            f"    Connect Cmd   : {ssh_cmd}",
            ""
        ])

    lines.extend([
        "-" * 72,
        "Security & Operational Notes",
        "-" * 72,
        "1. Passwords are cryptographically generated and 100% isolated from the host root password.",
        "2. Containers run in unprivileged user namespaces with complete process and network isolation.",
        "3. Containers remain clean standard Linux installations with ZERO internal guide files.",
        "4. All documentation and credentials are centrally archived under /root/02project/01LXD_vps_info/ on the host.",
        "=" * 72,
    ])
    return "\n".join(lines)


def render_markdown_credentials(host_ip: str, containers: List[Dict[str, Any]]) -> str:
    lines = [
        f"# {host_ip} LXC Container Access Credentials & Port Forwarding Matrix",
        "",
        "> **Cleanliness Notice**: Containers remain standard and clean. All configuration guides are archived here on the host.",
        "",
        "## Container Credentials Table",
        "",
        "| Container Name | Internal IPv4 | Role | Specs | SSH Port | Username | Password | Connect Command |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
    ]

    for c in containers:
        role = "Primary (80/443 Ready)" if c.get("is_3xui_ready") else "Independent Node"
        specs = f"{c['specs']['cpu_cores']} vCPU / {c['specs']['memory']}"
        connect_cmd = f"`ssh -p {c['ssh_port']} {c['user']}@{host_ip}`"
        lines.append(
            f"| **{c['name']}** | `{c['ipv4']}` | {role} | {specs} | **{c['ssh_port']}** | `{c['user']}` | `{c['password']}` | {connect_cmd} |"
        )

    lines.extend([
        "",
        "## Port Forwarding Matrix",
        "",
        "| Container | External Port | Protocol | Target | Description |",
        "| :--- | :--- | :--- | :--- | :--- |"
    ])

    for c in containers:
        name = c["name"]
        lines.append(f"| `{name}` | `{c['ssh_port']}` | TCP | `{c['ipv4']}:22` | Container SSH Management |")
        if c.get("is_3xui_ready"):
            lines.append(f"| `{name}` | `80` | TCP | `{c['ipv4']}:80` | HTTP Web / Acme.sh |")
            lines.append(f"| `{name}` | `443` | TCP | `{c['ipv4']}:443` | HTTPS Standard CDN Direct |")

    lines.extend([
        "",
        "## Docker Support",
        "",
        "All containers run with `security.nesting=true` and support native Docker installation inside the container:",
        "```bash",
        "curl -fsSL https://get.docker.com | bash",
        "```",
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
        "1. In Cloudflare DNS, create an `A` record pointing your domain (e.g. `c2.domain.com`) to host IP `" + host_ip + "` with Proxied (Orange Cloud) enabled.",
        "2. Navigate to **Rules -> Origin Rules -> Create rule** in the Cloudflare dashboard.",
        "3. Match Expression: `Hostname equals c2.domain.com`",
        "4. Rewrite destination port to: the assigned container port (e.g. `8443`, `2053`, or `2083`).",
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
        "- `credentials_and_ports.md`: Complete credentials, passwords, and port forwarding matrix.",
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

    for p in (summary_path, creds_path, cf_path, readme_path, result_path):
        try:
            os.chmod(p, 0o600)
        except Exception:
            pass

    return {
        "summary": summary_path,
        "credentials_md": creds_path,
        "cloudflare_md": cf_path,
        "readme_md": readme_path,
        "result_json": result_path
    }
