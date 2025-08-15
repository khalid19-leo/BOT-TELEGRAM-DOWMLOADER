import asyncio
import os
import uuid
import json
import datetime
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)
import yt_dlp

# ------ Basic Settings ------
# Note: The token is imported from Replit Secrets for security.

TOKEN = os.environ.get("TOKEN")
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID")
MAX_VIDEO_DURATION = 600
DATA_FILE = "bot_data.json"

if not TOKEN:
    print("❌ Error: Bot token not found. Please add it to Replit Secrets.")
    exit()

# ------ Logging Settings ------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ------ Multilingual Texts ------
TEXTS = {
    "ar": {
        "welcome": "مرحباً بك في بوت التنزيل! 👋",
        "select_lang": "📌 الرجاء اختيار اللغة:",
        "start": "أرسل لي رابط فيديو أو صورة من أي منصة وسأحاول تنزيلها لك.",
        "help": "📚 الأوامر المتاحة:\n/start - بدء الاستخدام\n/help - عرض المساعدة\n/language - تغيير اللغة",
        "downloading": "⏳ جاري تحميل الملف...",
        "success": "✅ تم التنزيل بنجاح!",
        "error": "❌ حدث خطأ أثناء المعالجة",
        "lang_set": "تم تعيين اللغة إلى العربية",
        "no_permission": "⛔️ ليس لديك الصلاحية لاستخدام هذا الأمر.",
        "stats_title": "📊 إحصائيات البوت",
        "total_users": "👤 إجمالي المستخدمين",
        "total_downloads": "📥 إجمالي التنزيلات",
        "bot_version": "🚀 إصدار البوت",
        "start_date": "📅 تاريخ التشغيل",
        "downloads_by_lang": "📈 التنزيلات حسب اللغة",
        "broadcast_sent": "✅ تم إرسال الرسالة إلى {} مستخدم.",
        "broadcast_error": "❌ خطأ في إرسال رسالة إلى {} مستخدم.",
        "user_not_found": "❌ المستخدم غير موجود في قاعدة البيانات.",
        "user_info_title": "👤 معلومات المستخدم",
        "user_id": "رقم المستخدم",
        "first_seen": "تاريخ الانضمام",
        "lang": "اللغة",
        "download_count": "عدد التنزيلات"
    },
    "en": {
        "welcome": "Welcome to Download Bot! 👋",
        "select_lang": "📌 Please select your language:",
        "start": "Send me a video or image link from any platform and I'll try to download it for you.",
        "help": "📚 Available commands:\n/start - Start using\n/help - Show help\n/language - Change language",
        "downloading": "⏳ Downloading file...",
        "success": "✅ Download completed successfully!",
        "error": "❌ Error processing request",
        "lang_set": "Language set to English",
        "no_permission": "⛔️ You do not have permission to use this command.",
        "stats_title": "📊 Bot Statistics",
        "total_users": "👤 Total Users",
        "total_downloads": "📥 Total Downloads",
        "bot_version": "🚀 Bot Version",
        "start_date": "📅 Start Date",
        "downloads_by_lang": "📈 Downloads by Language",
        "broadcast_sent": "✅ Message sent to {} users.",
        "broadcast_error": "❌ Error sending message to {} users.",
        "user_not_found": "❌ User not found in the database.",
        "user_info_title": "👤 User Information",
        "user_id": "User ID",
        "first_seen": "Joined",
        "lang": "Language",
        "download_count": "Download Count"
    }
}

# ------ Data System ------
def load_data():
    """Load data from JSON file. Create file if it doesn't exist."""
    try:
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
            # Ensure required keys exist
            if "global_stats" not in data:
                data["global_stats"] = {"ar_downloads": 0, "en_downloads": 0}
            return data
    except (FileNotFoundError, json.JSONDecodeError):
        initial_data = {
            "users": {},
            "system": {
                "version": "3.1",
                "start_date": str(datetime.datetime.now())
            },
            "global_stats": {
                "ar_downloads": 0,
                "en_downloads": 0
            }
        }
        return initial_data

def save_data(data):
    """Save data to JSON file."""
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

def get_user_lang(user_id):
    """Get user's preferred language."""
    data = load_data()
    return data["users"].get(str(user_id), {}).get("lang", "en")

def set_user_lang(user_id, lang):
    """Set user's language and store their data."""
    data = load_data()
    if str(user_id) not in data["users"]:
        data["users"][str(user_id)] = {
            "first_seen": str(datetime.datetime.now()),
            "lang": lang,
            "download_count": 0 # Initialize download count for new users
        }
    else:
        data["users"][str(user_id)]["lang"] = lang
    save_data(data)

