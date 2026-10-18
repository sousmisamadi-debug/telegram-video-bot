import os
import asyncio
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import google.generativeai as genai

# 1. إعداد تطبيق Flask
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running live!"

# 2. إعداد Gemini API
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)

# 3. أوامر البوت
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("أهلاً بك! استخدم الأمر /video متبوعاً بالموضوع لتوليد الفيديو.")

async def video_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic = " ".join(context.args)
    if not topic:
        await update.message.reply_text("الرجاء كتابة الموضوع بعد الأمر.\nمثال: /video تاريخ الأهرامات")
        return
    await update.message.reply_text(f"جاري معالجة طلبك حول: {topic} ...")

# 4. نقطة التشغيل الرئيسية
if __name__ == "__main__":
    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        print("خطأ: لم يتم العثور على TELEGRAM_TOKEN")
    else:
        # بناء وتجهيز تطبيق تيليجرام
        application = Application.builder().token(token).build()
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("video", video_command))
        
        # ملاحظة هامة: لتجنب مشاكل الـ Threads على Render المجاني، 
        # سنقوم بتشغيل السيرفر البسيط أو البوت مباشرة. 
        # وبما أن Render يطلب سيرفر ويب، سنشغل البوت كـ Webhook أو نقوم بتشغيل البوت بالطريقة المباشرة إذا كان مسموحاً،
        # أو نشغل الـ Flask في الخلفية بدلاً من البوت.
