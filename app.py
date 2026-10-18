import os
import asyncio
import threading
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import google.generativeai as genai
from moviepy.editor import TextClip, CompositeVideoClip, ColorClip

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running live!"

GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("أهلاً بك! استخدم الأمر /video متبوعاً بالموضوع لتوليد الفيديو.")

async def video_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic = " ".join(context.args)
    if not topic:
        await update.message.reply_text("الرجاء كتابة الموضوع بعد الأمر.\nمثال: /video قصة الذكاء الاصطناعي")
        return

    status_msg = await update.message.reply_text(f"⏳ جاري إنشاء الفيديو حول: {topic} ...")

    output_filename = f"video_{update.message.message_id}.mp4"

    def create_video():
        # إنشاء خلفية داكنة بسيطة للفيديو (مدة 5 ثوانٍ)
        bg_clip = ColorClip(size=(720, 1280), color=(15, 15, 25), duration=5)
        
        # إضافة نص الموضوع فوق الخلفية
        txt_clip = TextClip(topic, fontsize=40, color='white', method='caption', size=(600, None))
        txt_clip = txt_clip.set_position('center').set_duration(5)
        
        # دمج الفيديو وتصديره
        video = CompositeVideoClip([bg_clip, txt_clip])
        video.write_videofile(output_filename, fps=24, codec='libx264', audio=False, preset='ultrafast')

    try:
        # تشغيل عملية معالجة الفيديو دون تجميد حلقة الأحداث (asyncio)
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, create_video)

        # إرسال الفيديو الناتج إلى المستخدم على تيليجرام
        with open(output_filename, 'rb') as video_file:
            await context.bot.send_video(
                chat_id=update.effective_chat.id,
                video=video_file,
                caption=f"🎬 فيديو حول: {topic}"
            )
            
        await status_msg.delete()

    except Exception as e:
        await update.message.reply_text(f"❌ حدث خطأ أثناء إنشاء الفيديو: {str(e)}")

    finally:
        # مسح الملف المؤقت من السيرفر بعد الإرسال
        if os.path.exists(output_filename):
            os.remove(output_filename)

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
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()

    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
