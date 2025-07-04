import telegram
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, ContextTypes
import logging
import requests
import json
import yt_dlp  # For YouTube downloads
import os  # For file operations
import tempfile  # For temporary file creation
import random  # For PIN generation
import string  # For PIN generation
import asyncio  # For async operations

# Firebase Admin SDK imports
import firebase_admin
from firebase_admin import credentials, firestore

# Google Gemini API import
import google.generativeai as genai

# Vercel specific imports for handling HTTP requests
# from http.server import BaseHTTPRequestHandler # <<< REMOVE THIS LINE
# from urllib.parse import urlparse, parse_qs # <<< REMOVE THIS LINE
import io # Keep this if you use it, but it's not directly related to the TypeError

# Configure logging for Vercel environment
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Bot Configuration ---
BOT_TOKEN = os.environ.get('BOT_TOKEN') 
SEND_MESSAGE_API_URL = os.environ.get('SEND_MESSAGE_API_URL', "https://typical-gracia-pdbot-aed22ab6.koyeb.app/send-message")

# --- Firebase Initialization ---
firebase_service_account_key_json = os.environ.get('FIREBASE_SERVICE_ACCOUNT_KEY')
db = None
if firebase_service_account_key_json:
    try:
        if not firebase_admin._apps:
            cred = credentials.Certificate(json.loads(firebase_service_account_key_json))
            firebase_admin.initialize_app(cred)
        db = firestore.client()
        logger.info("Firebase initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize Firebase: {e}")
else:
    logger.error("FIREBASE_SERVICE_ACCOUNT_KEY not found in Vercel Environment Variables. Firebase will not be initialized.")

# --- Gemini AI Initialization ---
gemini_api_key = os.environ.get('GEMINI_API_KEY')
gemini_model = None
if gemini_api_key:
    try:
        genai.configure(api_key=gemini_api_key)
        gemini_model = genai.GenerativeModel('gemini-1.5-flash')
        logger.info("Gemini AI model initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize Gemini AI: {e}")
else:
    logger.error("GEMINI_API_KEY not found in Vercel Environment Variables. Gemini AI will not be initialized.")

APP_ID = "telegram_vercel_bot_app"
FILES_COLLECTION = db.collection(f"artifacts/{APP_ID}/public/data/files") if db else None

# --- Conversation States ---
SENDMSG_ASK_NUMBER, SENDMSG_ASK_MESSAGE = range(2)
YT_ASK_URL = range(2, 3)
UPLOAD_WAIT_FILE = range(3, 4)
GETFILE_ASK_PIN = range(4, 5)
AI_ASK_QUERY = range(5, 6)
DOWNLOAD_ASK_URL = range(6, 7)

# --- Helper Functions ---
def generate_pin(length=6):
    characters = string.ascii_uppercase + string.digits
    return ''.join(random.choice(characters) for i in range(length))

async def is_pin_unique(pin: str) -> bool:
    if not FILES_COLLECTION:
        logger.error("Firestore not initialized, cannot check PIN uniqueness.")
        return False
    query = FILES_COLLECTION.where('pin', '==', pin).limit(1)
    docs = await asyncio.to_thread(query.get)
    return len(docs) == 0

async def generate_unique_pin(length=6) -> str:
    while True:
        pin = generate_pin(length)
        if await is_pin_unique(pin):
            return pin
        await asyncio.sleep(0.1)

# --- Send Message API Function ---
async def send_message_via_api(number: str, message_text: str) -> bool:
    logger.info(f"Attempting to send message to number: {number} with text: {message_text[:50]}...")
    payload = {"number": number, "message": message_text}
    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(SEND_MESSAGE_API_URL, json=payload, headers=headers, timeout=20)
        response.raise_for_status()
        api_response = response.json()
        
        if api_response.get("status") == "success": 
            logger.info(f"Message sent successfully to {number}. API Response: {api_response}")
            return True
        else:
            logger.warning(f"Failed to send message to {number}. API Response: {api_response}")
            return False
    except requests.exceptions.Timeout:
        logger.error(f"Message API call timed out for number: {number}. URL: {SEND_MESSAGE_API_URL}")
        return False
    except requests.exceptions.RequestException as e:
        logger.error(f"Message API call failed for number {number}: {e}. URL: {SEND_MESSAGE_API_URL}")
        return False
    except ValueError as e:
        logger.error(f"Failed to decode JSON response from Message API: {e}. Response content: {response.text}")
        return False
    except Exception as e:
        logger.error(f"An unexpected error occurred during message API call: {e}")
        return False