# ------ Bot Commands ------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends the welcome message and language selection buttons."""
    user_id = update.effective_user.id
    set_user_lang(user_id, get_user_lang(user_id)) # Add user to DB on start if not exists
    keyboard = [
        [InlineKeyboardButton("English 🇬🇧", callback_data="lang_en")],
        [InlineKeyboardButton("العربية 🇸🇦", callback_data="lang_ar")]
    ]
    await update.message.reply_text(
        "🌍 Please select your language / الرجاء اختيار اللغة:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows the available commands list."""
    user_id = update.effective_user.id
    lang = get_user_lang(user_id)
    await update.message.reply_text(TEXTS[lang]["help"])

async def language_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles language selection button presses."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    lang = query.data.split("_")[1]
    set_user_lang(user_id, lang)
    await query.edit_message_text(
        f"{TEXTS[lang]['welcome']}\n\n{TEXTS[lang]['start']}"
    )

async def download_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles media download requests from links."""
    if not update.message or not update.message.text:
        return

    user_id = update.effective_user.id
    lang = get_user_lang(user_id)
    url = update.message.text
    file_name = f"media_{uuid.uuid4().hex}.mp4"

    downloading_msg = await update.message.reply_text(TEXTS[lang]["downloading"])

    try:
        ydl_opts = {
            "outtmpl": file_name,
            "format": "best",
            "max_duration": MAX_VIDEO_DURATION,
            "quiet": True,
            "no_warnings": True,
            "extractor_args": {
                "instagram": {
                    "headers": {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                    }
                }
            }
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await asyncio.to_thread(ydl.extract_info, url, download=True)

        if os.path.exists(file_name):
            with open(file_name, "rb") as media_file:
                if info.get("duration", 0) > 0:
                    await update.message.reply_video(
                        video=media_file,
                        caption=TEXTS[lang]["success"],
                        supports_streaming=True
                    )
                else:
                    await update.message.reply_photo(
                        photo=media_file,
                        caption=TEXTS[lang]["success"]
                    )

            await context.bot.delete_message(
                chat_id=update.message.chat_id,
                message_id=downloading_msg.message_id
            )

            # Update global download count and user's download count
            data = load_data()
            if lang == "ar":
                data["global_stats"]["ar_downloads"] += 1
            elif lang == "en":
                data["global_stats"]["en_downloads"] += 1

            user_id_str = str(user_id)
            if user_id_str in data["users"]:
                data["users"][user_id_str]["download_count"] += 1

            save_data(data)

    except Exception as e:
        logger.error(f"Download error: {e}")
        await update.message.reply_text(f"{TEXTS[lang]['error']}:\n{str(e)}")

    finally:
        if os.path.exists(file_name):
            try:
                os.remove(file_name)
            except Exception as e:
                logger.error(f"Error deleting file: {e}")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays detailed statistics for the admin only."""
    if str(update.effective_user.id) != ADMIN_CHAT_ID:
        await update.message.reply_text(TEXTS["en"]["no_permission"])
        return

    data = load_data()
    users_data = data.get("users", {})
    system_data = data.get("system", {})
    global_stats = data.get("global_stats", {"ar_downloads": 0, "en_downloads": 0})

    total_users = len(users_data)
    total_downloads = sum(user.get("download_count", 0) for user in users_data.values())

    stats_msg = (
        f"📊 **إحصائيات البوت**\n"
        f"---\n"
        f"👤 إجمالي المستخدمين: {total_users}\n"
        f"📥 إجمالي التنزيلات: {total_downloads}\n"
        f"---"
        f"📈 **التنزيلات حسب اللغة**\n"
        f"العربية 🇸🇦: {global_stats.get('ar_downloads', 0)}\n"
        f"الإنجليزية 🇬🇧: {global_stats.get('en_downloads', 0)}\n"
        f"---"
        f"🚀 إصدار البوت: {system_data.get('version', 'غير معروف')}\n"
        f"📅 تاريخ التشغيل: {system_data.get('start_date', 'غير معروف')}"
    )
    await update.message.reply_text(stats_msg)

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Sends a message to all users who have interacted with the bot.
    Usage: /broadcast <message>
    """
    if str(update.effective_user.id) != ADMIN_CHAT_ID:
        await update.message.reply_text(TEXTS["en"]["no_permission"])
        return

    if not context.args:
        await update.message.reply_text("⛔️ يرجى كتابة الرسالة بعد الأمر. مثال: `/broadcast مرحباً بكم في تحديث جديد!`")
        return

    message_to_send = " ".join(context.args)
    data = load_data()
    user_ids = data["users"].keys()
    sent_count = 0
    error_count = 0

    for user_id in user_ids:
        try:
            await context.bot.send_message(chat_id=user_id, text=message_to_send)
            sent_count += 1
            await asyncio.sleep(0.1) # small delay to avoid hitting Telegram API limits
        except Exception as e:
            logger.error(f"Error sending broadcast to user {user_id}: {e}")
            error_count += 1

    await update.message.reply_text(TEXTS["ar"]["broadcast_sent"].format(sent_count))
    if error_count > 0:
        await update.message.reply_text(TEXTS["ar"]["broadcast_error"].format(error_count))

async def user_info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Displays detailed information about a specific user.
    Usage: /userinfo <user_id>
    """
    if str(update.effective_user.id) != ADMIN_CHAT_ID:
        await update.message.reply_text(TEXTS["en"]["no_permission"])
        return

    if not context.args:
        await update.message.reply_text("⛔️ يرجى كتابة رقم المستخدم بعد الأمر. مثال: `/userinfo 123456789`")
        return

    target_user_id = context.args[0]
    data = load_data()
    user_data = data["users"].get(target_user_id)

    if user_data:
        info_msg = (
            f"👤 **معلومات المستخدم**\n"
            f"---\n"
            f"رقم المستخدم: `{target_user_id}`\n"
            f"تاريخ الانضمام: {user_data.get('first_seen', 'غير معروف')}\n"
            f"اللغة: {user_data.get('lang', 'غير معروف')}\n"
            f"عدد التنزيلات: {user_data.get('download_count', 0)}\n"
        )
        await update.message.reply_text(info_msg)
    else:
        await update.message.reply_text(TEXTS["ar"]["user_not_found"])

# ------ Main Function ------
def main():
    """Main entry point for the code."""
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(CommandHandler("userinfo", user_info_command))
    app.add_handler(CallbackQueryHandler(language_handler, pattern="^lang_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_media))

    logger.info("🚀 Bot is running with admin tools enabled...")
    app.run_polling()

if __name__ == "__main__":
    if not os.path.exists(DATA_FILE):
        save_data(load_data())
    main()
