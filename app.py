import os
import asyncio
import threading
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import google.generativeai as genai

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running live!"

# إعداد مفتاح Gemini
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("أهلاً بك! البوت يعمل الآن بكامل كفاءته وجاهز لتلقي أوامرك.")

async def video_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic = " ".join(context.args)
    if not topic:
        await update.message.reply_text("الرجاء كتابة الموضوع بعد الأمر.\nمثال: /video الذكاء الاصطناعي")
        return
    
    await update.message.reply_text(f"⏳ تم استلام موضوعك بنجاح: ({topic}). جاري المعالجة...")

def run_bot():
    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        return
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    application = Application.builder().token(token).concurrent_updates(False).build()
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("video", video_command))
    
    application.run_polling(allowed_updates=Update.ALL_TYPES, stop_signals=None)

if __name__ == "__main__":
    # تشغيل بوت تليجرام في خلفية مستقلة
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()

    # تشغيل سيرفر Flask
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
