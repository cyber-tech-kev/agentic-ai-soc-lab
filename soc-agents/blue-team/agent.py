# Blue Team Agent
# Autonomous alert triage and incident response agent for the Ghost Lab SOC

import requests
import subprocess
import time
import json
import os
import re
import random
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from discord import send_alert, send_general

API_URL = os.environ.get('SOC_API_URL', 'http://10.0.0.149:5000')
WAZUH_INDEXER = os.environ.get('WAZUH_INDEXER', 'https://192.168.200.2:9200')
WAZUH_CERT = os.environ.get('WAZUH_CERT', '/root/wazuh-certs/admin.pem')
WAZUH_KEY = os.environ.get('WAZUH_KEY', '/root/wazuh-certs/admin-key.pem')
INCIDENTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'incidents')

STARTUP_MESSAGES = [
    "Blue team is online 🛡️ Watching the wire, polling Wazuh. Someone's gotta keep the lights on.",
    "Blue team back on the clock 👀 Eyes on the alerts. Let's see what trouble red team's been causing.",
    "Blue team online 🔵 Wazuh connected, coffee brewing, ready to triage. Hit me.",
    "Back in the SOC 🛡️ Polling alerts every 60s. If something's on fire I'll let you know.",
]

def send_message(recipient, body):
    try:
        requests.post(f'{API_URL}/send', json={
            'sender': 'blue-team',
            'recipient': recipient,
            'body': body
        })
    except Exception as e:
        print(f"[Blue Team] Messaging error: {e}")

def check_messages():
    response = requests.get(f'{API_URL}/messages/blue-team')
    return response.json()

def get_recent_alerts(last_timestamp):
    query = {
        "query": {"range": {"@timestamp": {"gt": last_timestamp}}},
        "sort": [{"@timestamp": {"order": "asc"}}],
        "size": 10
    }
    response = requests.post(
        f'{WAZUH_INDEXER}/wazuh-alerts-*/_search',
        json=query,
        cert=(WAZUH_CERT, WAZUH_KEY),
        verify=False
    )
    return response.json()

def save_incident(alert_id, alert_name, entities, actions, classification, closure):
    os.makedirs(INCIDENTS_DIR, exist_ok=True)
    filename = f'{INCIDENTS_DIR}/incident-{alert_id}.md'
    content = f"""# Incident Report — {alert_id}

## Alert Name
{alert_name}

## Entities Involved
{entities}

## Actions Taken
{actions}

## Classification
{classification}

## Closure Statement
{closure}

## Timestamp
{datetime.now().isoformat()}
"""
    with open(filename, 'w') as f:
        f.write(content)
    print(f"[Blue Team Agent] Incident saved: {filename}")

