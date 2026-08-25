# Discord notification module for Ghost Lab SOC agents
import os
import requests

WEBHOOK_ALERTS = os.environ.get('DISCORD_WEBHOOK_ALERTS')
WEBHOOK_GENERAL = os.environ.get('DISCORD_WEBHOOK_GENERAL')
AGENT_COLORS = {
    'red-team':    0xf87171,
    'blue-team':   0x38bdf8,
    'green-team':  0x4ade80,
    'purple-team': 0xc084fc,
    'operator':    0x60a5fa,
}

def send_alert(agent, title, message, urgent=False):
    """Send to #soc-alerts — use for TPs, escalations, confirmed threats"""
    payload = {
        "embeds": [{
            "title": f"{'🚨 ' if urgent else '⚠️ '}{title}",
            "description": message[:4000],
            "color": AGENT_COLORS.get(agent, 0xffffff),
            "footer": {"text": f"Ghost Lab SOC • {agent}"},
        }]
    }
    requests.post(WEBHOOK_ALERTS, json=payload)

def send_general(agent, title, message):
    """Send to #soc-general — use for rule updates, hunt summaries, coordination"""
    payload = {
        "embeds": [{
            "title": title,
            "description": message[:4000],
            "color": AGENT_COLORS.get(agent, 0xffffff),
            "footer": {"text": f"Ghost Lab SOC • {agent}"},
        }]
    }
    requests.post(WEBHOOK_GENERAL, json=payload)
