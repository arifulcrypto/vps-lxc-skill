#!/usr/bin/env python3
"""Compare the tested versions with the newest GitHub releases. Read-only."""
import json
import sys
import urllib.error
import urllib.request

TESTED = {
    "MHSanaei/3x-ui": "v3.11.0",
    "XTLS/Xray-core": "v26.10.21",
    "MetaCubeX/mihomo": "v1.19.33",
    "zhboner/realm": "v2.9.6",
    "SagerNet/sing-box": "v1.14.4",
    "clash-verge-rev/clash-verge-rev": "v2.5.8",
    "chen08209/FlClash": "v0.9.2",
    "2dust/v2rayN": "7.25.6",
    "2dust/v2rayNG": "2.3.14",
}


def latest(repo: str) -> str:
    request = urllib.request.Request(f"https://api.github.com/repos/{repo}/releases/latest",
                                     headers={"Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.load(response)["tag_name"]


def main() -> int:
    newer = 0
    for repo, tested in TESTED.items():
        try:
            current = latest(repo)
        except (urllib.error.URLError, KeyError, ValueError) as e:
            print(f"{repo:<34} could not check: {e}")
            continue
        flag = "" if current == tested else "  <- newer release, test before upgrading"
        newer += bool(flag)
        print(f"{repo:<34} listed {tested:<12} latest {current}{flag}")
    print(f"{newer} newer release(s). See docs/software-versions.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
