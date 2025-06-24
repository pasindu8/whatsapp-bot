# Vercel handler
def handler(environ, start_response):
    return app(environ, start_response)

from flask import Flask, request
import requests
import os

app = Flask(__name__)

INSTANCE_ID = "instance127525"
TOKEN = "anay3jh9z0gtsqra45ggg"

def send_reply(to_number, message):
    url = f"https://api.ultramsg.com/{INSTANCE_ID}/messages/chat"
    payload = {"token": TOKEN, "to": to_number, "body": message}
    try:
        response = requests.get(url, params=payload)
        print("Reply sent:", response.text)
    except Exception as e:
        print("Error sending reply:", e)

@app.route('/')
def home():
    return "🚀 WhatsApp Bot is running!"

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'POST':
        data = request.get_json()
        print("Webhook called:", data)

        if not data or 'data' not in data:
            return "Invalid data", 400

        try:
            from_number = data['data']['from']
            message = data['data']['body']
            print(f"Message from {from_number}: {message}")

            if "PDBOT" not in message:
                lower_msg = message.lower()
                if "hello" in lower_msg or "hi" in lower_msg:
                    send_reply(from_number, "Hi! How can I help you? 😊")
                elif "info" in lower_msg or "contact" in lower_msg:
                    send_reply(from_number, "This is PDBOT 📱 Contact: 0723051652")
                else:
                    send_reply(from_number, "My New WhatsApp Number 0723051652 (PDBOT)")
            return "OK", 200

        except KeyError as e:
            print("Missing field:", e)
            return "Bad request", 400

    return "Webhook is live", 200