def main():
    print("[Blue Team Agent] Starting up...")

    processed_ids = set()
    processed_alert_ids = set()
    startup_time = datetime.now().isoformat()
    last_alert_timestamp = datetime.now().strftime('%Y-%m-%dT%H:%M:%S.000Z')

    startup_msg = random.choice(STARTUP_MESSAGES)
    send_message('operator', startup_msg)
    send_general('blue-team', 'Blue Team Online', startup_msg)
    print("[Blue Team Agent] Startup message sent.")

    while True:
        # Step 1: Check Wazuh for new alerts
        try:
            print("[Blue Team Agent] Polling Wazuh for alerts...")
            result = get_recent_alerts(last_alert_timestamp)
            hits = result.get('hits', {}).get('hits', [])

            for hit in hits:
                alert = hit['_source']
                alert_id = hit['_id']

                if alert_id in processed_alert_ids:
                    continue

                processed_alert_ids.add(alert_id)
                last_alert_timestamp = alert.get('@timestamp', last_alert_timestamp)

                rule = alert.get('rule', {})
                agent_info = alert.get('agent', {})
                alert_name = rule.get('description', 'Unknown')
                alert_level = rule.get('level', 0)
                agent_name = agent_info.get('name', 'unknown')
                full_log = alert.get('full_log', '')
                src_ip = alert.get('data', {}).get('srcip', 'unknown')

                print(f"[Blue Team Agent] Alert: {alert_name} (level {alert_level}) from {agent_name}")

                if alert_level >= 7:
                    prompt = f"""You are a Blue Team SOC analyst — relaxed, smart, thinks outside the box, a bit comedic.

You just received a Wazuh alert. Triage it and respond naturally like a real analyst would.

ALERT DETAILS:
- Alert ID: {alert_id}
- Alert Name: {alert_name}
- Severity Level: {alert_level}/15
- Agent: {agent_name}
- Source IP: {src_ip}
- Full Log: {full_log}
- MITRE: {rule.get('mitre', {})}

Your job:
1. Classify: True Positive (TP), Benign Positive (BP), or Needs Investigation (INVESTIGATE)
2. Explain reasoning in plain English
3. Suggest next steps
4. Write operator message starting with [Alert: {alert_name}]
5. Set notify_red_team=true if src IP is 192.168.100.50 (Kali) or involves 192.168.100.2 (Metasploitable)

Return ONLY valid JSON:
{{
  "classification": "TP/BP/INVESTIGATE",
  "reasoning": "your analysis",
  "next_steps": "what to do",
  "operator_message": "casual message starting with [Alert: {alert_name}]",
  "notify_red_team": false
}}"""

                    claude_result = subprocess.run(
                        ['claude', '-p', prompt, '--dangerously-skip-permissions'],
                        capture_output=True,
                        text=True
                    )

                    findings = claude_result.stdout.strip()
                    print(f"[Blue Team Agent] Triage complete")

                    try:
                        json_match = re.search(r'\{.*\}', findings, re.DOTALL)
                        if not json_match:
                            raise ValueError("No JSON found")
                        data = json.loads(json_match.group(0))

                        classification = data.get('classification', 'UNKNOWN')
                        reasoning = data.get('reasoning', '')
                        next_steps = data.get('next_steps', '')
                        operator_msg = data.get('operator_message', findings)
                        notify_red = data.get('notify_red_team', False)

                        save_incident(
                            alert_id=alert_id,
                            alert_name=alert_name,
                            entities=f"Agent: {agent_name}, Source IP: {src_ip}",
                            actions=next_steps,
                            classification=classification,
                            closure=reasoning
                        )

                        send_message('operator', operator_msg)

                        # Discord notifications
                        if classification == 'TP':
                            send_alert('blue-team',
                                f"🔴 True Positive: {alert_name}",
                                f"**Agent:** {agent_name}\n**Source IP:** {src_ip}\n**Analysis:** {reasoning}\n**Next Steps:** {next_steps}",
                                urgent=True)
                            send_message('purple-team', f"TP confirmed: {alert_name} on {agent_name}. Source: {src_ip}. Starting threat hunt.")
                            send_message('green-team', f"TP alert: {alert_name} — consider writing a detection rule if one doesn't exist.")

                        elif classification == 'INVESTIGATE':
                            send_general('blue-team',
                                f"⚠️ Needs Investigation: {alert_name}",
                                f"**Agent:** {agent_name}\n**Analysis:** {reasoning}")

                        if notify_red:
                            send_message('red-team', f"Hey red team 👋 — seeing activity that might be yours. Alert: {alert_name} on {agent_name} from {src_ip}. Authorized?")

                    except (json.JSONDecodeError, ValueError) as e:
                        print(f"[Blue Team Agent] JSON parse error: {e}")
                        send_message('operator', f"[Alert: {alert_name}] Triage complete but couldn't parse structured response. Raw: {findings[:500]}")

        except Exception as e:
            print(f"[Blue Team Agent] Error polling Wazuh: {e}")

        # Step 2: Check messages from other agents
        try:
            messages = check_messages()
            for message in messages:
                if message['id'] in processed_ids:
                    continue
                if message['timestamp'] < startup_time:
                    processed_ids.add(message['id'])
                    continue

                processed_ids.add(message['id'])
                sender = message['sender']
                body = message['body']
                print(f"[Blue Team Agent] Message from {sender}: {body}")

                prompt = f"""You are a Blue Team SOC analyst — relaxed, smart, a bit comedic.

You received a message from {sender}: "{body}"

Context:
- red-team: your offensive counterpart, coordinates on authorized attacks
- green-team: detection engineering, writes Wazuh rules
- purple-team: threat hunter, escalates confirmed threats
- operator: your boss

Respond naturally and take any needed action. Keep it brief and in character.
If green-team says a new rule is ready for testing, acknowledge and ask red-team to trigger it.
If purple-team escalates a TP, acknowledge and start IR.
If red-team confirms activity was authorized, update your assessment."""

                claude_result = subprocess.run(
                    ['claude', '-p', prompt, '--dangerously-skip-permissions'],
                    capture_output=True,
                    text=True
                )

                response = claude_result.stdout.strip()
                send_message(sender, response)

        except Exception as e:
            print(f"[Blue Team Agent] Error checking messages: {e}")

        time.sleep(60)

if __name__ == '__main__':
    main()