# --- AI API Function ---
async def ask_gemini_ai(query: str) -> str:
    if not gemini_model:
        return "AI සේවාව ලබා ගත නොහැක. කරුණාකර පසුව උත්සාහ කරන්න."
    
    logger.info(f"Asking AI: {query[:100]}...")
    try:
        response = await asyncio.to_thread(gemini_model.generate_content, query)
        return response.text
    except Exception as e:
        logger.error(f"Error calling Gemini AI: {e}")
        return "AI ප්‍රතිචාරයක් ලබාගැනීමේ දෝෂයක් සිදුවිය. කරුණාකර පසුව උත්සාහ කරන්න."

# --- External URL Download Function ---
async def download_file_from_url(url: str, chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    await context.bot.send_message(chat_id=chat_id, text='File එක download කරමින් සිටී. කරුණාකර මොහොතක් රැඳී සිටින්න...')
    logger.info(f"Attempting to download file from URL: {url}")

    temp_dir = tempfile.mkdtemp()
    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()

        filename = None
        if "Content-Disposition" in response.headers:
            filename = response.headers["Content-Disposition"].split("filename=")[-1].strip('"\'')
        if not filename:
            filename = os.path.basename(url.split('?')[0])
            if not filename:
                filename = "downloaded_file"

        file_path = os.path.join(temp_dir, filename)
        
        total_size = int(response.headers.get('content-length', 0))
        if total_size > 50 * 1024 * 1024:
            await context.bot.send_message(chat_id=chat_id, text=f'File එක ({total_size / (1024*1024):.2f} MB) Telegram හරහා කෙලින්ම යැවීමට විශාල වැඩියි. කරුණාකර වෙනත් download ක්‍රමයක් භාවිතා කරන්න.')
            logger.warning(f"File too large for direct Telegram upload: {url} ({total_size / (1024*1024):.2f} MB)")
            return

        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        file_size = os.path.getsize(file_path)
        logger.info(f"Downloaded file: {file_path}, Size: {file_size / (1024*1024):.2f} MB")

        await context.bot.send_message(chat_id=chat_id, text='File එක යවමින් සිටී...')
        with open(file_path, 'rb') as downloaded_file:
            await context.bot.send_document(
                chat_id=chat_id,
                document=downloaded_file,
                filename=filename,
                caption=f"ඔබගේ file එක: {filename}"
            )
        await context.bot.send_message(chat_id=chat_id, text='✅ **File එක සාර්ථකව යවන ලදී!**')

    except requests.exceptions.RequestException as e:
        logger.error(f"Error downloading file from URL {url}: {e}")
        await context.bot.send_message(chat_id=chat_id, text=f'❌ File එක download කිරීමේ දෝෂයක් සිදුවිය: {e}. කරුණාකර URL එක නිවැරදිදැයි පරීක්ෂා කරන්න.')
    except Exception as e:
        logger.error(f"An unexpected error occurred during URL download: {e}")
        await context.bot.send_message(chat_id=chat_id, text=f'❌ අනපේක්ෂිත දෝෂයක් සිදුවිය. කරුණාකර නැවත උත්සාහ කරන්න.')
    finally:
        if os.path.exists(temp_dir):
            import shutil
            shutil.rmtree(temp_dir)
            logger.info(f"Cleaned up temporary directory: {temp_dir}")

# --- Bot Commands and State Handlers ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles '/start' command, explains bot's purpose."""
    await update.message.reply_text(
        'ආයුබෝවන්! මම ඔබට දුරකථන අංකයකට message යැවීමට, YouTube videos download කිරීමට, '
        'ඕනෑම URL එකකින් files download කිරීමට, AI සමඟ කතා කිරීමට, '
        'සහ files upload කර PIN එකකින් නැවත download කිරීමට උදව් කරන bot කෙනෙක්. \n\n'
        'Commands:\n'
        '/sendmsg - දුරකථන අංකයකට message එකක් යවන්න.\n'
        '/yt_download - YouTube video එකක් download කරන්න.\n'
        '/download_url - ඕනෑම URL එකකින් file එකක් download කරන්න.\n'
        '/upload_file - File එකක් upload කර PIN එකක් ලබාගන්න.\n'
        '/get_file - PIN එකක් දී file එකක් download කරන්න.\n'
        '/ask_ai - AI සමඟ කතා කරන්න.\n'
        '/cancel - ඕනෑම ක්‍රියාවලියක් අවලංගු කරන්න.'
    )

# --- Send Message Conversation Handlers ---
async def start_send_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text('කරුණාකර ඔබට message එක යැවීමට අවශ්‍ය **දුරකථන අංකය** ඇතුළත් කරන්න (රට කේතය සමඟ, උදා: 94712345678).')
    return SENDMSG_ASK_NUMBER

async def get_sendmsg_number(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    number_input = update.message.text
    if not number_input.isdigit() or len(number_input) < 10:
        await update.message.reply_text('කරුණාකර වලංගු දුරකථන අංකයක් ඇතුළත් කරන්න. (උදා: 94712345678)')
        return SENDMSG_ASK_NUMBER
    
    context.user_data['sendmsg_number'] = number_input
    logger.info(f"Received number for message: {number_input}")
    await update.message.reply_text('හොඳයි. දැන් කරුණාකර ඔබට යැවීමට අවශ්‍ය **message එක** ඇතුළත් කරන්න.')
    return SENDMSG_ASK_MESSAGE

async def get_sendmsg_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    message_text_input = update.message.text
    number = context.user_data.get('sendmsg_number')

    logger.info(f"Received message text: {message_text_input}")
    logger.info(f"Attempting to send message to {number}...")

    if number and message_text_input:
        await update.message.reply_text('ඔබගේ message එක යවමින් සිටී...')
        is_sent = await send_message_via_api(number, message_text_input)

        if is_sent:
            await update.message.reply_text('✅ **Message සාර්ථකව යවන ලදී!**')
        else:
            await update.message.reply_text('❌ **Message යැවීම අසාර්ථක විය.** කරුණාකර නැවත උත්සාහ කරන්න.')
    else:
        await update.message.reply_text('අංකය හෝ message එක ලබාගැනීමේ දෝෂයක් සිදුවිය. කරුණාකර නැවත /sendmsg කරන්න.')
    return ConversationHandler.END

# --- YouTube Downloader Handlers ---
async def start_yt_download(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        'කරුණාකර ඔබට download කිරීමට අවශ්‍ය YouTube video එකේ **URL එක** ඇතුළත් කරන්න.'
    )
    return YT_ASK_URL

async def get_yt_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    yt_url = update.message.text
    chat_id = update.message.chat_id
    
    if "youtube.com/" not in yt_url and "youtu.be/" not in yt_url:
        await update.message.reply_text('කරුණාකර වලංගු YouTube URL එකක් ඇතුළත් කරන්න.')
        return YT_ASK_URL

    await update.message.reply_text('ඔබගේ video එක download කරමින් සිටී. කරුණාකර මොහොතක් රැඳී සිටින්න...')
    logger.info(f"Attempting to download YouTube video from: {yt_url}")

    temp_dir = tempfile.mkdtemp()
    output_template = os.path.join(temp_dir, '%(title)s.%(ext)s')

    ydl_opts = {
        'format': 'best[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': output_template,
        'noplaylist': True,
        'max_filesize': 50 * 1024 * 1024,
        'merge_output_format': 'mp4',
        'progress_hooks': [lambda d: logger.info(d['status'])],
        'quiet': True,
        'no_warnings': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = await asyncio.to_thread(ydl.extract_info, yt_url, download=True)
            file_path = ydl.prepare_filename(info_dict)

        if os.path.exists(file_path):
            file_size = os.path.getsize(file_path)
            logger.info(f"Downloaded file: {file_path}, Size: {file_size / (1024*1024):.2f} MB")

            if file_size > 50 * 1024 * 1024:
                await update.message.reply_text(
                    f'ඔබගේ video එක ({file_size / (1024*1024):.2f} MB) Telegram හරහා කෙලින්ම යැවීමට විශාල වැඩියි. '
                    'කරුණාකර වෙනත් download ක්‍රමයක් භාවිතා කරන්න.')
            else:
                await update.message.reply_text('Video එක යවමින් සිටී...')
                with open(file_path, 'rb') as video_file:
                    await context.bot.send_document(
                        chat_id=chat_id,
                        document=video_file,
                        caption=f"ඔබගේ video එක: {info_dict.get('title', 'YouTube Video')}"
                    )
                await update.message.reply_text('✅ **Video එක සාර්ථකව යවන ලදී!**')
        else:
            await update.message.reply_text('❌ Video එක download කිරීමේ දෝෂයක් සිදුවිය. කරුණාකර නැවත උත්සාහ කරන්න.')

    except yt_dlp.utils.DownloadError as e:
        logger.error(f"YouTube Download Error: {e}")
        await update.message.reply_text(f'❌ Video එක download කිරීමේ දෝෂයක් සිදුවිය: {e}. කරුණාකර URL එක නිවැරදිදැයි පරීක්ෂා කරන්න.')
    except Exception as e:
        logger.error(f"An unexpected error occurred during YouTube download: {e}")
        await update.message.reply_text(f'❌ අනපේක්ෂිත දෝෂයක් සිදුවිය. කරුණාකර නැවත උත්සාහ කරන්න.')
    finally:
        if os.path.exists(temp_dir):
            import shutil
            shutil.rmtree(temp_dir)
            logger.info(f"Cleaned up temporary directory: {temp_dir}")
    return ConversationHandler.END

# --- External URL Downloader Handlers ---
async def start_download_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        'කරුණාකර ඔබට download කිරීමට අවශ්‍ය file එකේ **External URL එක** ඇතුළත් කරන්න.'
    )
    return DOWNLOAD_ASK_URL

async def get_download_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    url = update.message.text
    chat_id = update.message.chat_id

    if not (url.startswith("http://") or url.startswith("https://")):
        await update.message.reply_text('කරුණාකර වලංගු URL එකක් ඇතුළත් කරන්න (http:// හෝ https:// වලින් ආරම්භ විය යුතුය).')
        return DOWNLOAD_ASK_URL

    await download_file_from_url(url, chat_id, context)
    return ConversationHandler.END

# --- File Upload with PIN Handlers ---
async def start_upload_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not FILES_COLLECTION:
        await update.message.reply_text("File upload සේවාව ලබා ගත නොහැක. කරුණාකර පසුව උත්සාහ කරන්න.")
        return ConversationHandler.END
    await update.message.reply_text(
        'කරුණාකර ඔබට upload කිරීමට අවශ්‍ය **file එක** (photo, video, document, audio) එවන්න.'
    )
    return UPLOAD_WAIT_FILE

async def handle_uploaded_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not FILES_COLLECTION:
        await update.message.reply_text("File upload සේවාව ලබා ගත නොහැක. කරුණාකර පසුව උත්සාහ කරන්න.")
        return ConversationHandler.END

    file_obj = None
    file_type = "document"
    if update.message.document:
        file_obj = update.message.document
    elif update.message.video:
        file_obj = update.message.video
        file_type = "video"
    elif update.message.audio:
        file_obj = update.message.audio
        file_type = "audio"
    elif update.message.photo:
        file_obj = update.message.photo[-1]
        file_type = "photo"
    
    if not file_obj:
        await update.message.reply_text('කරුණාකර වලංගු file එකක් (document, video, audio, photo) එවන්න.')
        return UPLOAD_WAIT_FILE

    if file_obj.file_size and file_obj.file_size > 50 * 1024 * 1024:
        await update.message.reply_text(
            f'ඔබගේ file එක ({file_obj.file_size / (1024*1024):.2f} MB) Telegram හරහා කෙලින්ම ගබඩා කිරීමට සහ යැවීමට විශාල වැඩියි. 50MB ට අඩු files පමණක් upload කරන්න.'
        )
        return ConversationHandler.END

    await update.message.reply_text('File එක ගබඩා කරමින් PIN එකක් සාදමින් සිටී...')
    logger.info(f"Received file for upload: {file_obj.file_id}, size: {file_obj.file_size}")

    try:
        unique_pin = await generate_unique_pin()
        
        file_metadata = {
            'file_id': file_obj.file_id,
            'file_name': file_obj.file_name if hasattr(file_obj, 'file_name') else f"telegram_{file_type}_{file_obj.file_id}.{file_obj.mime_type.split('/')[-1] if file_obj.mime_type else 'bin'}",
            'mime_type': file_obj.mime_type,
            'file_size': file_obj.file_size,
            'pin': unique_pin,
            'uploaded_by': update.effective_user.id,
            'upload_timestamp': firestore.SERVER_TIMESTAMP
        }
        
        await asyncio.to_thread(FILES_COLLECTION.document(unique_pin).set, file_metadata)
        
        await update.message.reply_text(
            f'✅ **File එක සාර්ථකව upload කරන ලදී!**\n'
            f'ඔබගේ PIN එක: `{unique_pin}`\n\n'
            'මෙම PIN එක ඕනෑම කෙනෙකුට /get_file command එක භාවිතා කර ඔබගේ file එක download කිරීමට භාවිතා කළ හැක.'
        )
        logger.info(f"File {file_obj.file_id} uploaded with PIN: {unique_pin}")

    except Exception as e:
        logger.error(f"Error processing uploaded file or saving to Firestore: {e}")
        await update.message.reply_text('❌ File upload කිරීමේ දෝෂයක් සිදුවිය. කරුණාකර නැවත උත්සාහ කරන්න.')
    return ConversationHandler.END

# --- PIN-based Download Handlers ---
async def start_get_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not FILES_COLLECTION:
        await update.message.reply_text("File download සේවාව ලබා ගත නොහැක. කරුණාකර පසුව උත්සාහ කරන්න.")
        return ConversationHandler.END
    await update.message.reply_text('කරුණාකර ඔබට download කිරීමට අවශ්‍ය file එකේ **PIN එක** ඇතුළත් කරන්න.')
    return GETFILE_ASK_PIN

async def get_file_by_pin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not FILES_COLLECTION:
        await update.message.reply_text("File download සේවාව ලබා ගත නොහැක. කරුණාකර පසුව උත්සාහ කරන්න.")
        return ConversationHandler.END

    pin = update.message.text.strip().upper()
    chat_id = update.message.chat_id

    await update.message.reply_text(f'PIN එක `{pin}` සමඟ file එක සොයමින්...')
    logger.info(f"Attempting to retrieve file with PIN: {pin}")

    try:
        doc_ref = FILES_COLLECTION.document(pin)
        doc = await asyncio.to_thread(doc_ref.get)

        if doc.exists:
            file_metadata = doc.to_dict()
            telegram_file_id = file_metadata.get('file_id')
            file_name = file_metadata.get('file_name', 'downloaded_file')
            file_size = file_metadata.get('file_size', 0)

            if not telegram_file_id:
                await update.message.reply_text('ගැටලුවක් සිදුවිය: File ID එක සොයාගත නොහැක.')
                logger.error(f"File ID missing for PIN: {pin}")
                return ConversationHandler.END
            
            if file_size > 50 * 1024 * 1024:
                 await update.message.reply_text(
                    f'ඔබ සොයන file එක ({file_size / (1024*1024):.2f} MB) Telegram හරහා කෙලින්ම යැවීමට විශාල වැඩියි. '
                    'කරුණාකර වෙනත් download ක්‍රමයක් භාවිතා කරන්න.'
                )
                 logger.warning(f"File for PIN {pin} too large for direct Telegram upload.")
                 return ConversationHandler.END

            await update.message.reply_text('File එක download කරමින් සිටී...')
            logger.info(f"Downloading file from Telegram with ID: {telegram_file_id}")

            try:
                file_info = await context.bot.get_file(telegram_file_id)
                downloaded_bytes = await file_info.download_as_bytearray()

                await context.bot.send_document(
                    chat_id=chat_id,
                    document=bytes(downloaded_bytes),
                    filename=file_name,
                    caption=f"ඔබගේ file එක: {file_name}"
                )
                await update.message.reply_text('✅ **File එක සාර්ථකව යවන ලදී!**')
                logger.info(f"File for PIN {pin} sent successfully.")

            except telegram.error.BadRequest as e:
                logger.error(f"Telegram BadRequest error when downloading file {telegram_file_id} for PIN {pin}: {e}")
                await update.message.reply_text('❌ Telegram හරහා file එක ලබාගැනීමේ දෝෂයක් සිදුවිය. (File ID වලංගු නොවිය හැක හෝ කල් ඉකුත් වී ඇත).')
            except Exception as e:
                logger.error(f"Error downloading/sending file for PIN {pin}: {e}")
                await update.message.reply_text('❌ File එක යැවීමේදී අනපේක්ෂිත දෝෂයක් සිදුවිය. කරුණාකර පසුව උත්සාහ කරන්න.')

        else:
            await update.message.reply_text('❌ වලංගු PIN එකක් නොවේ. කරුණාකර නිවැරදි PIN එක ඇතුළත් කරන්න.')
            logger.warning(f"Invalid PIN entered: {pin}")

    except Exception as e:
        logger.error(f"Error retrieving file from Firestore for PIN {pin}: {e}")
        await update.message.reply_text('❌ File සොයාගැනීමේදී දෝෂයක් සිදුවිය. කරුණාකර පසුව උත්සාහ කරන්න.')
    return ConversationHandler.END

# --- AI Conversation Handlers ---
async def start_ask_ai(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not gemini_model:
        await update.message.reply_text("AI සේවාව ලබා ගත නොහැක. කරුණාකර පසුව උත්සාහ කරන්න.")
        return ConversationHandler.END
    await update.message.reply_text('AI සමඟ කතා කිරීමට ඔබට අවශ්‍ය ප්‍රශ්නය හෝ විමසුම ඇතුළත් කරන්න.')
    return AI_ASK_QUERY

async def get_ai_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_query = update.message.text
    chat_id = update.message.chat_id

    if not user_query:
        await update.message.reply_text('කරුණාකර වලංගු ප්‍රශ්නයක් ඇතුළත් කරන්න.')
        return AI_ASK_QUERY
    
    await update.message.reply_text('ඔබගේ ප්‍රශ්නයට AI ප්‍රතිචාරයක් සකස් කරමින් සිටී...')
    ai_response = await ask_gemini_ai(user_query)
    
    await update.message.reply_text(ai_response)
    return ConversationHandler.END

# --- General Handlers ---
async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logger.info("Conversation cancelled by user.")
    await update.message.reply_text('ක්‍රියාවලිය අවලංගු කරන ලදී.')
    return ConversationHandler.END

async def unhandled_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message and update.message.text:
        logger.info(f"Received unhandled message: {update.message.text}")
        await update.message.reply_text(
            "මට තේරෙන්නේ නැහැ. කරුණාකර /start command එක භාවිතා කර ලබා ගත හැකි commands බලන්න."
        )

# --- Global Application Instance ---
application = Application.builder().token(BOT_TOKEN).build()

# Register handlers once
def register_handlers(app: Application) -> None:
    app.add_handler(CommandHandler("start", start_command))

    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("sendmsg", start_send_message)],
        states={
            SENDMSG_ASK_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_sendmsg_number)],
            SENDMSG_ASK_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_sendmsg_message)],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
    ))
    
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("yt_download", start_yt_download)],
        states={
            YT_ASK_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_yt_url)],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
    ))

    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("download_url", start_download_url)],
        states={
            DOWNLOAD_ASK_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_download_url)],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
    ))

    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("upload_file", start_upload_file)],
        states={
            UPLOAD_WAIT_FILE: [MessageHandler(filters.Document.ALL | filters.VIDEO | filters.AUDIO | filters.Photo, handle_uploaded_file)],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
    ))

    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("get_file", start_get_file)],
        states={
            GETFILE_ASK_PIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_file_by_pin)],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
    ))

    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("ask_ai", start_ask_ai)],
        states={
            AI_ASK_QUERY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_ai_query)],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
    ))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unhandled_message_handler))

