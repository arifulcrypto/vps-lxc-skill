# Gemini / Google Antigravity Skill Guidelines (English)

The skill is auto-discovered from [`.agents/skills/vps-lxc-creator/SKILL.md`](../.agents/skills/vps-lxc-creator/SKILL.md) (which links to the root [`SKILL.md`](../SKILL.md), the source of truth).

## In-session protocol
1. Extract target VPS `ip`, SSH credentials, and optional custom container parameters; ask for anything missing.
2. Default configuration creates 2 LXC containers, each with 2 vCPU, 1GB RAM, 10GB disk, distinct random passwords, and independent SSH ports starting at 2201.
3. Write a config JSON and run `python3 scripts/vps_lxc.py --config <file> --dry-run`. Show the plan and wait for confirmation.
4. Execute the deployment using `run_command` via `python3 scripts/vps_lxc.py --config <file>`. Do not run ad-hoc `sshpass` commands against the server.
5. On success, create a summary report from `result.json` with SSH login commands and credentials. Note that output files contain sensitive passwords.

Default output language is English (`en`).
