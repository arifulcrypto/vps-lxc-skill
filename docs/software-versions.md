# Software Versions and Downloads

Check for newer releases at any time:

```bash
python3 scripts/check_versions.py
```

"Tested" means this project ran that version with real traffic. A newer release may work, but test it first.

## Servers

| Software | Tested | Newest seen | Official download | How to upgrade |
| :--- | :--- | :--- | :--- | :--- |
| 3X-UI | v3.11.0 | v3.11.0 | [Releases](https://github.com/MHSanaei/3x-ui/releases) | `--xui-version vX.Y.Z --reinstall-xui` in vps-deploy-skill |
| Xray | 26.10.21 (bundled with 3X-UI) | 26.10.31 | [Releases](https://github.com/XTLS/Xray-core/releases) | Run `xray run -test` first, then replace the binary and restart `x-ui` |
| LXD | 5.21.9 LTS, 6.10.1, 4.0.15 | 6.10.1 | [Snap](https://snapcraft.io/lxd) | `snap refresh lxd --channel=5.21/stable` is one-way |
| Realm | 2.9.6 | 2.9.6 | [Releases](https://github.com/zhboner/realm/releases) | Replace the binary and restart `realm` |
| acme.sh | Installed from upstream | 3.1.6 | [Project](https://github.com/acmesh-official/acme.sh) | Upgrades itself |

To test a new Xray safely, keep the running config and point the assets at the panel's folder:

```bash
cd /usr/local/x-ui/bin
XRAY_LOCATION_ASSET=/usr/local/x-ui/bin /root/xray-new run -test -c config.json
```

## Clients

| Client | Platforms | Newest seen | Status here | Official download |
| :--- | :--- | :--- | :--- | :--- |
| Mihomo core | All | v1.19.33 | **Tested. Minimum v1.19.9** | [Releases](https://github.com/MetaCubeX/mihomo/releases) |
| Clash Verge Rev | Windows, macOS, Linux | v2.5.8 | Uses Mihomo, app not tested | [Releases](https://github.com/clash-verge-rev/clash-verge-rev/releases) |
| FlClash | Windows, macOS, Linux, Android | v0.9.2 | Uses Mihomo, app not tested | [Releases](https://github.com/chen08209/FlClash/releases) |
| v2rayN | Windows, Linux, macOS | 7.25.6 | Not tested | [Releases](https://github.com/2dust/v2rayN/releases) |
| v2rayNG | Android | 2.3.14 | Not tested | [Releases](https://github.com/2dust/v2rayNG/releases) |
| sing-box | All | v1.14.4 | Not tested as a client; used as a landing server | [Releases](https://github.com/SagerNet/sing-box/releases) |
| Hiddify | All | v4.1.1 | Not tested | [Releases](https://github.com/hiddify/hiddify-app/releases) |

**Mihomo and REALITY:** with an Xray server, Mihomo needs `support-x25519mlkem768: true`. The generated YAML and the panel subscription set it. A hand-written node without it fails against Xray. A sing-box server doesn't need it.

Only get these from the official links. Copies from unofficial sites can contain altered binaries.
