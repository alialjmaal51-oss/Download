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
    'geo_bypass': True,  # تجاوز القيود الجغرافية
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

# قاموس لتخزين بيانات المستخدمين مؤقتاً
user_video_info = {}
user_download_tasks = {}

# ------------------ دوال المساعدة ------------------
def format_bytes(size):
    """تنسيق حجم الملف"""
    return humanize.naturalsize(size) if size else "غير معروف"

def format_speed(bytes_per_sec):
    """تنسيق سرعة التحميل"""
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

def format_time(seconds):
    """تنسيق الوقت"""
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

def progress_bar(percentage, length=20):
    """إنشاء شريط تقدم"""
    filled = int(length * percentage // 100)
    bar = '█' * filled + '░' * (length - filled)
    return f"`{bar}`"

def is_video_url(url):
    """فحص إذا كان الرابط فيديو (مدعوم من yt-dlp)"""
    video_patterns = [
        r'youtube\.com',
        r'youtu\.be',
        r'facebook\.com',
        r'fb\.watch',
        r'vimeo\.com',
        r'dailymotion\.com',
        r'tiktok\.com',
        r'vt\.tiktok\.com',
        r'instagram\.com',
        r'twitter\.com',
        r'x\.com',
        r'twitch\.tv'
    ]
    return any(re.search(pattern, url.lower()) for pattern in video_patterns)

def is_tiktok_url(url):
    """فحص إذا كان الرابط من تيك توك"""
    tiktok_patterns = [
        r'tiktok\.com',
        r'vt\.tiktok\.com'
    ]
    return any(re.search(pattern, url.lower()) for pattern in tiktok_patterns)

async def get_video_formats(url):
    """جلب جميع الصيغ المتاحة للفيديو باستخدام yt-dlp"""
    ydl_opts = {
        **ydl_opts_base,
        'extract_flat': False,
        'format': 'all',
        'force_generic_extractor': False,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = info.get('formats', [])
            
            video_formats = []
            audio_formats = []
            
            for f in formats:
                format_note = f.get('format_note', '')
                ext = f.get('ext', '')
                filesize = f.get('filesize') or f.get('filesize_approx', 0)
                
                format_info = {
                    'format_id': f['format_id'],
                    'ext': ext,
                    'filesize': filesize,
                    'format_note': format_note,
                    'height': f.get('height', 0),
                    'vcodec': f.get('vcodec', 'none'),
                    'acodec': f.get('acodec', 'none'),
                    'fps': f.get('fps', 0)
                }
                
                if format_info['vcodec'] != 'none' and format_info['acodec'] != 'none':
                    video_formats.append(format_info)
                elif format_info['vcodec'] != 'none':
                    video_formats.append(format_info)
                elif format_info['acodec'] != 'none':
                    audio_formats.append(format_info)
            
            # ترتيب الصيغ حسب الجودة
            video_formats.sort(key=lambda x: x['height'], reverse=True)
            audio_formats.sort(key=lambda x: x['filesize'], reverse=True)
            
            return {
                'title': info.get('title', 'بدون عنوان'),
                'duration': info.get('duration', 0),
                'uploader': info.get('uploader', 'غير معروف'),
                'thumbnail': info.get('thumbnail', ''),
                'views': info.get('view_count', 0),
                'video_formats': video_formats,
                'audio_formats': audio_formats
            }
    except Exception as e:
        logger.error(f"Error getting video formats: {e}")
        return {'error': str(e)}

async def download_tiktok_direct(url, message, status_msg):
    """تحميل فيديو تيك توك مباشرة بدون خيارات (أعلى جودة)"""
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
            
            # البحث عن الملف المحمل
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
        logger.error(f"TikTok download error: {e}")
        await status_msg.edit_text(f"❌ خطأ في تحميل تيك توك: {str(e)[:100]}")
        # تنظيف الملفات المتبقية
        for f in os.listdir(DOWNLOAD_DIR):
            if 'tiktok' in f.lower() or 'vt' in f.lower():
                try:
                    os.remove(os.path.join(DOWNLOAD_DIR, f))
                except:
                    pass

def create_format_buttons(formats, prefix, page=0, items_per_page=5):
    """إنشاء أزرار للصيغ مع الصفحات"""
    buttons = []
    start = page * items_per_page
    end = start + items_per_page
    current_formats = formats[start:end]
    
    for f in current_formats:
        if f['height']:
            quality = f"{f['height']}p"
            if f.get('fps', 0) > 30:
                quality += f" {f['fps']}fps"
        elif f.get('format_note'):
            quality = f['format_note']
        else:
            quality = "غير معروف"
        
        size = format_bytes(f['filesize']) if f['filesize'] else 'غير معروف'
        ext = f['ext'].upper()
        
        button_text = f"{quality} - {ext} [{size}]"
        callback_data = f"{prefix}:{f['format_id']}"
        buttons.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
    
    # أزرار التنقل
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ السابق", callback_data=f"{prefix}_page:{page-1}"))
    if end < len(formats):
        nav_buttons.append(InlineKeyboardButton("التالي ➡️", callback_data=f"{prefix}_page:{page+1}"))
    
    if nav_buttons:
        buttons.append(nav_buttons)
    
    return buttons

async def download_and_upload_video(url, format_id, message, status_msg):
    """تحميل الفيديو بالصيغة المحددة ورفعه"""
    ydl_opts = {
        **ydl_opts_base,
        'format': format_id,
        'merge_output_format': 'mp4'
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
            if not os.path.exists(filename):
                for f in os.listdir(DOWNLOAD_DIR):
                    if info['title'] in f:
                        filename = os.path.join(DOWNLOAD_DIR, f)
                        break
            
            if os.path.exists(filename):
                await status_msg.edit_text("📤 **جاري رفع الملف...**")
                file_size = os.path.getsize(filename)
                caption = (
                    f"✅ **تم التحميل بنجاح!**\n\n"
                    f"🎬 **العنوان:** {info['title']}\n"
                    f"📊 **الحجم:** {format_bytes(file_size)}\n"
                    f"⏱️ **المدة:** {format_time(info.get('duration', 0))}\n"
                    f"👤 **الناشر:** {info.get('uploader', 'غير معروف')}\n\n"
                    f"🛡 **المطور:** هيثم محمود الجمال\n"
                )
                await message.reply_document(
                    document=filename,
                    caption=caption,
                    thumb=info.get('thumbnail')
                )
                os.remove(filename)
                await status_msg.delete()
            else:
                await status_msg.edit_text("❌ لم يتم العثور على الملف المحمل")
    except Exception as e:
        logger.error(f"Download error: {e}")
        await status_msg.edit_text(f"❌ خطأ في التحميل: {str(e)[:100]}")
        # تنظيف الملفات المتبقية
        for f in os.listdir(DOWNLOAD_DIR):
            if any(part in f for part in ['download', info.get('title', '')]):
                try:
                    os.remove(os.path.join(DOWNLOAD_DIR, f))
                except:
                    pass

async def download_regular_file(url, message, status_msg):
    """تحميل الملفات العادية (غير الفيديو)"""
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
                            
                            bar = progress_bar(percent)
                            text = (
                                f"**📥 جاري التحميل...**\n\n"
                                f"{bar}  **{percent:.1f}%**\n\n"
                                f"📦 {format_bytes(downloaded)} / {format_bytes(total)}\n"
                                f"⚡ {format_speed(speed)}\n"
                                f"⏱️ الوقت المنقضي: {format_time(elapsed)}"
                            )
                            await status_msg.edit_text(text)
                
                # رفع الملف
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

# ------------------ أوامر البوت ------------------
@app.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message: Message):
    welcome_text = (
        "**🌟 مرحباً بك في بوت التحميل الشامل المطور!**\n\n"
        "📥 **أرسل لي أي رابط وسأقوم بتحميله لك**\n\n"
        "**✨ المميزات:**\n"
        "• تحميل من **يوتيوب، فيسبوك، تيك توك، انستغرام** وآلاف المواقع\n"
        "• عرض جميع الصيغ المتاحة مع أحجامها وجوداتها\n"
        "• اختيار الجودة التي تريدها (صوت أو فيديو)\n"
        "• شريط تقدم وسرعة التحميل\n"
        "• تحميل الملفات العادية أيضاً\n"
        "• **تيك توك:** تحميل مباشر بدون خيارات 🚀\n\n"
        "**📝 الأوامر:**\n"
        "/start - بدء البوت\n"
        "/help - عرض المساعدة\n"
        "/cancel - إلغاء التحميل\n\n"
        "🚀 **أرسل الرابط الآن!**\n\n"
        "🛡 **المطور:** هيثم محمود الجمال\n"
    )
    await message.reply_text(welcome_text)

@app.on_message(filters.command("help") & filters.private)
async def help_cmd(client, message: Message):
    help_text = (
        "**📚 دليل الاستخدام:**\n\n"
        "**1️⃣ تحميل الفيديو:**\n"
        "• أرسل رابط فيديو (يوتيوب، فيسبوك، الخ)\n"
        "• اختر نوع التحميل (فيديو/صوت)\n"
        "• اختر الجودة المطلوبة\n"
        "• انتظر اكتمال التحميل والرفع\n\n"
        "**2️⃣ تحميل تيك توك:**\n"
        "• أرسل رابط تيك توك (tiktok.com أو vt.tiktok.com)\n"
        "• **سيتم التحميل مباشرة بدون خيارات** 🚀\n"
        "• سيتم رفع الفيديو بأعلى جودة متاحة\n\n"
        "**3️⃣ تحميل الملفات العادية:**\n"
        "• أرسل رابط الملف المباشر\n"
        "• سيتم التحميل والرفع تلقائياً\n\n"
        "**4️⃣ التحكم:**\n"
        "/cancel - إلغاء التحميل الحالي\n\n"
        "**⚠️ ملاحظات:**\n"
        "• الحد الأقصى للملفات: 2 جيجابايت\n"
        "• الروابط يجب أن تكون مباشرة أو من المواقع المدعومة\n\n"
        "🛡 **المطور:** هيثم محمود الجمال\n"
    )
    await message.reply_text(help_text)

@app.on_message(filters.command("cancel") & filters.private)
async def cancel_cmd(client, message: Message):
    user_id = message.from_user.id
    if user_id in user_video_info:
        del user_video_info[user_id]
        await message.reply_text("✅ **تم إلغاء العملية بنجاح**")
    else:
        await message.reply_text("❌ **لا يوجد عملية نشطة للإلغاء**")

@app.on_message(filters.text & filters.private)
async def handle_url(client, message: Message):
    url = message.text.strip()
    user_id = message.from_user.id
    
    # تجاهل الأوامر
    if url.startswith('/'):
        return
    
    # تجاهل الرسائل غير الروابط
    if not url.startswith(('http://', 'https://')):
        await message.reply_text("❌ **يرجى إرسال رابط صحيح يبدأ بـ http:// أو https://**")
        return
    
    status_msg = await message.reply_text("🔍 **جاري تحليل الرابط...**")
    
    # التحقق من نوع الرابط
    if is_tiktok_url(url):
        await download_tiktok_direct(url, message, status_msg)
        
    elif is_video_url(url):
        await status_msg.edit_text("🎬 **جاري جلب معلومات الفيديو...**")
        
        video_info = await get_video_formats(url)
        
        if 'error' in video_info:
            await status_msg.edit_text(f"❌ **خطأ:** {video_info['error']}")
            return
        
        # حفظ المعلومات
        user_video_info[user_id] = {
            'url': url,
            'info': video_info
        }
        
        # عرض معلومات الفيديو
        duration = format_time(video_info['duration']) if video_info['duration'] else 'غير معروف'
        views = f"{video_info['views']:,}" if video_info['views'] else 'غير معروف'
        
        text = (
            f"🎥 **{video_info['title']}**\n\n"
            f"👤 **الناشر:** {video_info['uploader']}\n"
            f"⏱️ **المدة:** {duration}\n"
            f"👁️ **المشاهدات:** {views}\n\n"
            f"**📋 اختر نوع التحميل:**"
        )
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎬 فيديو + صوت", callback_data=f"type:video")],
            [InlineKeyboardButton("🎵 صوت فقط", callback_data=f"type:audio")],
            [InlineKeyboardButton("❌ إلغاء", callback_data="cancel")]
        ])
        
        await status_msg.edit_text(text, reply_markup=keyboard)
        
    else:
        # رابط ملف عادي
        await status_msg.edit_text("📥 **جاري تحميل الملف...**")
        await download_regular_file(url, message, status_msg)

