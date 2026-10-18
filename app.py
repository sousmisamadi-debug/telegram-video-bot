import asyncio
import os
import tempfile
import threading
from flask import Flask, jsonify, request
import google.generativeai as genAI
from moviepy.editor import AudioFileClip, ImageClip, concatenate_videoclips
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# قراءة المتغيرات السرية من النظام (Render Environment Variables)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MY_USER_ID = int(os.getenv("MY_USER_ID", "6913390724"))

# تهيئة Gemini
genAI.configure(api_key=GEMINI_API_KEY)

app = Flask(__name__)


# مسار Health Check لكي يستجيب لـ UptimeRobot ويمنع الخمول
@app.route("/")
def home():
  return "Video Factory Agent is Running Online!", 200


@app.route("/health")
def health():
  return jsonify({"status": "healthy"}), 200


# دالة لتوليد القصة والسيناريو عبر Gemini بمعايير صارمة ونظيفة
def generate_clean_story(prompt_topic):
  model = genAI.GenerativeModel("gemini-1.5-flash")

  system_instruction = (
      "أنت وكيل ذكاء اصطناعي محترف لتوليد قصص قصيرة تاريخية أو غامضة وهادفة."
      " الشروط الصارمة جداً التي يجب أن تلتزم بها بنسبة 100%:"
      " 1. المحتوى يجب أن يكون نظيفاً تماماً، أخلاقياً، يحترم الدين ولا يمسه بصلة."
      " 2. منع تام لأي سب، قذف، ألفاظ نابية، أو إيحاءات غير أخلاقية."
      " 3. التركيز على القيم النبيلة، العبر، أو الحقائق التاريخية والعلمية المشوقة."
      " 4. قسّم القصة إلى 3 مشاهد قصيرة جداً."
      " لكل مشهد أعطني جزئين: النص المسموع (Voiceover text) باللغة العربية الفصحى المبسطة،"
      " ووصف بصري باللغة الإنجليزية (Image prompt) لتوليد صورة سينمائية معبرة."
      " اجعل المخرجات واضحة ومرتبة."
  )

  full_prompt = (
      f"{system_instruction}\n\nموضوع القصة المطلوب: {prompt_topic}"
  )
  response = model.generate_content(full_prompt)
  return response.text


# توليد صورة من Pollinations.ai وتحميلها مؤقتاً
def download_image(prompt_text, save_path):
  clean_prompt = prompt_text.replace(" ", "%20")
  url = f"https://image.pollinations.ai/prompt/{clean_prompt}?width=540&height=960&nologo=true"
  try:
    response = requests.get(url, timeout=30)
    if response.status_code == 200:
      with open(save_path, "wb") as f:
        f.write(response.content)
      return True
  except Exception as e:
    print(f"Error downloading image: {e}")
  return False


# توليد الصوت باستخدام edge-tts
async def generate_audio(text, output_path):
  import edge_tts

  voice = "ar-SA-ZariyahNeural"  # صوت عربي طبيعي ونقي
  communicate = edge_tts.Communicate(text, voice)
  await communicate.save(output_path)


# دمج الصور والصوت لإنتاج فيديو MP4
def create_video_from_scenes(scenes_data, audio_path, output_video_path):
  try:
    audio_clip = AudioFileClip(audio_path)
    total_duration = audio_clip.duration
    duration_per_scene = total_duration / len(scenes_data)

    image_clips = []
    temp_files = []

    for i, scene in enumerate(scenes_data):
      img_path = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False).name
      temp_files.append(img_path)

      # تحميل الصورة
      success = download_image(
          scene.get(
              "img_prompt",
              "cinematic historical mystery background, high quality",
          ),
          img_path,
      )
      if not success:
        # صورة افتراضية في حال الفشل
        download_image("ancient mysterious background", img_path)

      img_clip = ImageClip(img_path).set_duration(duration_per_scene)
      image_clips.append(img_clip)

    # دمج المقاطع البصرية
    video = concatenate_videoclips(image_clips, method="compose")
    video = video.set_audio(audio_clip)

    # كتابة ملف الفيديو النهائي
    video.write_videofile(
        output_video_path,
        fps=24,
        codec="libx264",
        audio_codec="aac",
        preset="ultrafast",
        logger=None,
    )

    # إغلاق المقاطع لتنظيف الذاكرة
    audio_clip.close()
    video.close()
    for f in temp_files:
      try:
        os.remove(f)
      except:
        pass
    return True
  except Exception as e:
    print(f"Error in video creation: {e}")
    return False


