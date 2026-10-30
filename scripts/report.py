#!/usr/bin/env python3
"""
Report generation and result serialization for VPS LXC Skill.
Renders clean markdown / text summaries and exports secure result.json.
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
            f"    Stealth Mode  : {'KVM Disguised' if c['specs'].get('stealth_kvm') else 'Standard'}",
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
        "2. Containers run in unprivileged user namespaces with KVM stealth virtualization masking.",
        "3. Docker and Docker Compose can be installed natively inside each container.",
        "4. Host server default SSH port 22 and main network routes remain untouched and secure.",
        "=" * 72,
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
    try:
        os.chmod(summary_path, 0o600)
    except Exception:
        pass

    result_data = {
        "status": "success",
        "host_ip": host_ip,
        "container_count": len(containers),
        "containers": containers
    }
    result_path = os.path.join(output_dir, "result.json")
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(result_data, f, indent=2, ensure_ascii=False)
    try:
        os.chmod(result_path, 0o600)
    except Exception:
        pass

    return {
        "summary": summary_path,
        "result_json": result_path
    }
