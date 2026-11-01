#!/usr/bin/env python3
"""Provisioning logic against a stateful fake of the LXD client."""
import json
import re
import shlex

import pytest

from scripts.provision import LXCProvisioner, PASSWORD_KEY, deployer_config, parse_size_mb, validate_plan
from scripts.remote import RemoteError
from scripts.report import render_relay_and_exit_guide


class FakeLXD:
    """Implements the lxc commands the provisioner uses, and rejects flags the real client rejects."""

    def __init__(self, default_profile_has_root=True):
        self.commands = []
        self.instances = {}
        self.profiles = {"default": {"devices": {"root": {"pool": "default"}}} if default_profile_has_root else {"devices": {}}}
        self.pools = [{"name": "default"}]
        self.networks = [{"name": "lxdbr0", "managed": True,
                          "config": {"ipv4.address": "10.0.43.1/24", "ipv4.nat": "true"}}]
        self.fail_device = None
        self.host_ram = 8192
        self.host_disk = 100

    def run(self, cmd, timeout=180, check=True):
        self.commands.append(cmd)
        code, out, err = self.dispatch(cmd)
        if check and code != 0:
            raise RemoteError(err or f"failed: {cmd}")
        return code, out, err

    def dispatch(self, cmd):
        if "profile show" in cmd and "--format" in cmd:
            return 1, "", "Error: unknown flag: --format"
        if cmd.startswith("lxc query"):
            return self.query(shlex.split(cmd)[2])
        if cmd == "nproc":
            return 0, "4", ""
        if cmd.startswith("free -m"):
            return 0, str(self.host_ram), ""
        if "df -BG" in cmd:
            return 0, str(self.host_disk), ""
        if cmd.startswith("command -v lxc"):
            return 0, "/snap/bin/lxc", ""
        if cmd.startswith("lxd version"):
            return 0, "5.21.9", ""
        if cmd.startswith("ip -4 route get"):
            return 0, "203.0.113.10", ""
        if cmd.startswith("ss -Htulnp"):
            return 0, getattr(self, "listeners", ""), ""
        if "HOST_FIREWALL" in cmd:
            return 0, "HOST_FIREWALL=none\nHOST_FORWARD=default", ""
        if "HOST_CC" in cmd:
            return 0, "HOST_CC=bbr\nHOST_RMEM_MAX=16777216", ""
        if "df -BM" in cmd:
            return 0, "10000", ""
        if cmd.startswith("lxc profile create"):
            self.profiles["vps-lxc"] = {"devices": {}}
            return 0, "", ""
        match = re.match(r"lxc profile device add (\S+) (\S+) \S+ (.*)", cmd)
        if match:
            profile, device, rest = match.groups()
            if device in self.profiles[profile]["devices"]:
                return 1, "", "Error: The device already exists"
            self.profiles[profile]["devices"][device] = dict(kv.split("=") for kv in rest.split())
            return 0, "", ""
        match = re.match(r"lxc init \S+ (\S+) -p (\S+)", cmd)
        if match:
            name = match.group(1)
            self.instances[name] = {"status": "Stopped", "config": {}, "devices": {}, "profile": match.group(2)}
            return 0, "", ""
        match = re.match(r"lxc config set (\S+) (\S+) (.+)", cmd)
        if match:
            self.instances[match.group(1)]["config"][match.group(2)] = shlex.split(match.group(3))[0]
            return 0, "", ""
        match = re.match(r"lxc config device (override|set) (\S+) (\S+) (\S+)=(\S+)", cmd)
        if match:
            _, name, device, key, value = match.groups()
            self.instances[name]["devices"].setdefault(device, {})[key] = value
            return 0, "", ""
        if cmd.startswith("lxc start"):
            self.instances[cmd.split()[2]]["status"] = "Running"
            return 0, "", ""
        if "PORT " in cmd:
            return self.apply_ports(cmd)
        return 0, "", ""

    def apply_ports(self, script):
        out = []
        for line in script.splitlines():
            remove = re.match(r"lxc config device remove (\S+) (\S+)", line)
            if remove:
                self.instances[remove.group(1)]["devices"].pop(remove.group(2), None)
            add = re.match(r"if lxc config device add (\S+) (\S+) proxy (listen=\S+) (connect=\S+) nat=true", line)
            if not add:
                continue
            name, dev, listen, connect = add.groups()
            if dev == self.fail_device:
                out.append(f"PORTFAIL {dev} Error: port is busy")
                continue
            self.instances[name]["devices"][dev] = {"type": "proxy", "listen": listen[7:], "connect": connect[8:], "nat": "true"}
            out.append(f"PORT {dev} nat")
        return 0, "\n".join(out), ""

    def query(self, path):
        if path == "/1.0/storage-pools?recursion=1":
            return 0, json.dumps(self.pools), ""
        if path == "/1.0/networks?recursion=1":
            return 0, json.dumps(self.networks), ""
        if path.endswith("/leases"):
            return 0, "[]", ""
        if path.startswith("/1.0/images/aliases/"):
            return 0, "{}", ""
        match = re.match(r"/1.0/profiles/(.+)", path)
        if match:
            if match.group(1) in self.profiles:
                return 0, json.dumps(self.profiles[match.group(1)]), ""
            return 1, "", "Error: Profile not found"
        match = re.match(r"/1.0/instances/([^?]+)", path)
        if match:
            inst = self.instances.get(match.group(1))
            if inst is None:
                return 1, "", "Error: Instance not found"
            return 0, json.dumps(dict(inst, expanded_config=inst["config"], expanded_devices=inst["devices"])), ""
        return 1, "", f"Error: unexpected query {path}"


