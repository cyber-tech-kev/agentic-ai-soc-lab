#!/usr/bin/env bash
#
# Ghost Lab SOC — first-run setup
#
# 1. Creates .env from .env.example and prompts for the must-change values.
# 2. Optionally rewrites the reference IPs in the agent prompt files
#    (agent.py + context.md) to match your own lab.
#
# This script is a convenience layer. The repo works with the reference
# defaults if you skip it — there is a single source of truth (the real
# files), no separate templates.
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

echo "── Ghost Lab SOC setup ─────────────────────────────"
echo

# ── 1. .env ─────────────────────────────────────────────
if [[ -f .env ]]; then
  echo "  .env already exists — leaving it untouched."
else
  cp .env.example .env
  echo "  Created .env from .env.example"
  echo
  echo "  Enter the required secrets (leave blank to edit .env by hand later):"

  read -rp "  Discord ALERTS webhook URL: " alerts
  read -rp "  Discord GENERAL webhook URL: " general
  read -rp "  Path to Wazuh client cert (.pem): " cert
  read -rp "  Path to Wazuh client key (.pem):  " key

  [[ -n "$alerts"  ]] && sed -i.bak "s|^DISCORD_WEBHOOK_ALERTS=.*|DISCORD_WEBHOOK_ALERTS=$alerts|"   .env
  [[ -n "$general" ]] && sed -i.bak "s|^DISCORD_WEBHOOK_GENERAL=.*|DISCORD_WEBHOOK_GENERAL=$general|" .env
  [[ -n "$cert"    ]] && sed -i.bak "s|^WAZUH_CERT=.*|WAZUH_CERT=$cert|"                             .env
  [[ -n "$key"     ]] && sed -i.bak "s|^WAZUH_KEY=.*|WAZUH_KEY=$key|"                                .env
  rm -f .env.bak

  chmod 600 .env
  echo "  .env written and locked to 0600."
fi
echo

# ── 2. Topology substitution (optional) ─────────────────
echo "── Lab topology ────────────────────────────────────"
echo "  The agent prompts contain reference IPs from the original build."
echo "  You can rewrite them now, or leave the defaults and edit prompts by hand."
echo
read -rp "  Rewrite reference IPs to your own lab? [y/N] " do_topo

if [[ "${do_topo,,}" == "y" ]]; then
  declare -A MAP
  echo "  Enter your values (blank = keep the reference default):"

  prompt_ip() {
    local label="$1" default="$2" var
    read -rp "    $label [$default]: " var
    MAP["$default"]="${var:-$default}"
  }

  prompt_ip "Hypervisor / Proxmox host"      "10.0.0.149"
  prompt_ip "Kali (attack platform)"         "192.168.100.50"
  prompt_ip "Metasploitable (target)"        "192.168.100.2"
  prompt_ip "pfSense gateway"                "192.168.200.1"
  prompt_ip "Wazuh SIEM"                     "192.168.200.2"
  prompt_ip "Windows endpoint"               "192.168.200.3"

  # Apply substitutions across prompt-bearing files only.
  files=$(grep -rl -E "10\.0\.0\.|192\.168\." \
            soc-agents --include='*.py' --include='*.md' || true)

  for old in "${!MAP[@]}"; do
    new="${MAP[$old]}"
    [[ "$old" == "$new" ]] && continue
    for f in $files; do
      sed -i.bak "s|$old|$new|g" "$f"
    done
    echo "    $old → $new"
  done
  find soc-agents -name '*.bak' -delete
  echo "  Topology rewritten. Review the prompt files before running the agents."
else
  echo "  Keeping reference defaults."
fi

echo
echo "── Done ────────────────────────────────────────────"
echo "  Next: review .env, install systemd units from systemd/,"
echo "  and read docs/CUSTOMIZING-AGENTS.md before first run."