# Register handlers when the script is loaded
register_handlers(application)

# --- Vercel Serverless Function Entry Point ---
# This function will be called by Vercel when an HTTP request comes in.
async def handler(request):
    """
    Vercel serverless function entry point for Telegram bot webhooks.
    """
    if request.method == 'POST':
        try:
            # Read the incoming JSON update from Telegram
            update_data = json.loads(request.body.decode('utf-8'))
            update = Update.de_json(update_data, application.bot)
            
            # Process the update asynchronously
            await application.process_update(update)
            
            # Telegram expects a 200 OK response quickly
            return {
                'statusCode': 200,
                'body': json.dumps({'status': 'ok'})
            }
        except Exception as e:
            logger.error(f"Error processing Telegram update: {e}")
            return {
                'statusCode': 500,
                'body': json.dumps({'error': str(e)})
            }
    elif request.method == 'GET':
        # Simple GET request response for checking if the endpoint is alive
        return {
            'statusCode': 200,
            'body': json.dumps({'status': 'Bot is running and ready for webhooks!'})
        }
    else:
        return {
            'statusCode': 405,
            'body': json.dumps({'error': 'Method Not Allowed'})
        }

# For local testing (optional, not for Vercel deployment)
# if __name__ == '__main__':
#     logger.info("Starting bot in polling mode for local development...")
#     application.run_polling(allowed_updates=Update.ALL_TYPES)
#     logger.info("Bot stopped.")
