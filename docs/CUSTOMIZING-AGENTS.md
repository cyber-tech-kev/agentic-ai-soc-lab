# Customizing the Agents

The four agents are driven by natural-language prompts. Some of that prompt text is
**lab-specific** and assumes the reference build. Swapping an IP is not enough, you may
need to rewrite the instructions themselves.

## Where agent behavior is defined

Each agent lives in `soc-agents/<team>/` with two files:

- **`agent.py`** — the loop, the tool-calling logic, and prompt strings passed to Claude.
  Mission lists and guardrails live here as Python string literals.
- **`context.md`** — the agent's standing mission/guardrail prompt in prose.

Configuration (endpoints, credentials, paths) is read from `.env` at runtime and you do not
edit code to change those. See `.env.example`.

## What `setup.sh` handles for you

Running `setup.sh` and answering "yes" to the topology step rewrites the reference IPs
across `agent.py` and `context.md` to your own addresses. That covers the mechanical part.

## What you still have to do by hand

The reference prompts encode assumptions beyond IP addresses:

- **The Red agent's mission list names specific CVEs against Metasploitable 2** — the
  vsftpd 2.3.4 backdoor, UnrealIRCd, distccd, and so on. If your target is a different VM,
  these missions don't apply. Rewrite the mission list in `soc-agents/red-team/agent.py` to
  match what your target actually runs.
- **Guardrails list authorized vs. off-limits hosts by role** ("never attack the
  hypervisor / pfSense / Wazuh"). Confirm these match your lab's crown jewels and targets.
- **The Purple agent treats the hypervisor as the primary hunt target.** Adjust if your
  threat model centers elsewhere.
- **Segment descriptions** in each `context.md` describe the three-segment reference layout.
  If your lab differs (e.g. two segments), rewrite the topology block so the agent's mental
  model matches reality.

## Adding or removing an agent

Agents are independent. To add one, create `soc-agents/<newteam>/agent.py` following an
existing agent as a template, give it a `context.md`, and enable a systemd instance:
`systemctl enable --now soc-agent@<newteam>`. The messaging platform routes by agent name,
so pick a name and use it consistently in the code, the unit instance, and any prompts that
reference it.

## A note on prompt quality

The reference prompts are arguably the most valuable part of this repo — they're a worked
example of how to instruct an autonomous security agent with clear scope and guardrails.
Read them before rewriting. Keep the structure (role, authorized scope, explicit
prohibitions, output format) even as you change the specifics.
