import os
import json
import asyncio
import uuid
import aiohttp
import subprocess
import threading
from urllib.parse import quote
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from google import genai
from google.genai import types

# --- إعدادات ---
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

client = genai.Client(api_key=GEMINI_KEY)
app = Flask(__name__)
TMP = "/tmp/vidgen"
os.makedirs(TMP, exist_ok=True)

# --- 1. العقل المدبر: توليد السيناريو ---
async def plan_script(topic: str) -> dict:
    prompt = f"""أنت مخرج سينمائي. أنشئ سيناريو لفيديو قصير (30-45 ثانية) حول: "{topic}".
أرجع JSON فقط بهاد الشكل:
{{
  "title": "عنوان قصير",
  "scenes": [
    {{"visual": "English description for image generation, cinematic", "narration": "نص عربي قصير للتعليق الصوتي", "duration": 6}},
    ...
  ]
}}
5 إلى 7 مشاهد. كل narration جملة واحدة قصيرة. لا تزيد أي شرح خارج JSON."""
    
    resp = await client.aio.models.generate_content(
        model="gemini-3.8-flash", 
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    return json.loads(resp.text)

# --- 2. وكيل الصور: Pollinations ---
async def gen_image(session, visual: str, idx: int) -> str:
    encoded_visual = quote(visual)
    url = f"https://image.pollinations.ai/prompt/{encoded_visual}"
    params = {"width": 1280, "height": 720, "nologo": "true", "seed": idx * 42 + 7}
    async with session.get(url, params=params, timeout=120) as r:
        r.raise_for_status()
        path = f"{TMP}/img_{uuid.uuid4().hex}.jpg"
        with open(path, "wb") as f:
            f.write(await r.read())
        return path

# --- 3. وكيل الصوت: Gemini TTS (الموديل الجديد) ---
async def gen_voice(text: str) -> str:
    # استعملنا البنية الجديدة اللي كتطلبها Google فـ الموديلات الجديدة
    resp = await client.aio.models.generate_content(
        model="gemini-3.8-flash-tts", 
        contents=[{
            "role": "user",
            "parts": [{
                "text": text,
                "speech_metadata": {"style": "cinematic, clear, informative"} # النبرة
            }]
        }],
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Kore")
                )
            ),
        ),
    )
    audio_data = resp.candidates[0].content.parts[0].inline_data.data
    path = f"{TMP}/voice_{uuid.uuid4().hex}.wav"
    with open(path, "wb") as f:
        f.write(audio_data)
    return path

# --- 4. الدمج: FFmpeg ---
def build_scene(img: str, voice: str, duration: int, idx: int) -> str:
    out = f"{TMP}/scene_{idx}_{uuid.uuid4().hex}.mp4"
    cmd = [
        "ffmpeg", "-y", "-loop", "1", "-i", img, "-i", voice,
        "-filter_complex",
        f"[0:v]scale=1920:1080:force_original_aspect_ratio=increase,"
        f"crop=1920:1080,zoompan=z='min(zoom+0.0015,1.15)':d={duration*25}:"
        f"s=1920x1080,format=yuv420p[v]",
        "-map", "[v]", "-map", "1:a",
        "-t", str(duration), "-r", "25",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "26",
        "-c:a", "aac", "-b:a", "128k", "-shortest", out,
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return out

# --- 5. Pipeline الرئيسي ---
async def main_pipeline(topic: str) -> str:
    script = await plan_script(topic)
    
    async with aiohttp.ClientSession() as session:
        tasks = []
        for i, scene in enumerate(script["scenes"]):
            tasks.append(gen_image(session, scene["visual"], i))
            tasks.append(gen_voice(scene["narration"]))
        assets = await asyncio.gather(*tasks)
    
    scenes_mp4 = []
    for i, scene in enumerate(script["scenes"]):
        img, voice = assets[i*2], assets[i*2 + 1]
        scene_path = build_scene(img, voice, scene["duration"], i)
        scenes_mp4.append(scene_path)
    
    concat_list = f"{TMP}/concat.txt"
    with open(concat_list, "w") as f:
        for p in scenes_mp4:
            f.write(f"file '{p}'\n")
    
    final = f"{TMP}/final_{uuid.uuid4().hex}.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", concat_list, "-c", "copy", final
    ], check=True, capture_output=True)
    
    for p in scenes_mp4 + [concat_list]:
        try: os.remove(p)
        except: pass
    
    return final

# --- 6. أوامر البوت ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("أهلاً بك! البوت جاهز.\nأرسل: /video [الموضوع]")

async def video_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic = " ".join(context.args)
    if not topic:
        await update.message.reply_text("الرجاء كتابة الموضوع بعد الأمر.")
        return
    
    await update.message.reply_text(f"⏳ تم استلام موضوعك بنجاح: ({topic}). جاري المعالجة...")
    
    try:
        video_path = await main_pipeline(topic)
        with open(video_path, 'rb') as v:
            await update.message.reply_video(video=v, caption=f"🎬 الفيديو ديال: {topic}")
        os.remove(video_path)
    except Exception as e:
        await update.message.reply_text(f"❌ وقع خطأ أثناء التوليد: {str(e)}")

# --- 7. تشغيل Flask والبوت ---
@app.route("/")
def home():
    return "Bot is running live!"

def run_bot():
    if not TELEGRAM_TOKEN:
        return
    application = Application.builder().token(TELEGRAM_TOKEN).concurrent_updates(True).build()
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("video", video_command))
    application.run_polling(allowed_updates=Update.ALL_TYPES, stop_signals=None)

if __name__ == "__main__":
    threading.Thread(target=run_bot, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
