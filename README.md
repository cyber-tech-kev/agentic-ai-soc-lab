# Agentic AI Powered SOC
---
An agentic, AI powered homelab Security Operations Center featuring four autonomous agents - Red, Blue, Green, Purple. Each drives Claude via the CLI and coordinates through a small custom Flask/SQLite messaging platform running against an intentionally vulnerable lab network.

This is a learning and portfolio project, packaged as a template you can clone and adapt to your own homelab. This is NOT production security tooling.

This lab consists of the following services:
Claude as the LLM, Proxmox environment, pfSense VM, Suricata (IDS), Wazuh (SIEM/EDR), Kali VM, Windows VM, Metasploitable 2 VM, self-hosted messaging platform.

---

## Security — Read Before Deploying!

**This project runs autonomous agents with unrestricted shell access. Acknowledge these risks before pointing it at anything.**

### Prompt injection is an identified, open, and unmitigated risk

The agents invoke Claude with `--dangerously-skip-permissions`, which gives them unrestricted shell access on their respective host. Attacker-controlled fields from Wazuh alert bodies, User-Agent strings, filenames, and command lines all flow into agent prompts **without sanitization**. A crafted log entry could in theory influence an agent that is able to run shell commands. (This has not been tested yet.)

This is a known architectural weakness in the design and is **not yet mitigated**. Do not run this against real or untrusted traffic. Treat it as a lab exercise in an isolated, segmented network. If you wish to extend it, adding external input validation should be your first concern so you aren't relying on the model to police itself.

### The messaging bus is a second, more direct injection path

The `/send` endpoint on the Flask messaging platform (`soc-messaging/soc-messaging-platform-main.py`) accepts a `sender`, `recipient`, and `body` with **no authentication**. Anything that can reach port 5000 can post a message into any agent's inbox while claiming to be any other agent, no alert has to be crafted or triaged first, it's a direct write into what an agent will read and act on next. This is arguably a shorter path to influencing agent behavior than the Wazuh alert-field path above, and it's equally **unmitigated**.

If you expose this port beyond `127.0.0.1` (including via Tailscale, per the comment in the code) for any reason, you're extending this same trust boundary. A minimal fix would be a shared-secret header checked on `/send`; that hasn't been implemented yet.

### Other Essentials

- **Runs an intentionally vulnerable VM** (Metasploitable 2) on purpose. Keep the lab network isolated.
- **Secrets live only in `.env`**, which is gitignored. The Discord webhook URLs are bearer creds — anyone holding them can post to the server. Never commit them, and rotate immediately if one leaks.
- **Agents run as a non-root user** by design. I suggest keeping it that way.

---

## What's in here

```
soc-agents/          The four agents (red / blue / green / purple)
  <team>/agent.py      loop + logic + prompt strings
  <team>/context.md    the agent's standing mission/guardrail prompt
soc-messaging/       Flask + SQLite message bus and dashboard (port 5000)
systemd/             Templated systemd unit for running agents as services
docs/                Topology, constraints, and agent customization guides
.env.example         Config template — copy to .env
setup.sh             Interactive first-run config
```

### The agents

| Agent  | Role                        | What it does                                    |
|--------|-----------------------------|-------------------------------------------------|
| Red    | Offensive                   | SSHes into Kali, runs authorized attacks on targets |
| Blue   | Alert triage / IR           | Reads Wazuh alerts, writes incident notes       |
| Green  | Detection engineering       | SSHes into Wazuh to stage detection rules       |
| Purple | Threat hunting              | Pulls raw logs, hunts across the environment     |

Agents coordinate by posting to the messaging platform, which also drives a live dashboard.
High-confidence alerts escalate to Discord.

---

## Prerequisites

This is **not** a one-command install. You need a working lab:

- Proxmox host with three network segments (see [docs/TOPOLOGY.md](docs/TOPOLOGY.md))
- A running Wazuh deployment (indexer + manager) with client certs
- Claude CLI installed and authenticated on the agent host
- Python 3 with `requests` and `flask`
- `jq` on the agent host (missing `jq` causes silent failures in multi-step invocations)
- A Discord server with two webhooks

---

## Setup

```bash
git clone <your-fork-url>
cd ghost-lab-soc

# Configure secrets + (optionally) rewrite reference IPs to your lab
./setup.sh

# Start the messaging platform
python3 soc-messaging/soc-messaging-platform-main.py

# Install and start the agents as services
sudo cp systemd/soc-agent@.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now soc-agent@{red-team,blue-team,green-team,purple-team}
```

Then read [docs/CUSTOMIZING-AGENTS.md](docs/CUSTOMIZING-AGENTS.md) — the reference agent
prompts assume specific targets (Metasploitable 2, named CVEs) and you'll likely need to
adapt them.

---

## Reference topology

Three isolated segments on one Proxmox host: home (`10.0.0.0/24`), red team
(`192.168.100.0/24`), and SOC (`192.168.200.0/24`). Full host table and the non-obvious
build constraints — pfSense interface quirks, Wazuh indexer binding, why only cross-segment
traffic is detectable — are in [docs/TOPOLOGY.md](docs/TOPOLOGY.md).

---

## Status & roadmap

This is an evolving lab project. Known gaps and planned work:

- **Prompt-injection defense** (external validation on Wazuh alert fields, and auth on the `/send` endpoint) the highest priority, see above
- Durable agent memory to avoid re-triaging known-benign alerts
- Deployment gates for the Green agent's rule-staging pipeline
- Cross-segment attack simulation (Kali > Windows endpoint)
- MISP and Zeek integration

Forks are welcome.
