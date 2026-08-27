# SOC Agent Messaging Platform
# Lightweight REST API for inter-agent communication in the Ghost Lab SOC

from flask import Flask, request, jsonify, render_template
import sqlite3
from datetime import datetime
import os
from pathlib import Path

# Initialize Flask app and define path to SQLite database file
app = Flask(__name__)
# ── Config ────────────────────────────────────────────────
# Values come from the environment (see .env.example).
# systemd injects them via EnvironmentFile=; for manual runs,
# export them or use `set -a; . .env; set +a`.

# Where the SQLite DB lives. Defaults to messages.db beside this file.
DB_PATH = os.environ.get(
    'SOC_DB_PATH',
    str(Path(__file__).resolve().parent / 'messages.db')
)

# Interface the server binds to.
# 127.0.0.1  = local only (safe default)
# 100.x.x.x  = a Tailscale address, if you view the dashboard remotely
# 0.0.0.0    = every interface, including your lab segments. Don't.
BIND_HOST = os.environ.get('SOC_BIND_HOST', '127.0.0.1')
BIND_PORT = int(os.environ.get('SOC_BIND_PORT', '5000'))

@app.route('/')
def dashboard():
    return render_template('dashboard.html')

# Create the messages table if it doesn't already exist
def initialize_database():
    conn = sqlite3.connect(DB_PATH)      # Open connection to the database
    cursor = conn.cursor()               # Create cursor to run SQL commands
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT NOT NULL,
            recipient TEXT NOT NULL,
            body TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    ''')
    conn.commit()                        # Save changes
    conn.close()                         # Free the connection

# Endpoint for agents to send a message
@app.route('/send', methods=['POST'])
def send_message():
    data = request.get_json()            # Read JSON body from the request
    sender = data['sender']
    recipient = data['recipient']
    body = data['body']
    timestamp = datetime.now().isoformat()  # Generate timestamp automatically

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO messages (sender, recipient, body, timestamp)
        VALUES (?, ?, ?, ?)
    ''', (sender, recipient, body, timestamp))
    conn.commit()
    conn.close()

    return jsonify({'status': 'sent'}), 200  # Confirm message was saved

# Endpoint for agents to retrieve messages by recipient
@app.route('/messages/<recipient>', methods=['GET'])
def get_messages(recipient):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, sender, recipient, body, timestamp
        FROM messages
        WHERE recipient = ? OR recipient = 'all'
        ORDER BY timestamp ASC
    ''', (recipient,))

    rows = cursor.fetchall()
    conn.close()

    # Format results as a list of message dictionaries
    messages = []
    for row in rows:
        messages.append({
            'id': row[0],
            'sender': row[1],
            'recipient': row[2],
            'body': row[3],
            'timestamp': row[4]
        })

    return jsonify(messages), 200

# Endpoint to retrieve all messages for the dashboard
@app.route('/messages', methods=['GET'])
def get_all_messages():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, sender, recipient, body, timestamp
        FROM messages
        ORDER BY timestamp ASC
    ''')
    rows = cursor.fetchall()
    conn.close()

    messages = []
    for row in rows:
        messages.append({
            'id': row[0],
            'sender': row[1],
            'recipient': row[2],
            'body': row[3],
            'timestamp': row[4]
        })

    return jsonify(messages), 200

# Initialize the database on startup
initialize_database()

# Start the Flask server
if __name__ == '__main__':
    app.run(host=BIND_HOST, port=BIND_PORT, debug=False)
