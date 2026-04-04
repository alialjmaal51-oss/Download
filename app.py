from flask import Flask
import threading
import os
import asyncio
import aiohttp
import time
import yt_dlp
import re
import humanize
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import logging
import dns.resolver

# إعداد DNS لتجاوز مشاكل الاستضافة
try:
    dns.resolver.default_resolver = dns.resolver.Resolver(configure=False)
    dns.resolver.default_resolver.nameservers = ['8.8.8.8', '1.1.1.1']
    logging.info("DNS set to 8.8.8.8 and 1.1.1.1")
except Exception as e:
    logging.warning(f"Could not set custom DNS: {e}")

# إعداد التسجيل
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- سيرفر Flask الوهمي لإبقاء البوت نشطاً ---
server = Flask(__name__)

@server.route('/')
def home():
    return "Bot is Running - Developed by: هيثم محمود الجمال"

@server.route('/health')
def health():
    return "OK", 200

def run_server():
    try:
        server.run(host="0.0.0.0", port=7860, threaded=True)
    except Exception as e:
        logger.error(f"Server error: {e}")

threading.Thread(target=run_server, daemon=True).start()
# ------------------------------------------

# التحقق من المتغيرات البيئية
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# إعدادات الوكيل (proxy) لتجاوز حظر Hugging Face
PROXY = os.getenv("HTTP_PROXY") or os.getenv("HTTPS_PROXY") or None
if PROXY:
    logger.info(f"Using proxy: {PROXY}")
else:
    logger.warning("No proxy set. If DNS errors persist, set HTTP_PROXY or HTTPS_PROXY.")

if not API_ID or not API_HASH or not BOT_TOKEN:
    logger.error("Missing required environment variables!")
    raise ValueError("Please set API_ID, API_HASH, and BOT_TOKEN")

# إعدادات التحميل
DOWNLOAD_DIR = "/tmp"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# إعداد yt-dlp مع إمكانية استخدام وكيل
ydl_opts_base = {
    'quiet': True,
    'no_warnings': True,
    'noplaylist': True,
    'restrictfilenames': True,
    'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),
    'geo_bypass': True,
}
if PROXY:
    ydl_opts_base['proxy'] = PROXY

# إنشاء البوت
app = Client(
    "super_download_bot",
    api_id=int(API_ID),
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workdir=DOWNLOAD_DIR,
    in_memory=True
)

# قاموس لتخزين بيانات المستخدمين مؤقتاً (للإلغاء)
user_download_tasks = {}

# ------------------ دوال المساعدة ------------------
def format_bytes(size):
    return humanize.naturalsize(size) if size else "غير معروف"

def format_time(seconds):
    if not seconds:
        return "غير معروف"
    if seconds < 60:
        return f"{seconds:.0f} ثانية"
    elif seconds < 3600:
        return f"{seconds/60:.1f} دقيقة"
    elif seconds < 86400:
        return f"{seconds/3600:.1f} ساعة"
    else:
        return f"{seconds/86400:.1f} يوم"

def is_video_url(url):
    video_patterns = [
        r'youtube\.com', r'youtu\.be', r'facebook\.com', r'fb\.watch',
        r'vimeo\.com', r'dailymotion\.com', r'tiktok\.com', r'vt\.tiktok\.com',
        r'instagram\.com', r'twitter\.com', r'x\.com', r'twitch\.tv'
    ]
    return any(re.search(pattern, url.lower()) for pattern in video_patterns)

def is_tiktok_url(url):
    return bool(re.search(r'tiktok\.com|vt\.tiktok\.com', url.lower()))

