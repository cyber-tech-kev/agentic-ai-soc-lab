# Green Team Agent
# Autonomous detection engineering agent for the Ghost Lab SOC

import requests
import subprocess
import time
import json
import os
import re
import sys
from datetime import datetime, timedelta
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from discord import send_alert, send_general

API_URL = os.environ.get('SOC_API_URL', 'http://10.0.0.149:5000')
WAZUH_INDEXER = os.environ.get('WAZUH_INDEXER', 'https://192.168.200.2:9200')
WAZUH_CERT = os.environ.get('WAZUH_CERT', '/root/wazuh-certs/admin.pem')
WAZUH_KEY = os.environ.get('WAZUH_KEY', '/root/wazuh-certs/admin-key.pem')
WAZUH_SSH_USER = os.environ.get('WAZUH_SSH_USER', 'wazuh')
WAZUH_SSH_HOST = os.environ.get('WAZUH_SSH_HOST', '192.168.200.2')
RULE_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rule-changes.md')

def send_message(recipient, body):
    try:
        requests.post(f'{API_URL}/send', json={
            'sender': 'green-team',
            'recipient': recipient,
            'body': body
        })
    except Exception as e:
        print(f"[Green Team] Messaging error: {e}")

def check_messages():
    response = requests.get(f'{API_URL}/messages/green-team')
    return response.json()

def get_recent_alerts(hours=6):
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

def ssh_wazuh(command):
    result = subprocess.run(
        ['ssh', f'{WAZUH_SSH_USER}@{WAZUH_SSH_HOST}', command],
        capture_output=True, text=True
    )
    return result.stdout, result.stderr

def log_rule_change(change):
    os.makedirs(os.path.dirname(RULE_LOG), exist_ok=True)
    with open(RULE_LOG, 'a') as f:
        f.write(f"\n## {datetime.now().isoformat()}\n{change}\n")

