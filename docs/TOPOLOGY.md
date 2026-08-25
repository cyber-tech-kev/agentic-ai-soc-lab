# Topology & Architectural Constraints

Ghost Lab runs on a single Proxmox host with three isolated network segments. The
addresses below are the **reference build** RFC1918 space, documentation rather than
secrets. Adapt them to your own lab (see `CUSTOMIZING-AGENTS.md` and `setup.sh`).

## Segments

| Segment    | Bridge | Range             | Hosts                                          |
|------------|--------|-------------------|------------------------------------------------|
| Home       | vmbr0  | 10.0.0.0/24       | Proxmox host (hypervisor)                       |
| Red team   | vmbr1  | 192.168.100.0/24  | Kali (attack platform), Metasploitable 2 (target) |
| SOC        | vmbr2  | 192.168.200.0/24  | pfSense (gateway), Wazuh (SIEM), Windows 10 endpoint |

### Reference host addresses

| Host              | Address          | Role                              |
|-------------------|------------------|-----------------------------------|
| Proxmox host      | 10.0.0.149       | Hypervisor. Agents run here.      |
| Kali              | 192.168.100.50   | Red team attack platform          |
| Metasploitable 2  | 192.168.100.2    | Intentionally vulnerable target   |
| pfSense           | 192.168.200.1    | Firewall / inter-segment gateway  |
| Wazuh             | 192.168.200.2    | SIEM — indexer :9200, API :55000  |
| Windows 10        | 192.168.200.3    | Monitored endpoint                |

Remote access is via Tailscale on the Proxmox host, advertising subnet routes.

## Constraints worth knowing before you build

These are the non-obvious lessons from the reference build. Ignoring them will cost you
hours.

**Only cross-segment traffic is detectable.** Hosts on the same bridge talk directly and
never traverse pfSense, so network-based detection (Suricata, etc.) never sees intra-segment
attacks. If your red and target hosts share a segment, their traffic is invisible to the
SOC. This bounds what the lab can catch — design attack scenarios that cross segments if you
want them detected.

**Proxmox owns `/etc/network/interfaces`.** It rewrites the file, so bridge IPs set by hand
there are lost on reboot. Set them through the Proxmox Network UI instead.

**pfSense interface naming is inverted from intuition.** In the reference build:
`LAN = em1 = red team segment`, `OPT1 = em2 = SOC segment`. OPT1 also needs an explicit
allow-all outbound rule before SOC-segment VMs can reach the internet — without it they're
silently cut off.

**Wazuh indexer binds localhost by default.** Set `network.host: 0.0.0.0` so agents on other
hosts can reach it. The indexer's certificate does not cover IP addresses, so client
connections use `verify=False` for TLS — expected in a lab, not something to "fix."

## Prerequisites

This is not a one-command install. You need:

- A Proxmox host with the three bridges configured
- A working Wazuh deployment (indexer + manager) with client certs
- The Claude CLI installed and authenticated on the agent host
- Python 3 with `requests` and `flask`
- A Discord server with two webhooks (alerts + general)
- `jq` installed on the agent host (used in multi-step Claude invocations; missing `jq`
  causes silent pipe failures)
