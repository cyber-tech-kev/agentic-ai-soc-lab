# Incident Report — pFt03p8BP1NDKOS3_h73

## Alert Name
Logon Failure - Unknown user or bad password

## Entities Involved
Agent: WORKSTATION-01

## Actions Taken
1) Check Wazuh/Windows Security log (Event ID 4625) on WORKSTATION-01 for the actual username and source workstation/IP tied to this failure — the alert itself didn't capture it. 2) Query for repeat failures against the same or multiple accounts from this host in the last 24h; a single hit isn't actionable but a burst or spray pattern would be. 3) If a source IP does surface, check whether it's 192.168.100.50 (Kali) or touches 192.168.100.2 (Metasploitable) — if so, escalate and flip this to a TP. 4) No user notification or account lockout needed at this severity unless correlation turns something up. Close as BP pending any repeat occurrences.

## Classification
BP

## Closure Statement
This is about as low-signal as alerts get — severity 5/15 (bottom third of the scale), no source IP captured, and the Full Log field is literally empty. A single 'unknown user or bad password' logon failure is one of the most common noise events in any Windows environment: fat-fingered passwords, stale saved creds, a scheduled task running with an old password, someone's phone trying to sync mail with an outdated PIN. The MITRE mapping to T1531 (Account Access Removal / Impact) is also a stretch — that technique is about deliberately locking legitimate users out of accounts, not a single failed logon, so I wouldn't weight that tag heavily here. Without a source IP, a username, or a pattern of repeated failures, there's nothing pointing to brute-forcing, credential stuffing, or targeted access abuse. It reads as routine background noise rather than an attack in progress.

## Timestamp
2026-08-07T19:12:59.621181