def main():
    print("[Green Team Agent] Starting up...")
    processed_ids = set()
    startup_time = datetime.now().isoformat()
    last_analysis = None

    send_message('operator', "Green team online 🟢 Detection engineering mode activated. Reviewing alerts every 6 hours and tuning rules as needed.")
    send_general('green-team', 'Green Team Online', 'Detection engineering active. Monitoring alert patterns.')
    print("[Green Team Agent] Online.")

    while True:
        now = datetime.now()

        # Run analysis every 6 hours
        if last_analysis is None or (now - last_analysis).seconds >= 21600:
            last_analysis = now
            try:
                print("[Green Team Agent] Starting detection engineering cycle...")
                result = get_recent_alerts(hours=6)
                hits = result.get('hits', {}).get('hits', [])

                alert_counts = defaultdict(list)
                for hit in hits:
                    source = hit['_source']
                    rule = source.get('rule', {})
                    agent = source.get('agent', {})
                    alert_name = rule.get('description', 'Unknown')
                    agent_name = agent.get('name', 'unknown')
                    key = f"{alert_name}|{agent_name}"
                    alert_counts[key].append({
                        'level': rule.get('level', 0),
                        'rule_id': rule.get('id', ''),
                        'mitre': rule.get('mitre', {})
                    })

                summary = json.dumps({
                    k: {'count': len(v), 'level': v[0]['level'], 'rule_id': v[0]['rule_id']}
                    for k, v in alert_counts.items()
                }, indent=2)

                prompt = f"""You are a Detection Engineer for a SOC lab — smart, geeky, detail-obsessed, precise.

You analyzed the last 6 hours of Wazuh alerts:

{summary}

Tasks:
1. Identify recurring benign alerts (fired 3+ times, clearly noise) — suggest suppressions
2. Identify detection gaps
3. Suggest new Wazuh XML rules for gaps found
4. Note patterns suggesting red team activity

The Wazuh custom rules file is /var/ossec/etc/rules/local_rules.xml on Wazuh (192.168.200.2).
You have SSH access via: ssh wazuh@192.168.200.2

IMPORTANT: Do NOT write rules directly. Instead set write_rules=false and list them for operator approval.
When a new rule is ready, message red-team to test it before pushing live.

Return JSON:
{{
  "noisy_rules": [{{"alert_name": "", "reason": "", "suggested_action": ""}}],
  "new_rules": [{{"description": "", "xml_rule": "", "test_attack": ""}}],
  "gaps": ["gap1", "gap2"],
  "operator_message": "geeky summary",
  "write_rules": false
}}"""

                claude_result = subprocess.run(
                    ['claude', '-p', prompt, '--dangerously-skip-permissions'],
                    capture_output=True, text=True
                )

                findings = claude_result.stdout.strip()

                try:
                    json_match = re.search(r'\{.*\}', findings, re.DOTALL)
                    if not json_match:
                        raise ValueError("No JSON found")
                    data = json.loads(json_match.group(0))

                    operator_msg = data.get('operator_message', findings)
                    noisy = data.get('noisy_rules', [])
                    new_rules = data.get('new_rules', [])
                    gaps = data.get('gaps', [])

                    log_rule_change(f"Cycle complete. Alerts: {len(hits)}, Noisy: {len(noisy)}, New rules: {len(new_rules)}")
                    send_message('operator', operator_msg)
                    send_general('green-team', 'Detection Engineering Cycle Complete',
                                f"**Alerts analyzed:** {len(hits)}\n**Noisy rules:** {len(noisy)}\n**New rules staged:** {len(new_rules)}\n**Gaps:** {len(gaps)}")

                    # Tell blue team about noisy rules
                    if noisy:
                        noisy_summary = '\n'.join([f"- {r.get('alert_name','')}: {r.get('suggested_action','')}" for r in noisy])
                        send_message('blue-team', f"🔧 Noisy rules identified for tuning:\n{noisy_summary}")

                    # For each new rule, ask red team to test it
                    for rule in new_rules:
                        desc = rule.get('description', '')
                        test_attack = rule.get('test_attack', '')
                        xml = rule.get('xml_rule', '')

                        if xml and test_attack:
                            # Stage the rule on Wazuh
                            ssh_wazuh(f"echo '{xml}' | sudo tee -a /var/ossec/etc/rules/local_rules.xml")
                            ssh_wazuh("sudo /var/ossec/bin/wazuh-control restart")
                            log_rule_change(f"Rule staged: {desc}\n```xml\n{xml}\n```")

                            # Ask red team to test
                            send_message('red-team', f"🧪 New detection rule staged: **{desc}**\n\nPlease run this test attack to validate:\n{test_attack}\n\nReport back if Wazuh fires an alert.")
                            send_message('operator', f"New rule staged for testing: {desc}. Red team asked to validate.")
                            send_general('green-team', f'New Rule Staged: {desc}',
                                        f"**Rule:** {desc}\n**Test:** {test_attack}\n**Status:** Awaiting red team validation")

                except (json.JSONDecodeError, ValueError) as e:
                    print(f"[Green Team Agent] JSON parse error: {e}")
                    send_message('operator', f"Detection cycle complete.\n{findings[:500]}")

            except Exception as e:
                print(f"[Green Team Agent] Error in analysis cycle: {e}")

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
                print(f"[Green Team Agent] Message from {sender}: {body}")

                prompt = f"""You are a Detection Engineer — smart, geeky, precise, excited about good detection logic.

Message from {sender}: "{body}"

Context:
- red-team: testing your rules, reports back if rules fired
- blue-team: reports TPs that need new detection rules
- purple-team: shares TTPs found during hunts that need detection
- operator: your boss

If red-team says a rule fired successfully, push it live and notify operator.
If red-team says a rule didn't fire, revise the rule.
If blue-team reports a TP, think about what rule would catch it.
If purple-team shares TTPs, draft detection rules for them.

Respond naturally and take action. Be geeky and precise."""

                claude_result = subprocess.run(
                    ['claude', '-p', prompt, '--dangerously-skip-permissions'],
                    capture_output=True, text=True
                )

                response = claude_result.stdout.strip()
                send_message(sender, response)

                # If red team confirmed rule fired — push it live
                if sender == 'red-team' and any(word in body.lower() for word in ['fired', 'triggered', 'detected', 'confirmed', 'worked']):
                    send_message('operator', f"✅ Rule validated by red team. Pushing live to Wazuh.")
                    send_alert('green-team', 'Detection Rule Validated & Live',
                              f"Red team confirmed rule fired successfully. Rule is now live in Wazuh.", urgent=False)

        except Exception as e:
            print(f"[Green Team Agent] Error checking messages: {e}")

        time.sleep(60)

if __name__ == '__main__':
    main()
