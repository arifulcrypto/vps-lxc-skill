#!/usr/bin/env python3
"""
VPS LXC Multi-Container Deployment Automation Engine.
Provisions isolated LXC containers with fair resource sharing / auto-split,
clean environment configuration, distinct random passwords, independent SSH port forwarding,
and 3X-UI pre-requisite integration. Reruns reconcile existing containers.

Usage:
  python3 scripts/vps_lxc.py --ip <IP> --ssh-pass <PASS> [--ssh-port 22] [--auto-split]
  python3 scripts/vps_lxc.py --ip <IP> --ssh-key ~/.ssh/id_rsa
  python3 scripts/vps_lxc.py --config config.json
  python3 scripts/vps_lxc.py --local [--count 2]
"""
import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scripts.provision import DEFAULT_IMAGE, MAX_CONTAINERS, LXCProvisioner, validate_plan  # noqa: E402
from scripts.remote import RemoteError, TargetRunner  # noqa: E402
from scripts.report import render_summary, save_artifacts  # noqa: E402


DEFAULTS: Dict[str, Any] = {
    "ssh_port": 22,
    "ssh_user": "root",
    "cpu": 2,
    "memory": 1024,
    "disk": 10,
    "ssh_base_port": 2201,
    "auto_split": False,
    "prepare_3xui": True,
    "local": False,
    "dry_run": False,
    "rotate_passwords": False,
    "image": DEFAULT_IMAGE,
    "storage_driver": "dir",
}


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="VPS LXC Multi-Container Deployment Automation Engine"
    )
    parser.add_argument("--config", help="Path to JSON configuration file")
    parser.add_argument("--ip", help="Target VPS public IPv4 address")
    parser.add_argument("--ssh-port", type=int, help="Host SSH port (default: 22)")
    parser.add_argument("--ssh-user", help="Host SSH user (default: root)")
    parser.add_argument("--ssh-pass", help="Host SSH password (or VPS_SSH_PASS env var)")
    parser.add_argument("--ssh-key", help="Path to SSH private key file")
    parser.add_argument("--local", action="store_true", default=None, help="Run directly on local host")
    parser.add_argument("--count", type=int, help=f"Number of containers, 1-{MAX_CONTAINERS} (default: 2)")
    parser.add_argument("--names", help="Comma-separated container names (default: vps-01,vps-02)")
    parser.add_argument("--auto-split", action="store_true", default=None,
                        help="Auto-detect host CPU/RAM/Disk and split resources fairly between containers")
    parser.add_argument("--cpu", type=int, help="CPU cores limit per container (default: 2)")
    parser.add_argument("--memory", type=int, help="Memory limit in MB (default: 1024)")
    parser.add_argument("--disk", type=int, help="Disk quota in GB (default: 10)")
    parser.add_argument("--ssh-base-port", type=int, help="Base port for container SSH (default: 2201)")
    parser.add_argument("--listen-ip", help="Host IPv4 address for port forwards (default: auto-detected)")
    parser.add_argument("--image", help=f"Container image (default: {DEFAULT_IMAGE})")
    parser.add_argument("--storage-driver", choices=["dir", "btrfs", "zfs", "lvm"],
                        help="Driver when the storage pool has to be created (default: dir)")
    parser.add_argument("--rotate-passwords", action="store_true", default=None,
                        help="Generate new root passwords for existing containers")
    parser.add_argument("--prepare-3xui", dest="prepare_3xui", action=argparse.BooleanOptionalAction, default=None,
                        help="Pre-install 3X-UI stack and forward 80/443 on first container (default: on)")
    parser.add_argument("--output-dir", help="Directory to save summary and credentials")
    parser.add_argument("--dry-run", action="store_true", default=None, help="Validate plan without making remote changes")
    return parser.parse_args(argv)


def load_config(args: argparse.Namespace) -> Dict[str, Any]:
    """Precedence: command line, then config file, then defaults."""
    cfg: Dict[str, Any] = {}
    if args.config:
        with open(args.config, "r", encoding="utf-8") as f:
            cfg = json.load(f)

    for k, v in vars(args).items():
        if k != "config" and v is not None:
            cfg[k] = v

    if not cfg.get("ssh_pass") and os.environ.get("VPS_SSH_PASS"):
        cfg["ssh_pass"] = os.environ["VPS_SSH_PASS"]

    for key, value in DEFAULTS.items():
        if cfg.get(key) in (None, ""):
            cfg[key] = value

    host_id = cfg.get("ip") or "localhost"
    default_output = f"/root/02project/01LXD_vps_info/{host_id}" if os.path.exists("/root/02project") else f"./output/{host_id}"
    cfg.setdefault("output_dir", default_output)
    return cfg