# دالة لبدء عملية معالجة القصة وإرسال الفيديو لتليجرام
async def process_and_send_video(update: Update, context: ContextTypes.DEFAULT_TYPE, topic: str):
  user_id = update.effective_user.id
  if user_id != MY_USER_ID:
    await update.message.reply_text("عذراً، هذا البوت مخصص للاستخدام الشخصي فقط.")
    return

  await update.message.reply_text(
      "⏳ جاري توليد القصة التاريخية وتجهيز الصور والصوت والمونتاج الآلي... انتظر قليلاً."
  )

  try:
    # 1. توليد النص بالذكاء الاصطناعي
    story_text = generate_clean_story(topic)

    # تقسيم مشاهد افتراضية مرتبطة بالموضوع
    scenes = [
        {
            "text": "قصة تاريخية مشوقة تحمل في طياتها عبرة عظيمة.",
            "img_prompt": f"ancient historical scene about {topic}, cinematic, 8k",
        },
        {
            "text": "أحداث غامضة تتكشف تدريجياً لتظهر الحقيقة.",
            "img_prompt": f"mysterious ancient atmosphere, dramatic lighting, {topic}",
        },
        {
            "text": "عبرة خالدة تبقى عبر الأزمان والعصور.",
            "img_prompt": f"inspiring historical conclusion, cinematic lighting, {topic}",
        },
    ]

    full_audio_text = " . ".join([s["text"] for s in scenes])
    audio_file = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False).name
    video_file = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name

    # 2. توليد الصوت
    await generate_audio(full_audio_text, audio_file)

    # 3. إنتاج الفيديو عبر MoviePy
    success = create_video_from_scenes(scenes, audio_file, video_file)

    if success and os.path.exists(video_file):
      # 4. إرسال الفيديو الجاهز إلى تيليجرام
      with open(video_file, "rb") as vid:
        await update.message.reply_video(
            video=vid,
            caption=(
                "🎬 **تم إنتاج الفيديو بنجاح!**\n\n"
                f"📌 الموضوع: {topic}\n\n"
                "✨ جاهز للرفع على تيك توك وريلز يوتيوب!"
            ),
            parse_mode="Markdown",
        )
    else:
      await update.message.reply_text(
          "❌ حدث خطأ أثناء عملية دمج وإنتاج الفيديو."
      )

    # تنظيف الملفات المؤقتة
    try:
      os.remove(audio_file)
      os.remove(video_file)
    except:
      pass

  except Exception as e:
    await update.message.reply_text(f"❌ حدث خطأ تقني: {str(e)}")


# أمر البدء في تليجرام
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
  await update.message.reply_text(
      "مرحباً بك في مصنع الفيديوهات الآلي! 🚀\n"
      "أرسل لي موضوعاً تاريخياً أو غامضاً، وسأقوم بتوليد الفيديو (صوت + صور + مونتاج MP4) وإرساله لك جاهزاً.\n\n"
      "مثال: `/video قصة اختراع الإسطرلاب في الأندلس`"
  )


# أمر توليد الفيديو
async def video_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
  topic = " ".join(context.args)
  if not topic:
    await update.message.reply_text(
        "الرجاء كتابة الموضوع بعد الأمر. مثال:\n`/video لغز مدينة ارم ذات العماد`"
    )
    return
  await process_and_send_video(update, context, topic)


# تشغيل بوت تليجرام في الخلفية
def run_telegram_bot():
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    application = Application.builder().token(os.environ.get("TELEGRAM_TOKEN")).build()
    
    # اترك الهاندلرز (Handlers) الخاصة بك هنا كما هي في كودك:
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("video", video_command))
    
    application.run_polling()
