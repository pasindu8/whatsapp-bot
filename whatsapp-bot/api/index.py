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
        # requests.get වෙනුවට requests.post භාවිතා කරන්න, params=payload වෙනුවට data=payload
        response = requests.post(url, data=payload) # <--- නිවැරදි කළ පේළිය
        print("Reply sent:", response.text)
        # ඔබට response එකේ status code එකත් පරීක්ෂා කිරීමට පුළුවන්
        response.raise_for_status() # 4xx හෝ 5xx වැනි වැරදි responses සඳහා HTTPError එකක් ඇති කරයි
    except requests.exceptions.RequestException as e:
        print(f"Error sending reply (RequestException): {e}")
    except Exception as e:
        print(f"An unexpected error occurred while sending reply: {e}")

@app.route('/')
def home():
    return "🚀 WhatsApp Bot is running!"

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'POST':
        data = request.get_json()
        print("Webhook called:", data)

        if not data or 'data' not in data:
            print("Invalid or missing 'data' key in webhook payload.")
            return "Invalid data", 400

        try:
            from_number = data['data']['from']
            message = data['data']['body']
            print(f"Message from {from_number}: {message}")

            # මේ condition එක සමාලෝචනය කරන්න: if "PDBOT" not in message:
            # ඔබට සියලුම messages වලට reply කිරීමට අවශ්‍ය නම්, මේ 'if' block එක ඉවත් කරන්න.
            # ඔබට 'PDBOT' message එකේ නැතිනම් පමණක් reply කිරීමට අවශ්‍ය නම්, මෙය තබා ගන්න.
            # එසේ නොමැතිව, ඔබට 'PDBOT' message එකේ තිබේ නම් පමණක් reply කිරීමට අවශ්‍ය නම්, 'if "PDBOT" in message:' ලෙස වෙනස් කරන්න.
            if "PDBOT" not in message:
                lower_msg = message.lower()
                if "hello" in lower_msg or "hi" in lower_msg:
                    send_reply(from_number, "Hi! How can I help you? 😊")
                elif "info" in lower_msg or "contact" in lower_msg:
                    send_reply(from_number, "This is PDBOT 📱 Contact: 0723051652")
                else:
                    send_reply(from_number, "My New WhatsApp Number 0723051652 (PDBOT)")
            else:
                # "PDBOT" message එකේ තිබේ නම්, කිසිවක් නොකිරීමට අවශ්‍ය නම්, මෙය ගැටලුවක් නොවේ.
                # එසේ නොමැතිනම්, "PDBOT" තිබෙන විට කළ යුතු දේ සඳහා logic මෙතනට එකතු කරන්න.
                print("Message contains 'PDBOT', not replying based on current logic.")

            return "OK", 200

        except KeyError as e:
            print(f"Missing field in webhook data: {e}. Full data: {data}")
            return "Bad request", 400
        except Exception as e:
            print(f"An unexpected error occurred in webhook processing: {e}. Data: {data}")
            return "Internal Server Error", 500

    # /webhook වෙත GET requests සඳහා
    return "Webhook is live", 200