# تحميل مباشر لأي فيديو بأعلى جودة (بدون اختيار صيغ)
async def download_best_video(url, message, status_msg):
    ydl_opts = {
        **ydl_opts_base,
        'format': 'bestvideo+bestaudio/best',
        'merge_output_format': 'mp4'
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            await status_msg.edit_text("📥 **جاري تحميل الفيديو بأعلى جودة...**")
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            if not os.path.exists(filename):
                for f in os.listdir(DOWNLOAD_DIR):
                    if info['title'] in f:
                        filename = os.path.join(DOWNLOAD_DIR, f)
                        break
            if os.path.exists(filename):
                await status_msg.edit_text("📤 **جاري رفع الفيديو...**")
                file_size = os.path.getsize(filename)
                caption = (
                    f"✅ **تم التحميل بنجاح!**\n\n"
                    f"🎬 **العنوان:** {info['title']}\n"
                    f"📊 **الحجم:** {format_bytes(file_size)}\n"
                    f"⏱️ **المدة:** {format_time(info.get('duration', 0))}\n"
                    f"👤 **الناشر:** {info.get('uploader', 'غير معروف')}\n\n"
                    f"🛡 **المطور:** هيثم محمود الجمال\n"
                )
                await message.reply_video(
                    video=filename,
                    caption=caption,
                    width=info.get('width', 0),
                    height=info.get('height', 0),
                    duration=info.get('duration', 0)
                )
                os.remove(filename)
                await status_msg.delete()
            else:
                await status_msg.edit_text("❌ لم يتم العثور على الملف المحمل")
    except Exception as e:
        logger.error(f"Download error: {e}")
        await status_msg.edit_text(f"❌ خطأ في التحميل: {str(e)[:100]}")
        # تنظيف
        for f in os.listdir(DOWNLOAD_DIR):
            if 'download' in f or ('title' in locals() and info.get('title') in f):
                try:
                    os.remove(os.path.join(DOWNLOAD_DIR, f))
                except:
                    pass

async def download_tiktok_direct(url, message, status_msg):
    # نفس الكود السابق لتحميل التيك توك
    ydl_opts = {
        **ydl_opts_base,
        'format': 'bestvideo+bestaudio/best',
        'merge_output_format': 'mp4'
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            await status_msg.edit_text("📱 **جاري تحميل فيديو تيك توك...**")
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            if not os.path.exists(filename):
                for f in os.listdir(DOWNLOAD_DIR):
                    if info['title'] in f:
                        filename = os.path.join(DOWNLOAD_DIR, f)
                        break
            if os.path.exists(filename):
                await status_msg.edit_text("📤 **جاري رفع الفيديو...**")
                file_size = os.path.getsize(filename)
                caption = (
                    f"✅ **تم التحميل بنجاح!**\n\n"
                    f"📱 **تيك توك**\n"
                    f"🎬 **العنوان:** {info['title']}\n"
                    f"📊 **الحجم:** {format_bytes(file_size)}\n"
                    f"⏱️ **المدة:** {format_time(info.get('duration', 0))}\n"
                    f"👤 **الناشر:** {info.get('uploader', 'غير معروف')}\n\n"
                    f"🛡 **المطور:** هيثم محمود الجمال\n"
                )
                await message.reply_video(
                    video=filename,
                    caption=caption,
                    width=info.get('width', 0),
                    height=info.get('height', 0),
                    duration=info.get('duration', 0)
                )
                os.remove(filename)
                await status_msg.delete()
            else:
                await status_msg.edit_text("❌ لم يتم العثور على الفيديو المحمل")
    except Exception as e:
        logger.error(f"TikTok error: {e}")
        await status_msg.edit_text(f"❌ خطأ في تحميل تيك توك: {str(e)[:100]}")
        for f in os.listdir(DOWNLOAD_DIR):
            if 'tiktok' in f.lower() or 'vt' in f.lower():
                try:
                    os.remove(os.path.join(DOWNLOAD_DIR, f))
                except:
                    pass

async def download_regular_file(url, message, status_msg):
    file_name = url.split('/')[-1].split('?')[0]
    if not file_name or '.' not in file_name:
        file_name = f"download_{datetime.now().strftime('%Y%m%d_%H%M%S')}.bin"
    filepath = os.path.join(DOWNLOAD_DIR, file_name)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    await status_msg.edit_text(f"❌ فشل التحميل. رمز الحالة: {resp.status}")
                    return
                total = int(resp.headers.get('content-length', 0))
                downloaded = 0
                start_time = time.time()
                with open(filepath, 'wb') as f:
                    async for chunk in resp.content.iter_chunked(1024 * 1024):
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            percent = (downloaded / total) * 100
                            elapsed = time.time() - start_time
                            speed = downloaded / elapsed if elapsed > 0 else 0
                            bar = '█' * int(20 * percent // 100) + '░' * (20 - int(20 * percent // 100))
                            text = f"**📥 جاري التحميل...**\n\n`{bar}`  **{percent:.1f}%**\n\n📦 {format_bytes(downloaded)} / {format_bytes(total)}\n⚡ {format_speed(speed)}\n⏱️ الوقت المنقضي: {format_time(elapsed)}"
                            await status_msg.edit_text(text)
                await status_msg.edit_text("📤 **جاري رفع الملف...**")
                await message.reply_document(
                    document=filepath,
                    caption=f"✅ **تم التحميل بنجاح!**\n\n📄 **الملف:** `{file_name}`\n📊 **الحجم:** {format_bytes(total)}\n\n🛡 **المطور:** هيثم محمود الجمال\n"
                )
                os.remove(filepath)
    except Exception as e:
        logger.error(f"Regular file error: {e}")
        await status_msg.edit_text(f"❌ خطأ: {str(e)[:100]}")
        if os.path.exists(filepath):
            os.remove(filepath)

def format_speed(bytes_per_sec):
    if not bytes_per_sec:
        return "0 B/s"
    if bytes_per_sec < 1024:
        return f"{bytes_per_sec:.2f} B/s"
    elif bytes_per_sec < 1024**2:
        return f"{bytes_per_sec/1024:.2f} KB/s"
    elif bytes_per_sec < 1024**3:
        return f"{bytes_per_sec/1024**2:.2f} MB/s"
    else:
        return f"{bytes_per_sec/1024**3:.2f} GB/s"

# ------------------ أوامر البوت ------------------
@app.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message: Message):
    await message.reply_text(
        "**🌟 مرحباً بك في بوت التحميل الشامل المطور!**\n\n"
        "📥 **أرسل لي أي رابط وسأقوم بتحميله وإرساله لك مباشرة**\n\n"
        "**✨ المميزات:**\n"
        "• تحميل فيديوهات يوتيوب، فيسبوك، انستغرام، تيك توك، وغيرها بأعلى جودة\n"
        "• تحميل الملفات العادية أيضاً\n"
        "• شريط تقدم وسرعة التحميل\n\n"
        "**📝 الأوامر:**\n"
        "/start - بدء البوت\n"
        "/help - عرض المساعدة\n"
        "/cancel - إلغاء التحميل الحالي\n\n"
        "🚀 **أرسل الرابط الآن!**\n\n"
        "🛡 **المطور:** هيثم محمود الجمال"
    )

@app.on_message(filters.command("help") & filters.private)
async def help_cmd(client, message: Message):
    await start_cmd(client, message)

@app.on_message(filters.command("cancel") & filters.private)
async def cancel_cmd(client, message: Message):
    user_id = message.from_user.id
    if user_id in user_download_tasks:
        # يمكن إضافة منطق لإلغاء التحميل إذا أردت
        del user_download_tasks[user_id]
        await message.reply_text("✅ **تم إلغاء العملية بنجاح**")
    else:
        await message.reply_text("❌ **لا يوجد عملية نشطة للإلغاء**")

@app.on_message(filters.text & filters.private)
async def handle_url(client, message: Message):
    url = message.text.strip()
    if url.startswith('/'):
        return
    if not url.startswith(('http://', 'https://')):
        await message.reply_text("❌ **يرجى إرسال رابط صحيح يبدأ بـ http:// أو https://**")
        return
    
    status_msg = await message.reply_text("🔍 **جاري تحليل الرابط...**")
    
    if is_tiktok_url(url):
        await download_tiktok_direct(url, message, status_msg)
    elif is_video_url(url):
        await download_best_video(url, message, status_msg)
    else:
        await status_msg.edit_text("📥 **جاري تحميل الملف...**")
        await download_regular_file(url, message, status_msg)

# ------------------ تشغيل البوت ------------------
if __name__ == "__main__":
    try:
        logger.info("🤖 البوت الشامل يعمل على Hugging Face...")
        logger.info("👨‍💻 المطور: هيثم محمود الجمال")
        logger.info(f"📁 مجلد التحميل: {DOWNLOAD_DIR}")
        if PROXY:
            logger.info(f"🔒 استخدام وكيل: {PROXY}")
        else:
            logger.info("⚠️ لم يتم تعيين وكيل.")
        logger.info("🚀 جاري تشغيل البوت...")
        app.run()
    except Exception as e:
        logger.error(f"❌ فشل تشغيل البوت: {e}")
        raise
