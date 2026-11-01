#!/usr/bin/env python3
"""
Remote execution engine for VPS commands via SSH and local subprocess.
Supports custom SSH ports, SSH private key authentication, password authentication
via sshpass, and safe non-interactive execution with timeouts.
"""
import os
import subprocess
from typing import List, Optional, Tuple


class RemoteError(Exception):
    pass


class TargetRunner:
    def __init__(self, ip: Optional[str] = None, port: int = 22, user: str = "root",
                 password: Optional[str] = None, key_file: Optional[str] = None,
                 is_local: bool = False):
        self.ip = ip
        self.port = int(port) if port else 22
        self.user = user or "root"
        self.password = password
        self.key_file = os.path.expanduser(key_file) if key_file else None
        self.is_local = is_local

    def build_ssh_command(self, cmd: str) -> List[str]:
        ssh_opts = [
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", "LogLevel=ERROR",
            "-o", "ConnectTimeout=15",
            "-p", str(self.port)
        ]

        if self.key_file:
            if not os.path.exists(self.key_file):
                raise RemoteError(f"SSH private key file not found: {self.key_file}")
            ssh_opts += ["-i", self.key_file]

        remote_dest = f"{self.user}@{self.ip}"

        if self.password and not self.key_file:
            return ["sshpass", "-p", self.password, "ssh"] + ssh_opts + [remote_dest, cmd]
        return ["ssh"] + ssh_opts + [remote_dest, cmd]

    def run(self, cmd: str, timeout: int = 180, check: bool = True) -> Tuple[int, str, str]:
        """
        Executes a command either locally or remotely over SSH.
        Standard input is strictly redirected to /dev/null to prevent hanging on pipes.
        """
        # Non-login shells miss /snap/bin on Debian and under sudo.
        wrapped = f'export PATH="$PATH:/snap/bin"\n{cmd}'
        if self.is_local or not self.ip:
            full_cmd = ["bash", "-c", wrapped]
        else:
            full_cmd = self.build_ssh_command(wrapped)

        try:
            res = subprocess.run(
                full_cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout
            )
            stdout = res.stdout.strip()
            stderr = res.stderr.strip()
            if check and res.returncode != 0:
                hint = ""
                if "Permission denied" in stderr:
                    hint = "\n[Hint] Authentication failed. Check SSH user, password, or key permissions."
                elif "Connection refused" in stderr or "timed out" in stderr.lower():
                    hint = f"\n[Hint] Cannot reach {self.ip}:{self.port}. Verify IP and SSH port."
                raise RemoteError(
                    f"Command execution failed (exit code {res.returncode}):\n"
                    f"Command: {cmd}\nStderr: {stderr}\nStdout: {stdout}{hint}"
                )
            return res.returncode, stdout, stderr
        except subprocess.TimeoutExpired as e:
            raise RemoteError(f"Command timed out after {timeout} seconds:\n{cmd}") from e

    def test_connection(self) -> None:
        """Verifies SSH connectivity and basic shell execution."""
        if self.is_local:
            return
        code, stdout, stderr = self.run("echo __OK__", timeout=15)
        if "__OK__" not in stdout:
            raise RemoteError(f"Failed to establish SSH connection to {self.user}@{self.ip}:{self.port}")
