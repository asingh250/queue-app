from flask import Flask, request, jsonify, send_from_directory
import sqlite3
from datetime import datetime
from twilio.rest import Client
import os

app = Flask(__name__)
DATABASE = 'queue_system.db'

def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token_number TEXT,
            phone_number TEXT,
            created_at TEXT,
            notified INTEGER DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS queue_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            current_token_number TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.route('/token', methods=['POST'])
def generate_token():
    phone_number = request.json.get('phone_number')
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('SELECT token_number FROM tokens ORDER BY id DESC LIMIT 1')
    last = cursor.fetchone()
    last_number = int(last[0][1:]) if last else 99
    new_token = f"Q{last_number + 1}"
    cursor.execute(
        'INSERT INTO tokens (token_number, phone_number, created_at) VALUES (?, ?, ?)',
        (new_token, phone_number, datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()
    return jsonify({"token_number": new_token})

@app.route('/next', methods=['POST'])
def call_next():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('SELECT id, token_number FROM tokens WHERE notified = 0 ORDER BY id LIMIT 1')
    current = cursor.fetchone()
    if not current:
        return jsonify({"message": "No more tokens"}), 200

    current_id, current_token = current
    cursor.execute('REPLACE INTO queue_state (id, current_token_number) VALUES (1, ?)', (current_token,))

    notify_id = current_id + 5
    cursor.execute('SELECT phone_number FROM tokens WHERE id = ?', (notify_id,))
    notify = cursor.fetchone()

    if notify:
        phone_number = notify[0]
        try:
            client = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
            client.messages.create(
                body="You are 5 tokens away. Please be ready.",
                from_=os.getenv("TWILIO_PHONE_NUMBER"),
                to=phone_number
            )
        except Exception as e:
            print("Failed to send SMS:", e)

    cursor.execute('UPDATE tokens SET notified = 1 WHERE id = ?', (current_id,))
    conn.commit()
    conn.close()
    return jsonify({"called_token": current_token})

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

if __name__ == '__main__':
    app.run(debug=True)
