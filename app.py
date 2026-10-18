import os
import asyncio
import threading
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import google.generativeai as genai

# 1. إعداد تطبيق Flask لاستجابة سيرفر Render
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running live!"

# 2. تهيئة مكتبة Gemini API
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)

# 3. أوامر البوت (Start & Video)
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("أهلاً بك! استخدم الأمر /video متبوعاً بالموضوع لتوليد الفيديو.")

async def process_and_send_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic = " ".join(context.args)
    if not topic:
        await update.message.reply_text("الرجاء كتابة الموضوع بعد الأمر.\nمثال: /video تاريخ الأهرامات")
        return

    await update.message.reply_text(f"جاري معالجة طلبك حول: {topic} ...")
    # هنا يتم وضع كود توليد الفيديو بواسطة moviepy و Gemini

async def video_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await process_and_send_video(update, context)

# 4. دالة تشغيل بوت تليجرام مع ضبط حلقة الأحداث (Asyncio Loop)
def run_telegram_bot():
    # ضبط حلقة أحداث جديدة لكل thread تفادياً لخطأ RuntimeError
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        print("خطأ: لم يتم العثور على TELEGRAM_TOKEN في متغيرات البيئة!")
        return

    application = Application.builder().token(token).build()

    # تسجيل الهاندلرز
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("video", video_command))

    # بدء استقبال الرسائل
    application.run_polling(close_loop=False)

# 5. نقطة الانطلاق لتشغيل السيرفر والبوت معاً
if __name__ == "__main__":
    # تشغيل البوت في Thread مستقل في الخلفية
    t = threading.Thread(target=run_telegram_bot)
    t.daemon = True
    t.start()

    # تشغيل سيرفر Flask على المنفذ المطلوب
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