def known_passwords(output_dir: str) -> Dict[str, str]:
    """Passwords from an earlier run, for containers created before they were stored in LXD."""
    try:
        with open(os.path.join(output_dir, "result.json"), "r", encoding="utf-8") as f:
            return {c["name"]: c["password"] for c in json.load(f).get("containers", []) if c.get("password")}
    except (OSError, ValueError, KeyError):
        return {}


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    cfg = load_config(args)

    is_local = cfg.get("local", False)
    ip = cfg.get("ip")

    if not is_local and not ip:
        print("[-] Error: Either --ip or --local must be specified.", file=sys.stderr)
        return 1

    try:
        plan = validate_plan(cfg)
    except (RemoteError, TypeError, ValueError) as e:
        print(f"[-] Invalid configuration: {e}", file=sys.stderr)
        return 1

    host_desc = "Local System" if is_local else f"{cfg['ssh_user']}@{ip}:{cfg['ssh_port']}"
    print(f"[*] Target Host: {host_desc}")

    container_names = plan["names"]
    count = plan["count"]
    ports = plan["ssh_ports"]

    if cfg.get("dry_run"):
        print("[!] DRY-RUN plan preview (no network calls):")
        for idx, name in enumerate(container_names):
            p = ports[idx]
            role = "Primary (3X-UI / Web Ready with ports 80/443)" if (idx == 0 and cfg["prepare_3xui"]) else "General Purpose VPS"
            print(f"    - Container: {name} (Role: {role})")
            print(f"      Specs    : {cfg['cpu']} vCPU | {cfg['memory']}MB RAM | {cfg['disk']}GB Disk")
            print(f"      SSH Port : Host :{p} -> Container :22 (User: root, Unique Random Password)")
            print("      Isolation: Unprivileged LXC (security.nesting=true, root user)")
        print("[!] DRY-RUN completed: inputs and the port plan are valid. Host capacity, existing ports "
              "and LXD state are checked on the real run.")
        return 0

    runner = TargetRunner(
        ip=ip if not is_local else None,
        port=cfg["ssh_port"],
        user=cfg["ssh_user"],
        password=cfg.get("ssh_pass"),
        key_file=cfg.get("ssh_key"),
        is_local=is_local
    )
    provisioner = LXCProvisioner(runner, image=cfg["image"], storage_driver=cfg["storage_driver"])

    try:
        print("[*] Phase 1: Testing SSH connection and preparing LXD environment...")
        runner.test_connection()
        lxd_ver = provisioner.ensure_lxd()
        print(f"[+] LXD daemon ready (version {lxd_ver})")

        host_ip = provisioner.detect_host_ip(cfg.get("listen_ip"))
        planned = [p for defs in plan["matrix"] for p in defs]
        provisioner.preflight_host_ports(planned)

        print("[*] Phase 2: Verifying storage pool, managed bridge and profile...")
        provisioner.ensure_storage_and_network()
        host_state = provisioner.apply_host_network(planned)
        print(f"[+] Host firewall: {host_state.get('HOST_FIREWALL')}; forwarding: {host_state.get('HOST_FORWARD')}; "
              f"congestion control: {host_state.get('HOST_CC')}; UDP buffer: {host_state.get('HOST_RMEM_MAX')}")

        print("[*] Phase 3: Computing resource limits...")
        specs = provisioner.existing_specs(container_names) if cfg.get("auto_split") else None
        specs = specs or provisioner.compute_specs(
            count=count,
            auto_split=cfg.get("auto_split", False),
            manual_cpu=cfg["cpu"],
            manual_ram=cfg["memory"],
            manual_disk=cfg["disk"]
        )
        print(f"[+] Per-container specs: {specs['cpu']} vCPU | {specs['memory_mb']}MB RAM | {specs['disk_gb']}GB Disk")

        print("[*] Phase 4: Checking base image...")
        provisioner.ensure_image()

        print("[*] Phase 5: Deploying LXC containers...")
        deployed = []
        previous = known_passwords(cfg["output_dir"])
        for idx, name in enumerate(container_names):
            port = ports[idx]
            is_first = (idx == 0 and cfg["prepare_3xui"])
            print(f"[*] Deploying container '{name}' on SSH port {port}...")
            c_info = provisioner.deploy_container(
                name=name,
                hostname="vps",
                ssh_port=port,
                cpu=specs["cpu"],
                memory_mb=specs["memory_mb"],
                disk_gb=specs["disk_gb"],
                is_primary_proxy=is_first,
                container_idx=idx + 1,
                prepare_3xui=cfg.get("prepare_3xui", True),
                host_ip=host_ip,
                public_ip=ip or host_ip,
                known_password=previous.get(name),
                rotate_password=bool(cfg.get("rotate_passwords")),
            )
            deployed.append(c_info)
            print(f"[+] Container '{name}' ready (IP: {c_info['ipv4']}, Port: {port})")

        print("[*] Phase 6: Generating reports and credential files...")
        paths = save_artifacts(cfg["output_dir"], ip or "localhost", deployed, host_state, provisioner.warnings)
        print(f"[+] Credentials & Ports matrix saved to: {paths['credentials_md']}")
        print(f"[+] Relay & Residential Exit guide saved to: {paths['relay_md']}")
        print(f"[+] Cloudflare Origin Rules saved to: {paths['cloudflare_md']}")
        print(f"[+] Cluster README saved to: {paths['readme_md']}")
        print(f"[+] JSON result saved to: {paths['result_json']}")

        print("\n" + render_summary(ip or "localhost", deployed, cfg["output_dir"]))
        for warning in provisioner.warnings:
            print(f"[!] Warning: {warning}")
        return 0

    except RemoteError as e:
        print(f"\n[-] Deployment Error: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"\n[-] Unexpected Error: {e}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