def provisioner(lxd):
    p = LXCProvisioner(lxd)
    p.ensure_storage_and_network()
    return p


def deploy(p, name="vps-01", idx=1, **kwargs):
    return p.deploy_container(name, "vps", 2200 + idx, container_idx=idx, host_ip="203.0.113.10",
                              public_ip="203.0.113.10", **kwargs)


def test_host_with_initialized_default_profile_does_not_abort():
    lxd = FakeLXD(default_profile_has_root=True)
    provisioner(lxd)
    assert not any("profile device add default" in c for c in lxd.commands)
    assert not any("--format" in c for c in lxd.commands)


def test_second_run_of_storage_setup_succeeds_and_changes_nothing():
    lxd = FakeLXD()
    provisioner(lxd)
    lxd.commands.clear()
    provisioner(lxd)
    assert not any("profile create" in c or "profile device add" in c for c in lxd.commands)


def test_failed_lxd_read_is_not_treated_as_empty():
    lxd = FakeLXD()
    lxd.dispatch = lambda cmd: (1, "", "Error: permission denied")
    with pytest.raises(RemoteError, match="permission denied"):
        provisioner(lxd)


def test_mismatched_profile_is_rejected():
    lxd = FakeLXD()
    lxd.profiles["vps-lxc"] = {"devices": {"root": {"pool": "other"}, "eth0": {"network": "lxdbr0"}}}
    with pytest.raises(RemoteError, match="does not use pool"):
        provisioner(lxd)


def test_unmanaged_bridge_is_rejected():
    lxd = FakeLXD()
    lxd.networks = [{"name": "lxdbr0", "managed": False, "config": {}}]
    with pytest.raises(RemoteError, match="must be LXD-managed"):
        provisioner(lxd)


def test_new_container_gets_static_ip_nat_ports_and_stored_password():
    lxd = FakeLXD()
    result = deploy(provisioner(lxd))
    assert result["ipv4"] == "10.0.43.10"
    assert lxd.instances["vps-01"]["devices"]["eth0"]["ipv4.address"] == "10.0.43.10"
    device = lxd.instances["vps-01"]["devices"]["p443"]
    assert device["listen"] == "tcp:203.0.113.10:443" and device["connect"] == "tcp:10.0.43.10:443"
    assert {p["forward"] for p in result["ports"]} == {"nat"}
    assert lxd.instances["vps-01"]["config"][PASSWORD_KEY] == result["password"]


def test_rerun_keeps_password_and_touches_no_devices():
    lxd = FakeLXD()
    p = provisioner(lxd)
    first = deploy(p)
    lxd.commands.clear()
    second = deploy(p)
    assert second["password"] == first["password"]
    assert not any("chpasswd" in c and first["password"] in c for c in lxd.commands)
    assert not any("config device" in c for c in lxd.commands)


def test_rerun_applies_changed_limits_and_starts_stopped_container():
    lxd = FakeLXD()
    p = provisioner(lxd)
    deploy(p)
    lxd.instances["vps-01"]["status"] = "Stopped"
    lxd.commands.clear()
    result = deploy(p, cpu=4, memory_mb=2048)
    assert "lxc config set vps-01 limits.cpu 4" in lxd.commands
    assert "lxc config set vps-01 limits.memory 2048MB" in lxd.commands
    assert any(c.startswith("lxc start vps-01") for c in lxd.commands)
    assert result["specs"]["cpu_cores"] == 4


def test_rotation_changes_the_password():
    lxd = FakeLXD()
    p = provisioner(lxd)
    first = deploy(p)
    assert deploy(p, rotate_password=True)["password"] != first["password"]


def test_container_without_stored_password_keeps_it_unchanged():
    lxd = FakeLXD()
    p = provisioner(lxd)
    deploy(p)
    del lxd.instances["vps-01"]["config"][PASSWORD_KEY]
    lxd.commands.clear()
    result = deploy(p)
    assert result["password"] is None
    assert not any("chpasswd" in c and "root:" in c for c in lxd.commands)
    assert "ssh_pass" not in result["deployer_config"]


