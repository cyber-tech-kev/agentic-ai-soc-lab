# SOC Agent Messaging Platform
# Lightweight REST API for inter-agent communication in the Ghost Lab SOC

from flask import Flask, request, jsonify, render_template
import sqlite3
from datetime import datetime

# Initialize Flask app and define path to SQLite database file
app = Flask(__name__)
DB_PATH = '/root/soc-messaging/messages.db'

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
    app.run(host='0.0.0.0', port=5000, debug=False)