@app.on_callback_query()
async def handle_callback(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    data = callback_query.data
    
    if data == "cancel":
        await callback_query.message.edit_text("❌ **تم إلغاء العملية**")
        await callback_query.answer()
        return
    
    if user_id not in user_video_info:
        await callback_query.answer("انتهت الجلسة، أرسل الرابط مجدداً", show_alert=True)
        return
    
    video_info = user_video_info[user_id]
    
    if data.startswith("type:"):
        choice = data.split(":")[1]
        
        if choice == "video":
            formats = video_info['info']['video_formats']
            if not formats:
                await callback_query.answer("لا توجد صيغ فيديو متاحة", show_alert=True)
                return
            
            buttons = create_format_buttons(formats, "video", 0)
            keyboard = InlineKeyboardMarkup(buttons)
            
            await callback_query.message.edit_text(
                "🎬 **اختر جودة الفيديو:**",
                reply_markup=keyboard
            )
            
        elif choice == "audio":
            formats = video_info['info']['audio_formats']
            if not formats:
                await callback_query.answer("لا توجد صيغ صوت متاحة", show_alert=True)
                return
            
            buttons = create_format_buttons(formats, "audio", 0)
            keyboard = InlineKeyboardMarkup(buttons)
            
            await callback_query.message.edit_text(
                "🎵 **اختر جودة الصوت:**",
                reply_markup=keyboard
            )
    
    elif data.startswith("video_page:") or data.startswith("audio_page:"):
        prefix = data.split("_")[0]
        page = int(data.split(":")[1])
        
        formats = video_info['info'][f'{prefix}_formats']
        buttons = create_format_buttons(formats, prefix, page)
        keyboard = InlineKeyboardMarkup(buttons)
        
        await callback_query.message.edit_text(
            f"{'🎬 فيديو' if prefix == 'video' else '🎵 صوت'} - اختر الجودة:",
            reply_markup=keyboard
        )
    
    elif data.startswith("video:") or data.startswith("audio:"):
        prefix, format_id = data.split(":")
        
        await callback_query.message.edit_text("⏳ **جاري التحميل والمعالجة...**")
        
        url = video_info['url']
        await download_and_upload_video(url, format_id, callback_query.message, callback_query.message)
        
        # تنظيف البيانات
        if user_id in user_video_info:
            del user_video_info[user_id]
    
    await callback_query.answer()

# ------------------ تشغيل البوت ------------------
if __name__ == "__main__":
    try:
        logger.info("🤖 البوت الشامل يعمل على Hugging Face...")
        logger.info("👨‍💻 المطور: هيثم محمود الجمال")
        logger.info(f"📁 مجلد التحميل: {DOWNLOAD_DIR}")
        if PROXY:
            logger.info(f"🔒 استخدام وكيل: {PROXY}")
        else:
            logger.info("⚠️ لم يتم تعيين وكيل. إذا واجهت مشكلة في تحليل DNS، قم بتعيين HTTP_PROXY أو HTTPS_PROXY.")
        logger.info("🚀 جاري تشغيل البوت...")
        
        app.run()
        
    except Exception as e:
        logger.error(f"❌ فشل تشغيل البوت: {e}")
        raise