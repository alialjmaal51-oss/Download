import logging
import sqlite3
import os
import time
import asyncio
import yt_dlp
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters, CallbackQueryHandler

TOKEN = os.getenv("TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "5570615802"))

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

DB_NAME = "bot_database.db"

TRANS = {
    'en': {
        'welcome': "❖ 𝐖𝐞𝐥𝐜𝐨𝐦𝐞 <b>{name}</b> ❖\n\n⚡︎ 𝐅𝐚𝐬𝐭𝐞𝐬𝐭 𝐌𝐞𝐝𝐢𝐚 𝐃𝐨𝐰𝐧𝐥𝐨𝐚𝐝𝐞𝐫 ⚡︎\n\n➢ 𝐒𝐮𝐩𝐩𝐨𝐫𝐭𝐬: 𝐘𝐨𝐮𝐓𝐮𝐛𝐞, 𝐓𝐢𝐤𝐓𝐨𝐤, 𝐈𝐆, 𝐅𝐁...\n➢ 𝐀𝐧𝐝 𝟏𝟎𝟎𝟎+ 𝐨𝐭𝐡𝐞𝐫 𝐬𝐢𝐭𝐞𝐬.\n➢ 𝐉𝐮𝐬𝐭 𝐬𝐞𝐧𝐝 𝐭𝐡𝐞 𝐔𝐑𝐋 𝐭𝐨 𝐬𝐭𝐚𝐫𝐭.\n\n❴ 𝐏𝐨𝐰𝐞𝐫𝐞𝐝 𝐛𝐲 𝐲𝐭-𝐝𝐥𝐩 ❵",
        'maintenance': "⚠︎ 𝐓𝐡𝐞 𝐁𝐨𝐭 𝐢𝐬 𝐮𝐧𝐝𝐞𝐫 𝐦𝐚𝐢𝐧𝐭𝐞𝐧𝐚𝐧𝐜𝐞 𝐧𝐨𝐰.",
        'process': "➢ 𝐏𝐫𝐨𝐜𝐞𝐬𝐬𝐢𝐧𝐠 𝐘𝐨𝐮𝐫 𝐑𝐞𝐪𝐮𝐞𝐬𝐭 ⚡︎...",
        'downloading': "⬇︎ 𝐃𝐨𝐰𝐧𝐥𝐨𝐚𝐝𝐢𝐧𝐠...",
        'uploading': "⬆︎ 𝐔𝐩𝐥𝐨𝐚𝐝𝐢𝐧𝐠 𝐭𝐨 𝐓𝐞𝐥𝐞𝐠𝐫𝐚𝐦...",
        'error_generic': "✕ 𝐄𝐫𝐫𝐨𝐫: {error}",
        'error_size': "✕ 𝐅𝐢𝐥𝐞 𝐢𝐬 𝐭𝐨𝐨 𝐥𝐚𝐫𝐠𝐞 𝐟𝐨𝐫 𝐓𝐞𝐥𝐞𝐠𝐫𝐚𝐦 (𝐋𝐢𝐦𝐢𝐭 𝟓𝟎𝐌𝐁).",
        'send_url': "⚠︎ 𝐏𝐥𝐞𝐚𝐬𝐞 𝐬𝐞𝐧𝐝 𝐚 𝐯𝐚𝐥𝐢𝐝 𝐔𝐑𝐋.",
        'caption': "❖ <b>{title}</b>\n\n➢ 𝐃𝐨𝐰𝐧𝐥𝐨𝐚𝐝𝐞𝐝 𝐛𝐲: @{bot_user}",
        'sites_btn': "⟡ 𝐒𝐮𝐩𝐩𝐨𝐫𝐭𝐞𝐝 𝐒𝐢𝐭𝐞𝐬 ⟡",
        'settings_btn': "⚙️ 𝐒𝐞𝐭𝐭𝐢𝐧𝐠𝐬",
        'sites_title': "❖ <b>𝐒𝐮𝐩𝐩𝐨𝐫𝐭𝐞𝐝 𝐒𝐢𝐭𝐞𝐬 (𝟏𝟎𝟎𝟎+)</b> ❖\n\n➢ YouTube\n➢ Instagram\n➢ TikTok\n➢ Facebook\n➢ Twitter (X)\n➢ SoundCloud\n➢ Twitch\n➢ Pinterest\n➢ Vimeo\n➢ Dailymotion\n\n➕ 𝐀𝐧𝐝 𝐀𝐥𝐦𝐨𝐬𝐭 𝐀𝐧𝐲 𝐎𝐭𝐡𝐞𝐫 𝐒𝐢𝐭𝐞!",
        'back': "🔙 𝐁𝐚𝐜𝐤",
        'select_lang_msg': "❖ 𝐏𝐥𝐞𝐚𝐬𝐞 𝐒𝐞𝐥𝐞𝐜𝐭 𝐘𝐨𝐮𝐫 𝐋𝐚𝐧𝐠𝐮𝐚𝐠𝐞",
        'lang_set': "✅ 𝐋𝐚𝐧𝐠𝐮𝐚𝐠𝐞 𝐬𝐞𝐭 𝐭𝐨 𝐄𝐧𝐠𝐥𝐢𝐬𝐡"
    },
    'ar': {
        'welcome': "❖ <b>أهلاً بك {name}</b> ❖\n\n⚡︎ <b>أقوى بوت تحميل ميديا</b> ⚡︎\n\n➢ يدعم: يوتيوب، تيك توك، انستا، فيسبوك...\n➢ وأكثر من 1000 موقع آخر.\n➢ فقط أرسل الرابط للبدء.\n\n❴ يعمل بقوة yt-dlp ❵",
        'maintenance': "⚠︎ البوت تحت الصيانة حالياً.",
        'process': "➢ جاري معالجة طلبك ⚡︎...",
        'downloading': "⬇︎ جاري التحميل...",
        'uploading': "⬆︎ جاري الرفع إلى تيليجرام...",
        'error_generic': "✕ حدث خطأ: {error}",
        'error_size': "✕ الملف كبير جداً (حد تيليجرام 50 ميجا).",
        'send_url': "⚠︎ الرجاء إرسال رابط صالح.",
        'caption': "❖ <b>{title}</b>\n\n➢ تم التحميل بواسطة: @{bot_user}",
        'sites_btn': "⟡ المواقع المدعومة ⟡",
        'settings_btn': "⚙️ الإعدادات",
        'sites_title': "❖ <b>المواقع المدعومة (1000+)</b> ❖\n\n➢ يوتيوب (YouTube)\n➢ انستقرام (Instagram)\n➢ تيك توك (TikTok)\n➢ فيسبوك (Facebook)\n➢ تويتر (X)\n➢ ساوند كلاود (SoundCloud)\n➢ بينتيريست (Pinterest)\n➢ تويتش (Twitch)\n➢ فيميو (Vimeo)\n\n➕ وتقريباً أي موقع فيديو آخر!",
        'back': "🔙 رجوع",
        'select_lang_msg': "❖ اختر لغتك المفضلة\n❖ Select Language",
        'lang_set': "✅ تم تعيين اللغة العربية"
    }
}

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, date_joined TEXT, language TEXT)''')
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN language TEXT")
    except:
        pass
    cursor.execute('''CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY, maintenance_mode INTEGER DEFAULT 0, ban_list TEXT DEFAULT '')''')
    cursor.execute('SELECT count(*) FROM settings')
    if cursor.fetchone()[0] == 0:
        cursor.execute('INSERT INTO settings (id, maintenance_mode, ban_list) VALUES (1, 0, "")')
    conn.commit()
    conn.close()

def get_db_connection():
    return sqlite3.connect(DB_NAME)

def get_mandatory_buttons():
    return [[InlineKeyboardButton("𓄼𝗗𝗲𝘃𓄹", url="https://t.me/albashekaljmaal2")], [InlineKeyboardButton("𓄼𝗦𝗼𝘂𝗿𝗰𝗲𓄹", url="https://t.me/albashekaljmaal")]]

def get_user_lang(user_id):
    conn = get_db_connection()
    res = conn.execute('SELECT language FROM users WHERE user_id = ?', (user_id,)).fetchone()
    conn.close()
    return res[0] if res and res[0] else None

def format_size(bytes):
    if bytes is None or bytes == 0:
        return "Unknown"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes < 1024.0:
            return f"{bytes:.1f} {unit}"
        bytes /= 1024.0
    return f"{bytes:.1f} TB"

def get_video_formats(url):
    """استخراج صيغ الفيديو المتاحة (فيديو ثم mp3) مع الأحجام"""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = info.get('formats', [])
            
            video_formats = []
            audio_formats = []
            
            for f in formats:
                # تنسيق فيديو (يحتوي على فيديو)
                if f.get('vcodec') != 'none':
                    resolution = f.get('resolution') or f.get('format_note') or 'Unknown'
                    size = f.get('filesize') or f.get('filesize_approx') or 0
                    video_formats.append({
                        'format_id': f['format_id'],
                        'resolution': resolution,
                        'size': size,
                        'size_str': format_size(size),
                        'type': 'video'
                    })
                # تنسيق صوت فقط (سنحوله لـ mp3)
                elif f.get('acodec') != 'none' and f.get('vcodec') == 'none':
                    size = f.get('filesize') or f.get('filesize_approx') or 0
                    audio_formats.append({
                        'format_id': f['format_id'],
                        'size': size,
                        'size_str': format_size(size),
                        'type': 'audio'
                    })
            
            # ترتيب الفيديو حسب الدقة تنازلياً (أعلى دقة أولاً)
            def resolution_key(f):
                res = f['resolution']
                match = re.search(r'(\d+)', res)
                return int(match.group(1)) if match else 0
            video_formats.sort(key=resolution_key, reverse=True)
            
            # اختيار أفضل تنسيق صوت (أعلى جودة - أكبر حجم)
            if audio_formats:
                audio_formats.sort(key=lambda x: x['size'], reverse=True)
                best_audio = audio_formats[0]
                best_audio['resolution'] = 'mp3'
            else:
                best_audio = None
            
            return video_formats, best_audio
    except Exception as e:
        logging.error(f"Error fetching formats: {e}")
        return [], None

async def download_with_format(url, format_id, is_audio, user_id, status_msg, context):
    """تحميل الفيديو أو الصوت بالصيغة المحددة"""
    file_path = f"downloads/{user_id}_{int(time.time())}"
    ydl_opts = {
        'format': format_id,
        'outtmpl': file_path + '.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'max_filesize': 50 * 1024 * 1024,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    if is_audio:
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
        ydl_opts['outtmpl'] = file_path + '.%(ext)s'
    
    lang = get_user_lang(user_id) or 'en'
    try:
        await status_msg.edit_text(TRANS[lang]['downloading'], reply_markup=InlineKeyboardMarkup(get_mandatory_buttons()))
        loop = asyncio.get_event_loop()
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=True))
            if is_audio:
                filename = file_path + '.mp3'
                if not os.path.exists(filename):
                    # قد يكون الملف بصيغة أخرى مؤقتة
                    for f in os.listdir('downloads'):
                        if f.startswith(os.path.basename(file_path)) and f.endswith('.mp3'):
                            filename = os.path.join('downloads', f)
                            break
            else:
                filename = ydl.prepare_filename(info)
                if not os.path.exists(filename):
                    for f in os.listdir('downloads'):
                        if f.startswith(os.path.basename(file_path)):
                            filename = os.path.join('downloads', f)
                            break
            title = info.get('title', 'Media')
        
        if not os.path.exists(filename):
            raise Exception("Download failed")
        
        await status_msg.edit_text(TRANS[lang]['uploading'], reply_markup=InlineKeyboardMarkup(get_mandatory_buttons()))
        caption = TRANS[lang]['caption'].format(title=title, bot_user=context.bot.username)
        
        with open(filename, 'rb') as f:
            if is_audio:
                await context.bot.send_audio(chat_id=user_id, audio=f, caption=caption, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(get_mandatory_buttons()))
            else:
                await context.bot.send_video(chat_id=user_id, video=f, caption=caption, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(get_mandatory_buttons()))
        
        os.remove(filename)
        await status_msg.delete()
    except yt_dlp.utils.DownloadError as e:
        if "File is larger than" in str(e):
            await status_msg.edit_text(TRANS[lang]['error_size'], reply_markup=InlineKeyboardMarkup(get_mandatory_buttons()))
        else:
            await status_msg.edit_text(TRANS[lang]['error_generic'].format(error="Unsupported or private link"), reply_markup=InlineKeyboardMarkup(get_mandatory_buttons()))
    except Exception as e:
        logging.error(f"Download error: {e}")
        await status_msg.edit_text(TRANS[lang]['error_generic'].format(error=str(e)[:100]), reply_markup=InlineKeyboardMarkup(get_mandatory_buttons()))
        if 'filename' in locals() and os.path.exists(filename):
            os.remove(filename)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conn = get_db_connection()
    conn.execute('INSERT OR IGNORE INTO users (user_id, username, date_joined) VALUES (?, ?, ?)', (user.id, user.username, time.strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    settings = conn.execute('SELECT maintenance_mode, ban_list FROM settings WHERE id=1').fetchone()
    conn.close()

    if str(user.id) in settings[1].split(','): return

    lang = get_user_lang(user.id)
    if not lang:
        keyboard = [[InlineKeyboardButton("العربية 🇮🇶", callback_data='set_lang_ar'), InlineKeyboardButton("English 🇺🇸", callback_data='set_lang_en')]] + get_mandatory_buttons()
        await update.message.reply_text("❖ <b>Welcome</b> / <b>أهلاً بك</b>\n\n☟ Please Select Your Language ☟\n☟ اختر لغة البوت ☟", parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if settings[0] == 1 and user.id != ADMIN_ID:
        await update.message.reply_text(TRANS[lang]['maintenance'], reply_markup=InlineKeyboardMarkup(get_mandatory_buttons()))
        return
    await show_main_menu(update, context, lang)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, lang):
    user = update.effective_user
    text = TRANS[lang]['welcome'].format(name=user.first_name)
    buttons = [[InlineKeyboardButton(TRANS[lang]['sites_btn'], callback_data='sites_list')], [InlineKeyboardButton(TRANS[lang]['settings_btn'], callback_data='settings_menu')]]
    if user.id == ADMIN_ID:
        buttons.insert(0, [InlineKeyboardButton("♛ 𝐀𝐝𝐦𝐢𝐧 𝐏𝐚𝐧𝐞𝐥 ♛", callback_data='admin_panel')])
    
    markup = InlineKeyboardMarkup(buttons + get_mandatory_buttons())
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode='HTML', reply_markup=markup)
    else:
        await update.message.reply_text(text, parse_mode='HTML', reply_markup=markup)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    conn = get_db_connection()
    settings = conn.execute('SELECT maintenance_mode, ban_list FROM settings WHERE id=1').fetchone()
    conn.close()

    if str(user_id) in settings[1].split(','): return
    lang = get_user_lang(user_id) or 'en'
    if settings[0] == 1 and user_id != ADMIN_ID:
        await update.message.reply_text(TRANS[lang]['maintenance'], reply_markup=InlineKeyboardMarkup(get_mandatory_buttons()))
        return
    if not text.startswith('http'):
        await update.message.reply_text(TRANS[lang]['send_url'], reply_markup=InlineKeyboardMarkup(get_mandatory_buttons()))
        return

    status_msg = await update.message.reply_text(TRANS[lang]['process'], reply_markup=InlineKeyboardMarkup(get_mandatory_buttons()))
    
    # استخراج الصيغ
    video_formats, best_audio = get_video_formats(text)
    
    if not video_formats and not best_audio:
        await status_msg.edit_text(TRANS[lang]['error_generic'].format(error="No formats found"), reply_markup=InlineKeyboardMarkup(get_mandatory_buttons()))
        return
    
    # بناء الأزرار
    keyboard = []
    # إضافة صيغ الفيديو (أعلى جودة أولاً)
    for idx, fmt in enumerate(video_formats):
        button_text = f"🎬 {fmt['resolution']} - {fmt['size_str']}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"video_{idx}_{fmt['format_id']}")])
    # إضافة صيغة mp3 إن وجدت
    if best_audio:
        button_text = f"🎵 mp3 - {best_audio['size_str']}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"audio_{best_audio['format_id']}")])
    
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel_download")])
    # تخزين data في context.user_data
    context.user_data['formats'] = {
        'url': text,
        'video_formats': video_formats,
        'best_audio': best_audio,
        'status_msg_id': status_msg.message_id,
        'chat_id': update.effective_chat.id,
        'user_id': user_id
    }
    
    await status_msg.edit_text(
        "🎬 **Choose a format to download:**\n(Video formats first, then MP3 audio)",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    lang = get_user_lang(user_id) or 'en'

    # التعامل مع أزرار القائمة الرئيسية
    if data == 'admin_panel':
        await admin_panel_view(update, context)
        await query.answer()
        return

    if data.startswith('set_lang_'):
        new_lang = data.split('_')[2]
        conn = get_db_connection()
        conn.execute('UPDATE users SET language = ? WHERE user_id = ?', (new_lang, user_id))
        conn.commit()
        conn.close()
        await query.answer(TRANS[new_lang]['lang_set'])
        await show_main_menu(update, context, new_lang)
        return

    if data == 'back_home':
        await show_main_menu(update, context, lang)
        await query.answer()
        return

    if data == 'settings_menu':
        kb = [[InlineKeyboardButton("العربية 🇮🇶", callback_data='set_lang_ar'), InlineKeyboardButton("English 🇺🇸", callback_data='set_lang_en')], [InlineKeyboardButton(TRANS[lang]['back'], callback_data='back_home')]] + get_mandatory_buttons()
        await query.edit_message_text(f"⚙️ <b>{TRANS[lang]['settings_btn']}</b>\n\n{TRANS[lang]['select_lang_msg']}", parse_mode='HTML', reply_markup=InlineKeyboardMarkup(kb))
        await query.answer()
        return

    if data == 'sites_list':
        kb = [[InlineKeyboardButton(TRANS[lang]['back'], callback_data='back_home')]] + get_mandatory_buttons()
        await query.edit_message_text(TRANS[lang]['sites_title'], parse_mode='HTML', reply_markup=InlineKeyboardMarkup(kb))
        await query.answer()
        return

    # التعامل مع أزرار التحميل (صيغ الفيديو و mp3)
    if data.startswith('video_') or data.startswith('audio_'):
        # استرجاع البيانات المخزنة
        formats_data = context.user_data.get('formats')
        if not formats_data or formats_data['user_id'] != user_id:
            await query.answer("Session expired. Please send the link again.", show_alert=True)
            await query.message.delete()
            return
        
        url = formats_data['url']
        status_msg_id = formats_data['status_msg_id']
        chat_id = formats_data['chat_id']
        
        # تحديد الصيغة
        if data.startswith('video_'):
            parts = data.split('_')
            idx = int(parts[1])
            format_id = parts[2]
            is_audio = False
            resolution = formats_data['video_formats'][idx]['resolution']
            await query.answer(f"Downloading video: {resolution}")
        else:  # audio_
            format_id = data.split('_')[1]
            is_audio = True
            await query.answer("Downloading MP3 audio")
        
        # حذف الرسالة الحالية (الأزرار) وإرسال رسالة حالة جديدة
        await query.message.delete()
        status_msg = await context.bot.send_message(chat_id=chat_id, text="🔄 Processing...", reply_markup=InlineKeyboardMarkup(get_mandatory_buttons()))
        # تحديث status_msg_id في context
        context.user_data['formats']['status_msg_id'] = status_msg.message_id
        
        # بدء التحميل في خلفية (async)
        asyncio.create_task(download_with_format(url, format_id, is_audio, user_id, status_msg, context))
        return

    if data == "cancel_download":
        await query.answer("Cancelled.")
        await query.message.delete()
        if 'formats' in context.user_data:
            del context.user_data['formats']
        return

    # باقي الأزرار الإدارية
    if user_id != ADMIN_ID:
        await query.answer("⛔ Access Denied", show_alert=True)
        return

    conn = get_db_connection()
    if data == 'lock_bot':
        conn.execute('UPDATE settings SET maintenance_mode=1 WHERE id=1')
        conn.commit()
        await query.answer("🔒 Bot Locked")
        await admin_panel_view(update, context)
    elif data == 'unlock_bot':
        conn.execute('UPDATE settings SET maintenance_mode=0 WHERE id=1')
        conn.commit()
        await query.answer("🔓 Bot Unlocked")
        await admin_panel_view(update, context)
    elif data == 'stats':
        await query.answer("Stats Updated")
        await admin_panel_view(update, context)
    elif data == 'broadcast':
        await query.message.reply_text("➢ Send the message to broadcast (Text/Photo/Video):", reply_markup=InlineKeyboardMarkup(get_mandatory_buttons()))
        context.user_data['awaiting_broadcast'] = True
    elif data == 'ban_user':
        await query.message.reply_text("➢ Send User ID to Ban:", reply_markup=InlineKeyboardMarkup(get_mandatory_buttons()))
        context.user_data['awaiting_ban'] = True
    elif data == 'unban_user':
        await query.message.reply_text("➢ Send User ID to Unban:", reply_markup=InlineKeyboardMarkup(get_mandatory_buttons()))
        context.user_data['awaiting_unban'] = True
    conn.close()
    await query.answer()

async def admin_panel_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != ADMIN_ID:
        await query.answer("⛔ Access Denied", show_alert=True)
        return

    conn = get_db_connection()
    total_users = conn.execute('SELECT count(*) FROM users').fetchone()[0]
    m_mode = conn.execute('SELECT maintenance_mode FROM settings WHERE id=1').fetchone()[0]
    conn.close()

    status = "🟢 Online" if m_mode == 0 else "🔴 Maintenance"
    text = f"♛ <b>ADMIN PANEL</b> ♛\n\n👥 Total Users: <code>{total_users}</code>\n⚙️ Bot Status: {status}\n📡 Ping: <code>{round(time.time() % 1, 3) * 100}ms</code>"
    
    kb = [
        [InlineKeyboardButton("📢 Broadcast", callback_data='broadcast'), InlineKeyboardButton("📊 Stats", callback_data='stats')],
        [InlineKeyboardButton("🔒 Lock Bot", callback_data='lock_bot'), InlineKeyboardButton("🔓 Unlock Bot", callback_data='unlock_bot')],
        [InlineKeyboardButton("🚫 Ban User", callback_data='ban_user'), InlineKeyboardButton("✅ Unban User", callback_data='unban_user')],
        [InlineKeyboardButton("🔙 Back", callback_data='back_home')]
    ] + get_mandatory_buttons()
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(kb))

async def admin_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID: return
    kb = InlineKeyboardMarkup(get_mandatory_buttons())

    if context.user_data.get('awaiting_broadcast'):
        conn = get_db_connection()
        users = conn.execute('SELECT user_id FROM users').fetchall()
        conn.close()
        success, failed = 0, 0
        msg = await update.message.reply_text("➢ Starting Broadcast...", reply_markup=kb)
        for user in users:
            try:
                if update.message.photo: await context.bot.send_photo(user[0], update.message.photo[-1].file_id, caption=update.message.caption, reply_markup=kb)
                elif update.message.video: await context.bot.send_video(user[0], update.message.video.file_id, caption=update.message.caption, reply_markup=kb)
                else: await context.bot.send_message(user[0], update.message.text, reply_markup=kb)
                success += 1
            except: failed += 1
        await msg.edit_text(f"✅ Broadcast Completed\n\n🟢 Success: {success}\n🔴 Failed: {failed}", reply_markup=kb)
        context.user_data['awaiting_broadcast'] = False
        return

    text = update.message.text
    conn = get_db_connection()
    current_bans = conn.execute('SELECT ban_list FROM settings WHERE id=1').fetchone()[0]
    
    if context.user_data.get('awaiting_ban'):
        if text.isdigit():
            new_list = current_bans + f",{text}" if current_bans else text
            conn.execute('UPDATE settings SET ban_list=? WHERE id=1', (new_list,))
            conn.commit()
            await update.message.reply_text(f"🚫 User {text} Banned.", reply_markup=kb)
        context.user_data['awaiting_ban'] = False
    elif context.user_data.get('awaiting_unban'):
        if text.isdigit():
            ban_list = current_bans.split(',')
            if text in ban_list:
                ban_list.remove(text)
                conn.execute('UPDATE settings SET ban_list=? WHERE id=1', (",".join(ban_list),))
                conn.commit()
                await update.message.reply_text(f"✅ User {text} Unbanned.", reply_markup=kb)
            else: await update.message.reply_text("⚠️ User not in ban list.", reply_markup=kb)
        context.user_data['awaiting_unban'] = False
    conn.close()

if __name__ == '__main__':
    if not os.path.exists('downloads'):
        os.makedirs('downloads')
    init_db()
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('admin', admin_panel_view))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND) & filters.User(ADMIN_ID) & (filters.Regex(r'^\d+$') | filters.ALL), admin_input_handler), group=1)
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message), group=0)
    print("Bot is running with format selection...")
    application.run_polling()
