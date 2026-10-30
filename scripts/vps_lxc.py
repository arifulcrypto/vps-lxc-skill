#!/usr/bin/env python3
"""
VPS LXC Multi-Container Deployment Automation Engine.
Provisions isolated LXC containers with fair resource sharing / auto-split,
clean environment configuration, distinct random passwords, independent SSH port forwarding,
and 3X-UI pre-requisite integration.

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

from scripts.provision import LXCProvisioner  # noqa: E402
from scripts.remote import RemoteError, TargetRunner  # noqa: E402
from scripts.report import render_summary, save_artifacts  # noqa: E402


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="VPS LXC Multi-Container Deployment Automation Engine"
    )
    parser.add_argument("--config", help="Path to JSON configuration file")
    parser.add_argument("--ip", help="Target VPS public IPv4 address")
    parser.add_argument("--ssh-port", type=int, default=22, help="Host SSH port (default: 22)")
    parser.add_argument("--ssh-user", default="root", help="Host SSH user (default: root)")
    parser.add_argument("--ssh-pass", help="Host SSH password (or VPS_SSH_PASS env var)")
    parser.add_argument("--ssh-key", help="Path to SSH private key file")
    parser.add_argument("--local", action="store_true", help="Run directly on local host")
    parser.add_argument("--count", type=int, default=2, help="Number of containers to create (default: 2)")
    parser.add_argument("--names", help="Comma-separated container names (default: vps-01,vps-02)")
    parser.add_argument("--auto-split", action="store_true",
                        help="Auto-detect host CPU/RAM/Disk and split resources fairly between containers")
    parser.add_argument("--cpu", type=int, default=2, help="CPU cores limit per container (default: 2)")
    parser.add_argument("--memory", type=int, default=1024, help="Memory limit in MB (default: 1024)")
    parser.add_argument("--disk", type=int, default=10, help="Disk quota in GB (default: 10)")
    parser.add_argument("--ssh-base-port", type=int, default=2201, help="Base port for container SSH (default: 2201)")
    parser.add_argument("--prepare-3xui", dest="prepare_3xui", action=argparse.BooleanOptionalAction, default=True,
                        help="Pre-install 3X-UI stack and forward 80/443 on first container (default: on)")
    parser.add_argument("--output-dir", help="Directory to save summary and credentials")
    parser.add_argument("--dry-run", action="store_true", help="Validate plan without making remote changes")
    return parser.parse_args(argv)


def load_config(args: argparse.Namespace) -> Dict[str, Any]:
    cfg: Dict[str, Any] = {}
    if args.config:
        with open(args.config, "r", encoding="utf-8") as f:
            cfg = json.load(f)

    for k, v in vars(args).items():
        if k not in ("config",) and v is not None:
            if v != parser_default(k) or k not in cfg:
                cfg[k] = v

    if not cfg.get("ssh_pass") and os.environ.get("VPS_SSH_PASS"):
        cfg["ssh_pass"] = os.environ["VPS_SSH_PASS"]

    # Fill defaults
    cfg.setdefault("ssh_port", 22)
    cfg.setdefault("ssh_user", "root")
    cfg.setdefault("count", 2)
    cfg.setdefault("cpu", 2)
    cfg.setdefault("memory", 1024)
    cfg.setdefault("disk", 10)
    cfg.setdefault("ssh_base_port", 2201)
    cfg.setdefault("auto_split", False)
    cfg.setdefault("prepare_3xui", True)

    host_id = cfg.get("ip") or "localhost"
    cfg.setdefault("output_dir", f"./output/{host_id}")
    return cfg


def parser_default(key: str) -> Any:
    defaults = {
        "ssh_port": 22,
        "ssh_user": "root",
        "count": 2,
        "cpu": 2,
        "memory": 1024,
        "disk": 10,
        "ssh_base_port": 2201,
        "auto_split": False,
        "prepare_3xui": True,
        "local": False,
        "dry_run": False
    }
    return defaults.get(key)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    cfg = load_config(args)

    is_local = cfg.get("local", False)
    ip = cfg.get("ip")

    if not is_local and not ip:
        print("[-] Error: Either --ip or --local must be specified.", file=sys.stderr)
        return 1

    host_desc = "Local System" if is_local else f"{cfg['ssh_user']}@{ip}:{cfg['ssh_port']}"
    print(f"[*] Target Host: {host_desc}")

    count = int(cfg["count"])
    if cfg.get("names"):
        container_names = [n.strip() for n in cfg["names"].split(",") if n.strip()]
    else:
        container_names = [f"vps-{i:02d}" for i in range(1, count + 1)]

    base_port = int(cfg["ssh_base_port"])
    ports = [base_port + i for i in range(len(container_names))]

    runner = TargetRunner(
        ip=ip if not is_local else None,
        port=cfg["ssh_port"],
        user=cfg["ssh_user"],
        password=cfg.get("ssh_pass"),
        key_file=cfg.get("ssh_key"),
        is_local=is_local
    )

    provisioner = LXCProvisioner(runner)

    if cfg.get("dry_run"):
        specs = {
            "cpu": cfg["cpu"],
            "memory_mb": cfg["memory"],
            "disk_gb": cfg["disk"]
        }
        print("[!] DRY-RUN plan preview (pure validation, no network calls):")
        for idx, name in enumerate(container_names):
            p = ports[idx]
            role = "Primary (3X-UI / Web Ready with ports 80/443)" if (idx == 0 and cfg["prepare_3xui"]) else "General Purpose VPS"
            print(f"    - Container: {name} (Role: {role})")
            print(f"      Specs    : {specs['cpu']} vCPU | {specs['memory_mb']}MB RAM | {specs['disk_gb']}GB Disk")
            print(f"      SSH Port : Host :{p} -> Container :22 (User: root, Unique Random Password)")
            print("      Isolation: Unprivileged LXC (security.nesting=true, root user)")
        print("[!] DRY-RUN completed: configuration is valid; no changes made.")
        return 0

    try:
        print("[*] Phase 1: Testing SSH connection and preparing LXD environment...")
        runner.test_connection()
        lxd_ver = provisioner.ensure_lxd()
        print(f"[+] LXD daemon ready (version {lxd_ver})")

        print("[*] Phase 2: Computing resource limits...")
        specs = provisioner.compute_specs(
            count=count,
            auto_split=cfg.get("auto_split", False),
            manual_cpu=cfg["cpu"],
            manual_ram=cfg["memory"],
            manual_disk=cfg["disk"]
        )
        print(f"[+] Per-container specs: {specs['cpu']} vCPU | {specs['memory_mb']}MB RAM | {specs['disk_gb']}GB Disk")

        print("[*] Phase 3: Verifying storage pool and managed bridge...")
        provisioner.ensure_storage_and_network()
        print("[+] Storage pool and network verified.")

        print("[*] Phase 4: Checking base image...")
        provisioner.cache_base_image()

        print("[*] Phase 5: Deploying LXC containers...")
        deployed = []
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
                is_primary_proxy=is_first
            )
            deployed.append(c_info)
            print(f"[+] Container '{name}' ready (IP: {c_info['ipv4']}, Port: {port})")

        print("[*] Phase 6: Generating reports and credential files...")
        paths = save_artifacts(cfg["output_dir"], ip or "localhost", deployed)
        print(f"[+] Summary saved to: {paths['summary']}")
        print(f"[+] JSON result saved to: {paths['result_json']}")

        print("\n" + render_summary(ip or "localhost", deployed))
        return 0

    except RemoteError as e:
        print(f"\n[-] Deployment Error: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"\n[-] Unexpected Error: {e}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
