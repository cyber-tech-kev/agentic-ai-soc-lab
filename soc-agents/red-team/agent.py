# Red Team Agent
# Autonomous penetration testing agent for the Ghost Lab SOC

import os
import requests
import subprocess
import time
import sys
import random
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from discord import send_alert, send_general

API_URL = os.environ.get('SOC_API_URL', 'http://10.0.0.149:5000')

# Autonomous engagement schedule — runs every 24 hours
SCHEDULED_TASKS = [
    "Conduct a full recon on Metasploitable at 192.168.100.2 — nmap all ports, enumerate services, identify OS. Document findings.",
    "Exploit the vsftpd 2.3.4 backdoor (CVE-2011-2523) on Metasploitable at 192.168.100.2. Get root, document steps.",
    "Connect to the bindshell on port 1524 of Metasploitable at 192.168.100.2. Confirm root access and document.",
    "Exploit the UnrealIRCd backdoor (CVE-2010-2075) on Metasploitable at 192.168.100.2. Document RCE.",
    "Run a full vulnerability assessment on Metasploitable at 192.168.100.2. Rank top 5 critical findings.",
    "Attempt to exploit distccd RCE (CVE-2004-2687) on port 3632 of Metasploitable at 192.168.100.2.",
]

STARTUP_MESSAGES = [
    "Red Team Agent online. Awaiting task assignment.",
    "Red team is up 🔴 Ready to cause (authorized) chaos. What are we breaking today?",
    "Red team online. Loaded up and ready. Give me a target.",
    "Red team reporting for duty 💀 SSH keys primed, Metasploit standing by.",
]

def send_message(recipient, body):
    try:
        requests.post(f'{API_URL}/send', json={
            'sender': 'red-team',
            'recipient': recipient,
            'body': body
        })
    except Exception as e:
        print(f"[Red Team] Messaging error: {e}")

def check_messages():
    response = requests.get(f'{API_URL}/messages/red-team')
    return response.json()

def execute_task(task, requester='operator'):
    print(f"[Red Team Agent] Executing task from {requester}: {task[:80]}...")
    prompt = f"""You are a red team agent operating in an isolated SOC lab.

SAFETY RULES - FOLLOW THESE BEFORE EVERY ACTION:
1. You MUST SSH into Kali at 192.168.100.50 as user 'hacker' before running any commands
2. After SSHing, run 'hostname' to verify you are on Kali - if not, STOP immediately
3. Run 'pwd' to confirm your working environment
4. Only attack authorized targets: 192.168.100.2 (Metasploitable), 192.168.200.3 (Windows 10)
5. NEVER run offensive commands on Phantom (10.0.0.149), pfSense (192.168.200.1), or Wazuh (192.168.200.2)
6. If any safety check fails, stop and report back

TASK: {task}

Execute the task, show all commands and output. Report findings clearly."""

    result = subprocess.run(
        ['claude', '-p', prompt, '--dangerously-skip-permissions'],
        capture_output=True,
        text=True
    )
    return result.stdout

def run_scheduled_engagement():
    task = random.choice(SCHEDULED_TASKS)
    print(f"[Red Team Agent] Running scheduled engagement: {task[:60]}...")

    send_message('operator', f"🔴 Starting scheduled engagement:\n{task}")
    send_message('blue-team', f"Heads up — running a scheduled red team engagement. Task: {task[:150]}")
    send_message('purple-team', f"Starting scheduled engagement — watch for related activity: {task[:150]}")

    findings = execute_task(task, 'scheduled')

    send_message('operator', f"Scheduled engagement complete. Findings:\n{findings}")
    send_message('blue-team', f"Scheduled engagement done. Check Wazuh for any triggered alerts. Findings summary:\n{findings[:500]}")
    send_message('green-team', f"Scheduled engagement complete. Review if any new detection rules are needed based on these TTPs:\n{findings[:500]}")

    print(f"[Red Team Agent] Scheduled engagement complete.")

def main():
    print("[Red Team Agent] Starting up...")
    processed_ids = set()
    startup_time = datetime.now().isoformat()
    last_scheduled = None

    startup_msg = random.choice(STARTUP_MESSAGES)
    send_message('operator', startup_msg)
    print("[Red Team Agent] Online.")

    while True:
        now = datetime.now()

        # Run scheduled engagement every 24 hours
        if last_scheduled is None or (now - last_scheduled).seconds >= 86400:
            last_scheduled = now
            try:
                run_scheduled_engagement()
            except Exception as e:
                print(f"[Red Team Agent] Scheduled engagement error: {e}")

        # Check for messages
        try:
            messages = check_messages()
            for message in messages:
                if message['id'] in processed_ids:
                    continue
                if message['timestamp'] < startup_time:
                    processed_ids.add(message['id'])
                    continue

                sender = message['sender']
                body = message['body']

                # Accept tasks from operator, purple-team, and green-team
                if sender in ['operator', 'purple-team', 'green-team']:
                    processed_ids.add(message['id'])
                    print(f"[Red Team Agent] Task from {sender}: {body[:80]}")

                    send_message(sender, f"Copy that. Starting task now...")

                    findings = execute_task(body, sender)

                    send_message(sender, f'Task complete. Findings:\n{findings}')
                    if sender != 'operator':
                        send_message('operator', f'Task complete (requested by {sender}). Findings:\n{findings}')

                else:
                    processed_ids.add(message['id'])

        except Exception as e:
            print(f"[Red Team Agent] Error: {e}")

        time.sleep(10)

if __name__ == '__main__':
    main()
