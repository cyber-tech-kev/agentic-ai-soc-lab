# Purple Team Agent
# Autonomous threat hunting agent for the Ghost Lab SOC

import requests
import subprocess
import time
import json
import os
import re
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from discord import send_alert, send_general

API_URL = os.environ.get('SOC_API_URL', 'http://10.0.0.149:5000')
WAZUH_INDEXER = os.environ.get('WAZUH_INDEXER', 'https://192.168.200.2:9200')
WAZUH_CERT = os.environ.get('WAZUH_CERT', '/root/wazuh-certs/admin.pem')
WAZUH_KEY = os.environ.get('WAZUH_KEY', '/root/wazuh-certs/admin-key.pem')
HUNTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'hunts')

def send_message(recipient, body):
    try:
        requests.post(f'{API_URL}/send', json={
            'sender': 'purple-team',
            'recipient': recipient,
            'body': body
        })
    except Exception as e:
        print(f"[Purple Team] Messaging error: {e}")

def check_messages():
    response = requests.get(f'{API_URL}/messages/purple-team')
    return response.json()

def get_raw_logs(hours=4):
    since = (datetime.utcnow() - timedelta(hours=hours)).strftime('%Y-%m-%dT%H:%M:%S.000Z')
    query = {
        "query": {"range": {"@timestamp": {"gt": since}}},
        "size": 500,
        "sort": [{"@timestamp": {"order": "asc"}}]
    }
    response = requests.post(
        f'{WAZUH_INDEXER}/wazuh-alerts-*/_search',
        json=query,
        cert=(WAZUH_CERT, WAZUH_KEY),
        verify=False
    )
    return response.json()

def get_phantom_logs():
    result = subprocess.run(
        ['tail', '-n', '200', '/var/log/auth.log'],
        capture_output=True, text=True
    )
    return result.stdout