def test_device_failure_cannot_produce_a_result():
    lxd = FakeLXD()
    lxd.fail_device = "p443"
    with pytest.raises(RemoteError, match="p443"):
        deploy(provisioner(lxd))


def test_lookup_uses_exact_instance_paths():
    lxd = FakeLXD()
    deploy(provisioner(lxd))
    assert not any(c.startswith("lxc list") for c in lxd.commands)


def test_auto_split_rejects_a_host_that_is_too_small():
    lxd = FakeLXD()
    lxd.host_ram, lxd.host_disk = 1024, 6
    with pytest.raises(RemoteError, match="cannot fit 4 containers"):
        LXCProvisioner(lxd).compute_specs(4, auto_split=True)


def test_auto_split_divides_after_reserving_host_headroom():
    assert LXCProvisioner(FakeLXD()).compute_specs(4, auto_split=True) == {"cpu": 4, "memory_mb": 1920, "disk_gb": 24}


def test_manual_overcommit_is_recorded():
    lxd = FakeLXD()
    lxd.host_ram = 2048
    p = LXCProvisioner(lxd)
    assert p.compute_specs(4, manual_ram=1024)["memory_mb"] == 1024
    assert "Memory limits total 4096MB" in p.warnings[0]


def test_existing_specs_keep_auto_split_stable():
    lxd = FakeLXD()
    p = provisioner(lxd)
    deploy(p, cpu=3, memory_mb=1500, disk_gb=20)
    assert p.existing_specs(["vps-01"]) == {"cpu": 3, "memory_mb": 1500, "disk_gb": 20}


def test_foreign_listener_blocks_before_changes():
    lxd = FakeLXD()
    lxd.listeners = 'tcp LISTEN 0 511 0.0.0.0:443 0.0.0.0:* users:(("nginx",pid=1,fd=6))'
    with pytest.raises(RemoteError, match="443/tcp"):
        LXCProvisioner(lxd).preflight_host_ports([{"ext": 443, "proto": "tcp"}])


def test_own_proxy_listener_is_allowed():
    lxd = FakeLXD()
    lxd.listeners = 'tcp LISTEN 0 511 0.0.0.0:443 0.0.0.0:* users:(("lxd",pid=1,fd=6))'
    LXCProvisioner(lxd).preflight_host_ports([{"ext": 443, "proto": "tcp"}])


def base_cfg(**extra):
    return dict({"cpu": 2, "memory": 1024, "disk": 10, "ssh_base_port": 2201, "ssh_port": 22}, **extra)


@pytest.mark.parametrize("cfg,message", [
    ({"count": 0}, "between 1 and 6"),
    ({"count": 7}, "between 1 and 6"),
    ({"names": "a,a"}, "Duplicate"),
    ({"names": "bad_name"}, "Invalid container name"),
    ({"names": "a;reboot"}, "Invalid container name"),
    ({"names": "a,b", "count": 3}, "disagrees"),
    ({"memory": 0}, "memory must be"),
    ({"ssh_base_port": 80}, "planned for both"),
    ({"ssh_base_port": 2201, "ssh_port": 2201}, "host SSH port"),
    ({"ssh_base_port": 70000}, "out of range"),
])
def test_invalid_plans_are_rejected(cfg, message):
    with pytest.raises(RemoteError, match=message):
        validate_plan(base_cfg(**cfg))


def test_names_set_the_count_and_all_six_containers_have_unique_ports():
    assert validate_plan(base_cfg(names="a,b,c"))["count"] == 3
    assert validate_plan(base_cfg(count=6))["count"] == 6


def test_deployer_config_matches_the_forwarded_ports():
    cfg = deployer_config("203.0.113.10", 2, 2202, "pw")
    plan = validate_plan(base_cfg(count=2))
    forwarded = {(p["ext"], p["proto"]) for p in plan["matrix"][1]}
    for key, proto in (("ssh_port", "tcp"), ("panel_port", "tcp"), ("reality_port", "tcp"), ("hy2_port", "udp"),
                       ("https_port", "tcp"), ("sub_port", "tcp"), ("vmess_port", "tcp"), ("trojan_port", "tcp")):
        assert (cfg[key], proto) in forwarded, key
    assert cfg["web_backend_port"] not in {p for p, _ in forwarded}
    assert cfg["cert_mode"] == "dns-01"
    assert deployer_config("203.0.113.10", 1, 2201, None)["cert_mode"] == "http-01"


def test_runbook_uses_real_container_names():
    text = render_relay_and_exit_guide("203.0.113.10", [{"name": "vps-01"}, {"name": "vps-02"}])
    assert "c3-backup" not in text and "c2-app" not in text
    assert "lxc exec vps-02" in text and "$(uname -m)" in text


@pytest.mark.parametrize("value,expected", [("1024MB", 1024), ("10GB", 10000), ("1GiB", 1024), ("x", 0)])
def test_parse_size(value, expected):
    assert parse_size_mb(value) == expected
