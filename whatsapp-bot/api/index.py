from flask import Flask, request
import requests
import os

# Initialize the Flask application
app = Flask(__name__)

# --- Configuration ---
# IMPORTANT: It's best practice to use environment variables for sensitive data like tokens.
# For Vercel, you would set these in your project settings:
# Project Settings -> Environment Variables
INSTANCE_ID = "instance127525" # Replace with your actual Ultramsg Instance ID
TOKEN = "anay3jh9z0gtsqra45ggg"   # Replace with your actual Ultramsg Token

# Alternatively, if you set them as environment variables in Vercel:
# INSTANCE_ID = os.environ.get("ULTRAMSG_INSTANCE_ID")
# TOKEN = os.environ.get("ULTRAMSG_TOKEN")
# Make sure to set these variables in your Vercel project settings.


# --- Function to send replies via Ultramsg API ---
def send_reply(to_number, message):
    # Base URL for the chat message API
    base_url = f"https://api.ultramsg.com/{INSTANCE_ID}/messages/chat"

    # Parameters that go into the URL (query string)
    # Ultramsg's error message indicated 'token' must be a GET parameter,
    # even for POST requests to this specific endpoint.
    url_params = {"token": TOKEN}

    # Data that goes into the POST request body
    # 'to' is the recipient's number, 'body' is the message content
    post_data = {"to": to_number, "body": message}

    try:
        # Make the POST request to Ultramsg
        # 'params' sends data in the URL query string
        # 'data' sends data in the request body (form-urlencoded by default)
        response = requests.post(base_url, params=url_params, data=post_data)
        
        # Print the full response from Ultramsg for debugging purposes
        print("Ultramsg API Response:", response.text) 

        # Raise an HTTPError for bad responses (4xx or 5xx status codes)
        response.raise_for_status() 
        
        print("Reply sent successfully to Ultramsg!")

    except requests.exceptions.HTTPError as errh:
        # Handles HTTP errors (e.g., 400 Bad Request, 401 Unauthorized, 404 Not Found, 500 Internal Server Error)
        print(f"HTTP Error occurred: {errh} - Response: {response.text}")
    except requests.exceptions.ConnectionError as errc:
        # Handles network-related errors (e.g., DNS failure, refused connection)
        print(f"Error Connecting to Ultramsg: {errc}")
    except requests.exceptions.Timeout as errt:
        # Handles request timeout errors
        print(f"Timeout Error when connecting to Ultramsg: {errt}")
    except requests.exceptions.RequestException as err:
        # Handles any other general request-related errors
        print(f"An unknown requests error occurred: {err}")
    except Exception as e:
        # Catches any other unexpected errors during the process
        print(f"An unexpected error occurred while sending reply: {e}")


# --- Flask Routes ---

# Home route - simple check to see if the bot is running
@app.route('/')
def home():
    return "🚀 WhatsApp Bot is running!"

# Webhook route - receives incoming messages from Ultramsg
@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'POST':
        # Get the JSON data sent by Ultramsg
        data = request.get_json()
        print("Webhook called with data:", data) # Log the entire incoming payload

        # Basic validation: Check if 'data' key exists in the payload
        if not data or 'data' not in data:
            print("Invalid or missing 'data' key in webhook payload.")
            return "Invalid data", 400

        try:
            # Extract sender's number and message body
            from_number = data['data']['from']
            message = data['data']['body']
            print(f"Message from {from_number}: {message}")

            # Convert message to lowercase for case-insensitive matching
            lower_msg = message.lower()

            # --- Bot Logic ---
            # IMPORTANT: Review this logic based on how you want your bot to respond.
            # Current logic: If "PDBOT" is NOT in the message, then apply these rules.
            # If "PDBOT" IS in the message, it will do nothing (fall through to 'return "OK", 200').
            # If you want to respond to ALL messages, remove the 'if "PDBOT" not in message:' block entirely.
            # If you want to respond ONLY if "PDBOT" IS in the message, change it to 'if "PDBOT" in message:'.

            if "PDBOT" not in lower_msg: # Changed to lower_msg to be consistent
                if "hello" in lower_msg or "hi" in lower_msg:
                    send_reply(from_number, "Hi there! How can I help you today? 😊")
                elif "info" in lower_msg or "contact" in lower_msg:
                    send_reply(from_number, "This is PDBOT 🤖. You can contact us at: 0723051652")
                elif "lk" in lower_msg: # Added specific response for "lk" as per your test
                    send_reply(from_number, "Ah, 'lk' detected! This is a specific response for that. How else can I assist?")
                else:
                    # Default reply if no specific keyword is matched
                    send_reply(from_number, "Thanks for your message! My new WhatsApp Number is 0723051652 (PDBOT).")
            else:
                # This block runs if "PDBOT" is found in the message and the above 'if' is true.
                # You can add specific logic here if you want the bot to react when "PDBOT" is present.
                print("Message contains 'PDBOT'. Current logic skips replying for this message.")

            # Always return a 200 OK to Ultramsg to acknowledge receipt of the webhook
            return "OK", 200

        except KeyError as e:
            # Catches errors if expected keys like 'from' or 'body' are missing
            print(f"Missing expected field in webhook data: {e}. Full data received: {data}")
            return "Bad request: Missing data", 400
        except Exception as e:
            # Catches any other unexpected errors during webhook processing
            print(f"An unexpected error occurred during webhook processing: {e}. Data: {data}")
            return "Internal Server Error", 500

    # For GET requests to /webhook, simply acknowledge that the webhook is active
    return "Webhook is live", 200