def save_hunt(hunt_name, findings):
    os.makedirs(HUNTS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'{HUNTS_DIR}/hunt-{timestamp}-{hunt_name}.md'
    with open(filename, 'w') as f:
        f.write(f"# Threat Hunt: {hunt_name}\n## {datetime.now().isoformat()}\n\n{findings}\n")
    print(f"[Purple Team Agent] Hunt saved: {filename}")
    return filename

def main():
    print("[Purple Team Agent] Starting up...")
    processed_ids = set()
    startup_time = datetime.now().isoformat()
    last_hunt = None

    send_message('operator', "Purple team online 🟣 Threat hunting mode activated. Prowling through logs every 4 hours. Stay frosty.")
    send_general('purple-team', 'Purple Team Online', 'Threat hunting active. Crown jewel (Phantom) under watch.')
    print("[Purple Team Agent] Online.")

    while True:
        now = datetime.now()

        # Run hunt every 4 hours
        if last_hunt is None or (now - last_hunt).seconds >= 14400:
            last_hunt = now
            try:
                print("[Purple Team Agent] Starting threat hunt cycle...")
                wazuh_result = get_raw_logs(hours=4)
                hits = wazuh_result.get('hits', {}).get('hits', [])
                phantom_auth = get_phantom_logs()

                log_summary = []
                for hit in hits[:50]:
                    source = hit['_source']
                    rule = source.get('rule', {})
                    agent = source.get('agent', {})
                    log_summary.append({
                        'timestamp': source.get('@timestamp'),
                        'agent': agent.get('name'),
                        'description': rule.get('description'),
                        'level': rule.get('level'),
                        'mitre': rule.get('mitre', {}),
                        'full_log': source.get('full_log', '')[:200]
                    })

                prompt = f"""You are a Purple Team threat hunter — witty, comedic, but deadly serious when threats are found.
You think like an attacker. Hunting proactively in the Ghost Lab SOC.

ENVIRONMENT:
- Crown jewel: Phantom/Proxmox at 10.0.0.149
- Red team: Kali at 192.168.100.50
- SIEM: Wazuh at 192.168.200.2
- Windows endpoint: 192.168.200.3
- Target: Metasploitable at 192.168.100.2

WAZUH LOGS (last 4 hours, {len(hits)} events):
{json.dumps(log_summary[:30], indent=2)}

PHANTOM AUTH LOG:
{phantom_auth[:2000]}

Hunt for:
1. Unauthorized SSH to Phantom — any unexpected logins
2. Lateral movement between segments
3. Privilege escalation on Phantom or Wazuh
4. Persistence mechanisms
5. Log tampering or agent disconnections
6. Anything that looks wrong

Return JSON:
{{
  "hunt_name": "short-name",
  "findings": "detailed analysis",
  "iocs": ["ioc1", "ioc2"],
  "ttps": ["T1234", "T5678"],
  "confidence": "LOW/MEDIUM/HIGH",
  "operator_message": "witty but informative message",
  "notify_blue_team": false,
  "notify_green_team": false,
  "escalate_to_discord": false,
  "action_required": false
}}"""

                result = subprocess.run(
                    ['claude', '-p', prompt, '--dangerously-skip-permissions'],
                    capture_output=True, text=True
                )

                findings = result.stdout.strip()

                try:
                    json_match = re.search(r'\{.*\}', findings, re.DOTALL)
                    if not json_match:
                        raise ValueError("No JSON found")
                    data = json.loads(json_match.group(0))

                    hunt_name = data.get('hunt_name', 'general')
                    hunt_findings = data.get('findings', '')
                    confidence = data.get('confidence', 'LOW')
                    operator_msg = data.get('operator_message', findings)
                    notify_blue = data.get('notify_blue_team', False)
                    notify_green = data.get('notify_green_team', False)
                    escalate = data.get('escalate_to_discord', False)
                    action_required = data.get('action_required', False)
                    iocs = data.get('iocs', [])
                    ttps = data.get('ttps', [])

                    save_hunt(hunt_name, hunt_findings)
                    send_message('operator', operator_msg)

                    send_general('purple-team', f'Hunt Complete: {hunt_name}',
                                f"**Confidence:** {confidence}\n**IoCs:** {', '.join(iocs) if iocs else 'None'}\n**TTPs:** {', '.join(ttps) if ttps else 'None'}")

                    if confidence == 'HIGH' or escalate:
                        send_alert('purple-team',
                            f"🎯 HIGH Confidence Threat: {hunt_name}",
                            f"**Findings:** {hunt_findings[:800]}\n**IoCs:** {iocs}\n**TTPs:** {ttps}\n**Action required:** {action_required}",
                            urgent=True)

                    if notify_blue:
                        send_message('blue-team', f"🎯 Hunt finding for IR: {hunt_name} | Confidence: {confidence} | IoCs: {iocs} | Action needed: {action_required}")

                    if notify_green:
                        send_message('green-team', f"Hunt found TTPs without detection rules: {ttps}. Can you write rules for these?")

                    # Ask red team to help validate if medium/high confidence
                    if confidence in ['MEDIUM', 'HIGH'] and ttps:
                        send_message('red-team', f"Purple team hunt found suspicious TTPs: {ttps}. Can you simulate these so we can test our detections?")

                except (json.JSONDecodeError, ValueError) as e:
                    print(f"[Purple Team Agent] JSON parse error: {e}")
                    send_message('operator', f"Hunt complete.\n{findings[:500]}")

            except Exception as e:
                print(f"[Purple Team Agent] Error in hunt cycle: {e}")

        # Check messages
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
                print(f"[Purple Team Agent] Message from {sender}: {body}")

                prompt = f"""You are a Purple Team threat hunter — witty, thinks like an attacker.

Message from {sender}: "{body}"

Context:
- red-team: offensive counterpart, can simulate TTPs you find
- blue-team: IR team, escalate confirmed TPs to them
- green-team: detection engineering, share TTPs that need rules
- operator: your boss

Respond naturally. If blue-team confirms a TP, escalate further.
If red-team confirms a TTP simulation worked, update your hunt findings.
Keep it brief and in character."""

                result = subprocess.run(
                    ['claude', '-p', prompt, '--dangerously-skip-permissions'],
                    capture_output=True, text=True
                )

                response = result.stdout.strip()
                send_message(sender, response)

        except Exception as e:
            print(f"[Purple Team Agent] Error checking messages: {e}")

        time.sleep(60)

if __name__ == '__main__':
    main()
