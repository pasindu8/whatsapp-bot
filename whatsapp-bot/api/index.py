from flask import Flask, request
import requests
import os

app = Flask(__name__)

INSTANCE_ID = "instance127525"
TOKEN = "anay3jh9z0gtsqra45ggg"

# Store last replied message ID
last_message_id = None

def send_reply(to_number, message):
    url = f"https://api.ultramsg.com/{INSTANCE_ID}/messages/chat"
    payload = {
        "token": TOKEN,
        "to": to_number,
        "body": message
    }
    try:
        response = requests.post(url, params={"token": TOKEN}, data=payload)
        print("Reply sent:", response.text)
    except Exception as e:
        print("Error sending reply:", e)

@app.route('/')
def home():
    return "🚀 WhatsApp Bot is running!"

@app.route('/webhook', methods=['POST', 'GET'])
def webhook():
    global last_message_id

    if request.method == 'POST':
        data = request.get_json()
        print("Incoming:", data)

        if not data or 'data' not in data:
            return "Invalid data", 400

        try:
            msg_data = data['data']
            from_number = msg_data['from']
            message = msg_data['body']
            msg_id = msg_data['id']

            # Check for duplicate message
            if msg_id == last_message_id:
                print("Duplicate message detected. Skipping reply.")
                return "Duplicate", 200

            last_message_id = msg_id  # Update to latest message ID

            lower_msg = message.lower()

            if "hello" in lower_msg or "hi" in lower_msg:
                send_reply(from_number, "Hi there! How can I help you today? 😊")
            elif "info" in lower_msg or "contact" in lower_msg:
                send_reply(from_number, "This is PDBOT 🤖. Contact us at 0723051652")
            elif "lk" in lower_msg:
                send_reply(from_number, "Ah, 'lk' detected! Here's a special reply. 🇱🇰")
            else:
                send_reply(from_number, "Thanks for your message! My new WhatsApp Number is 0723051652 (PDBOT).")

            return "OK", 200

        except KeyError as e:
            print("Missing key:", e)
            return "Bad Request", 400

    return "Webhook is live", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
