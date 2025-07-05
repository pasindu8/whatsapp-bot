import json, os, logging, requests, tempfile, yt_dlp, firebase_admin, google.generativeai as genai
# (import rest of your code dependencies)

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, ContextTypes

# Initialize logging, Firebase, Gemini, handlers and application builder here (copy your existing setup)...

application = Application.builder().token(os.environ["BOT_TOKEN"]).build()
# register_handlers(application)  ← make sure all ADD_HANDLER calls are here

async def handler(request):
    if request.method == "POST":
        try:
            update_data = json.loads(await request.body())
            update = Update.de_json(update_data, application.bot)
            await application.process_update(update)
            return {"statusCode": 200, "body": json.dumps({"status": "ok"})}
        except Exception as e:
            logging.error(f"handler error: {e}")
            return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
    elif request.method == "GET":
        return {"statusCode": 200, "body": json.dumps({"status": "Bot is running!"})}
    else:
        return {"statusCode": 405, "body": json.dumps({"error": "Method Not Allowed"})}
