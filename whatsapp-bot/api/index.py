from flask import Flask, request
import requests
import os

app = Flask(__name__)

INSTANCE_ID = "instance127525"
TOKEN = "anay3jh9z0gtsqra45ggg" # ඔබේ සත්‍ය token එක

def send_reply(to_number, message):
    # chat message API එක සඳහා මූලික URL එක
    base_url = f"https://api.ultramsg.com/{INSTANCE_ID}/messages/chat"

    # URL එකට යන parameters (query string)
    # Ultramsg හි දෝෂ පණිවිඩය අනුව 'token' එක මෙතන තිබිය යුතුයි
    url_params = {"token": TOKEN}

    # POST request body එකට යන data
    post_data = {"to": to_number, "body": message}

    try:
        # requests.post භාවිතා කරන්න
        # url_params 'params' ලෙස යවන්න (URL query string සඳහා)
        # post_data 'data' ලෙස යවන්න (request body සඳහා)
        response = requests.post(base_url, params=url_params, data=post_data)
        
        print("Ultramsg API Response:", response.text) # Ultramsg වෙතින් ලැබෙන සම්පූර්ණ ප්‍රතිචාරය print කරන්න
        response.raise_for_status() # 4xx හෝ 5xx වැනි වැරදි responses සඳහා HTTPError එකක් ඇති කරයි
        print("Reply sent successfully to Ultramsg!")

    except requests.exceptions.HTTPError as errh:
        print(f"HTTP Error occurred: {errh} - Response: {response.text}")
    except requests.exceptions.ConnectionError as errc:
        print(f"Error Connecting: {errc}")
    except requests.exceptions.Timeout as errt:
        print(f"Timeout Error: {errt}")
    except requests.exceptions.RequestException as err:
        print(f"Something went wrong with the request: {err}")
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

            # Bot logic - පරීක්ෂා කිරීම සඳහා සරල කර ඇත, අවශ්‍ය පරිදි සකස් කරන්න
            lower_msg = message.lower()
            if "hello" in lower_msg or "hi" in lower_msg:
                send_reply(from_number, "Hi! How can I help you? 😊")
            elif "info" in lower_msg or "contact" in lower_msg:
                send_reply(from_number, "This is PDBOT 📱 Contact: 0723051652")
            elif "lk" in lower_msg: # "lk" සඳහා විශේෂ reply එකක්
                send_reply(from_number, "You sent 'lk'. Here's a specific response.")
            else:
                send_reply(from_number, "My New WhatsApp Number 0723051652 (PDBOT)")
            
            return "OK", 200

        except KeyError as e:
            print(f"Missing field in webhook data: {e}. Full data: {data}")
            return "Bad request", 400
        except Exception as e:
            print(f"An unexpected error occurred in webhook processing: {e}. Data: {data}")
            return "Internal Server Error", 500

    return "Webhook is live", 200
