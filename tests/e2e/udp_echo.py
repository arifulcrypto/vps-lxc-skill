#!/usr/bin/env python3
"""UDP echo: `udp_echo.py <port>` serves, `udp_echo.py <host> <port>` checks a round trip."""
import socket
import sys

if len(sys.argv) == 2:
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind(("0.0.0.0", int(sys.argv[1])))
    while True:
        data, peer = server.recvfrom(2048)
        server.sendto(data, peer)
else:
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client.settimeout(3)
    client.sendto(b"vps-lxc", (sys.argv[1], int(sys.argv[2])))
    assert client.recv(2048) == b"vps-lxc"
