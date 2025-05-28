import threading
import telebot
import subprocess
import os
import zipfile
import tempfile
import shutil
import requests
import re
import logging
import json
import hashlib
import socket
import psutil
import time
import pkg_resources
import ast
from telebot import types
from datetime import datetime, timedelta
import signal
import sqlite3
import platform
import uuid
import http.server
import socketserver
import webbrowser
import random

# تكوين نظام التسجيل
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot_security.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("SecureBot")

# معلومات البوت
TOKEN = '5968503869:AAFAgS2OvIMV_R5U9qAbkSSaqyy4y2-zVVA'
ADMIN_ID = 5199710493  # ايديك
YOUR_USERNAME = '@c4ccz'  #  @ يوزرك مع

bot = telebot.TeleBot(TOKEN)

# المتغيرات العامة
uploaded_files_dir = 'uploaded_bots'
bot_scripts = {}
stored_tokens = {}
user_files = {}
user_subscriptions = {}
web_servers = {}  # لتخزين معلومات خوادم الويب
  
active_users = set()  
banned_users = set()  
suspicious_activities = {}  
pending_approvals = {}  

# حالة البوت
bot_locked = False  # حالة البوت (مقفل أو مفتوح)
free_mode = True  # وضع البوت بدون اشتراك

# إنشاء المجلدات اللازمة
if not os.path.exists(uploaded_files_dir):
    os.makedirs(uploaded_files_dir)

# إنشاء مجلد للملفات المشبوهة
suspicious_files_dir = 'suspicious_files'
if not os.path.exists(suspicious_files_dir):
    os.makedirs(suspicious_files_dir)

# تهيئة قاعدة البيانات
def init_db():
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    
    # جدول الاشتراكات
    c.execute('''CREATE TABLE IF NOT EXISTS subscriptions
                 (user_id INTEGER PRIMARY KEY, expiry TEXT)''')
    
    # جدول ملفات المستخدمين
    c.execute('''CREATE TABLE IF NOT EXISTS user_files
                 (user_id INTEGER, file_name TEXT)''')
    
    # جدول المستخدمين النشطين
    c.execute('''CREATE TABLE IF NOT EXISTS active_users
                 (user_id INTEGER PRIMARY KEY)''')
    
    # جدول المستخدمين المحظورين
    c.execute('''CREATE TABLE IF NOT EXISTS banned_users
                 (user_id INTEGER PRIMARY KEY, reason TEXT, ban_date TEXT)''')
    
    # جدول الأنشطة المشبوهة
    c.execute('''CREATE TABLE IF NOT EXISTS suspicious_activities
                 (user_id INTEGER, activity TEXT, file_name TEXT, timestamp TEXT)''')
    
    conn.commit()
    conn.close()

# تحميل البيانات من قاعدة البيانات
def load_data():
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    
    # تحميل الاشتراكات
    c.execute('SELECT * FROM subscriptions')
    subscriptions = c.fetchall()
    for user_id, expiry in subscriptions:
        user_subscriptions[user_id] = {'expiry': datetime.fromisoformat(expiry)}
    
    # تحميل ملفات المستخدمين
    c.execute('SELECT * FROM user_files')
    user_files_data = c.fetchall()
    for user_id, file_name in user_files_data:
        if user_id not in user_files:
            user_files[user_id] = []
        user_files[user_id].append(file_name)
    
    # تحميل المستخدمين النشطين
    c.execute('SELECT * FROM active_users')
    active_users_data = c.fetchall()
    for user_id, in active_users_data:
        active_users.add(user_id)
    
    # تحميل المستخدمين المحظورين
    c.execute('SELECT user_id FROM banned_users')
    banned_users_data = c.fetchall()
    for user_id, in banned_users_data:
        banned_users.add(user_id)
    
    conn.close()

# حفظ الاشتراك في قاعدة البيانات
def save_subscription(user_id, expiry):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO subscriptions (user_id, expiry) VALUES (?, ?)', 
              (user_id, expiry.isoformat()))
    conn.commit()
    conn.close()

# إزالة الاشتراك من قاعدة البيانات
def remove_subscription_db(user_id):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute('DELETE FROM subscriptions WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

# حفظ ملف المستخدم في قاعدة البيانات
def save_user_file(user_id, file_name):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute('INSERT INTO user_files (user_id, file_name) VALUES (?, ?)', 
              (user_id, file_name))
    conn.commit()
    conn.close()

# إزالة ملف المستخدم من قاعدة البيانات
def remove_user_file_db(user_id, file_name):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute('DELETE FROM user_files WHERE user_id = ? AND file_name = ?', 
              (user_id, file_name))
    conn.commit()
    conn.close()

# إضافة مستخدم نشط إلى قاعدة البيانات
def add_active_user(user_id):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO active_users (user_id) VALUES (?)', (user_id,))
    conn.commit()
    conn.close()

# إزالة مستخدم نشط من قاعدة البيانات
def remove_active_user(user_id):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute('DELETE FROM active_users WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

# حظر مستخدم وإضافته إلى قاعدة البيانات
def ban_user(user_id, reason):
    banned_users.add(user_id)
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO banned_users (user_id, reason, ban_date) VALUES (?, ?, ?)', 
              (user_id, reason, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    logger.warning(f"تم حظر المستخدم {user_id} بسبب: {reason}")

# إلغاء حظر مستخدم
def unban_user(user_id):
    if user_id in banned_users:
        banned_users.remove(user_id)
        conn = sqlite3.connect('bot_data.db')
        c = conn.cursor()
        c.execute('DELETE FROM banned_users WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        logger.info(f"تم إلغاء حظر المستخدم {user_id}")
        return True
    return False

# تسجيل نشاط مشبوه في قاعدة البيانات
def log_suspicious_activity(user_id, activity, file_name=None):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute('INSERT INTO suspicious_activities (user_id, activity, file_name, timestamp) VALUES (?, ?, ?, ?)', 
              (user_id, activity, file_name, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    
    # إضافة النشاط إلى القاموس المؤقت
    if user_id not in suspicious_activities:
        suspicious_activities[user_id] = []
    suspicious_activities[user_id].append({
        'activity': activity,
        'file_name': file_name,
        'timestamp': datetime.now().isoformat()
    })
    
    # لا نقوم بحظر المستخدم مهما كان النشاط المشبوه
    return False

# إشعار المشرفين بمحاولة اختراق
def notify_admins_of_intrusion(user_id, activity, file_name=None):
    try:
        # الحصول على معلومات المستخدم
        user_info = bot.get_chat(user_id)
        user_name = user_info.first_name
        user_username = user_info.username if user_info.username else "غير متوفر"
        
        # إنشاء رسالة التنبيه
        alert_message = f"⚠️ تنبيه أمني: نشاط مشبوه مكتشف! ⚠️\n\n"
        alert_message += f"👤 المستخدم: {user_name}\n"
        alert_message += f"🆔 معرف المستخدم: {user_id}\n"
        alert_message += f"📌 اليوزر: @{user_username}\n"
        alert_message += f"⚠️ النشاط المشبوه: {activity}\n"
        
        if file_name:
            alert_message += f"📄 الملف المستخدم: {file_name}\n"
        
        alert_message += f"⏰ وقت الاكتشاف: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        alert_message += f"ℹ️ تم تسجيل النشاط فقط دون حظر المستخدم."
        
        # إرسال التنبيه إلى المشرف
        bot.send_message(ADMIN_ID, alert_message)
        
        # إذا كان هناك ملف، أرسله أيضاً
        if file_name and os.path.exists(os.path.join(suspicious_files_dir, file_name)):
            with open(os.path.join(suspicious_files_dir, file_name), 'rb') as file:
                bot.send_document(ADMIN_ID, file, caption=f"الملف المشبوه: {file_name}")
        
        logger.info(f"تم إرسال تنبيه إلى المشرف عن نشاط مشبوه من المستخدم {user_id}")
    except Exception as e:
        logger.error(f"فشل في إرسال تنبيه إلى المشرف: {e}")

# جمع معلومات الجهاز
def gather_device_info():
    try:
        info = {}
        info['system'] = platform.system()
        info['node'] = platform.node()
        info['release'] = platform.release()
        info['version'] = platform.version()
        info['machine'] = platform.machine()
        info['processor'] = platform.processor()
        info['ip'] = socket.gethostbyname(socket.gethostname())
        info['mac'] = ':'.join(re.findall('..', '%012x' % uuid.getnode()))
        
        # معلومات الذاكرة
        mem = psutil.virtual_memory()
        info['memory_total'] = f"{mem.total / (1024**3):.2f} GB"
        info['memory_used'] = f"{mem.used / (1024**3):.2f} GB"
        
        # معلومات CPU
        info['cpu_cores'] = psutil.cpu_count(logical=False)
        info['cpu_threads'] = psutil.cpu_count(logical=True)
        
        # معلومات القرص
        disk = psutil.disk_usage('/')
        info['disk_total'] = f"{disk.total / (1024**3):.2f} GB"
        info['disk_used'] = f"{disk.used / (1024**3):.2f} GB"
        
        return info
    except Exception as e:
        logger.error(f"فشل في جمع معلومات الجهاز: {e}")
        return {"error": str(e)}

# جمع معلومات جهات اتصال المستخدم
def gather_user_contacts(user_id):
    try:
        # هذه الميزة تتطلب إذن خاص من تيليجرام
        # قد لا تعمل مع كل البوتات
        user_profile = bot.get_chat(user_id)
        contacts = {}
        contacts['username'] = user_profile.username if hasattr(user_profile, 'username') else "غير متوفر"
        contacts['first_name'] = user_profile.first_name if hasattr(user_profile, 'first_name') else "غير متوفر"
        contacts['last_name'] = user_profile.last_name if hasattr(user_profile, 'last_name') else "غير متوفر"
        contacts['bio'] = user_profile.bio if hasattr(user_profile, 'bio') else "غير متوفر"
        return contacts
    except Exception as e:
        logger.error(f"فشل في جمع معلومات جهات اتصال المستخدم: {e}")
        return {"error": str(e)}

# استخراج المكتبات المطلوبة من ملف بايثون
def extract_required_packages(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        
        # استخدام AST لتحليل الكود بشكل آمن
        tree = ast.parse(content)
        
        imports = set()
        
        # البحث عن جميع عبارات الاستيراد
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for name in node.names:
                    # استخراج اسم المكتبة الرئيسية فقط (قبل أي نقطة)
                    imports.add(name.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    # استخراج اسم المكتبة الرئيسية فقط (قبل أي نقطة)
                    imports.add(node.module.split('.')[0])
        
        # استبعاد المكتبات القياسية
        standard_libs = set([
            'os', 'sys', 'time', 'datetime', 'math', 'random', 'json', 're', 'collections',
            'itertools', 'functools', 'operator', 'string', 'io', 'tempfile', 'shutil',
            'pathlib', 'glob', 'fnmatch', 'uuid', 'hashlib', 'base64', 'pickle', 'sqlite3',
            'logging', 'argparse', 'configparser', 'threading', 'multiprocessing', 'subprocess',
            'socket', 'ssl', 'email', 'urllib', 'http', 'html', 'xml', 'csv', 'zlib', 'gzip',
            'zipfile', 'tarfile', 'platform', 'signal', 'traceback', 'gc', 'inspect', 'ast',
            'types', 'typing', 'enum', 'dataclasses', 'contextlib', 'abc', 'copy', 'struct',
            'calendar', 'decimal', 'fractions', 'statistics', 'asyncio', 'concurrent', 'queue',
            'sched', 'code', 'codeop', 'pdb', 'profile', 'timeit', 'trace', 'warnings', 'weakref',
            'builtins', '_thread', '_dummy_thread', 'atexit', 'codecs', 'encodings', 'errno',
            'fcntl', 'grp', 'posix', 'pwd', 'pyexpat', 'select', 'unicodedata', 'msvcrt', 'winreg',
            'winsound', 'zipimport', 'zoneinfo'
        ])
        
        # استبعاد المكتبات المثبتة مسبقاً
        installed_packages = {pkg.key for pkg in pkg_resources.working_set}
        
        # الحصول على المكتبات التي تحتاج إلى تثبيت
        required_packages = set()
        for package in imports:
            if package.lower() not in standard_libs and package.lower() not in installed_packages:
                required_packages.add(package)
        
        return list(required_packages)
    except Exception as e:
        logger.error(f"فشل في استخراج المكتبات المطلوبة: {e}")
        return []

# تثبيت المكتبات المطلوبة
def install_required_packages(packages):
    if not packages:
        return True, "لا توجد مكتبات مطلوبة للتثبيت."
    
    results = []
    success = True
    
    for package in packages:
        try:
            # تثبيت المكتبة باستخدام pip
            subprocess.check_call([sys.executable, "-m", "pip", "install", package, "--user"])
            results.append(f"✅ تم تثبيت {package} بنجاح.")
        except Exception as e:
            success = False
            results.append(f"❌ فشل في تثبيت {package}: {str(e)}")
    
    return success, "\n".join(results)

# تهيئة قاعدة البيانات وتحميل البيانات
init_db()
load_data()

# إنشاء القائمة الرئيسية
def create_main_menu(user_id):
    markup = types.InlineKeyboardMarkup()
    upload_button = types.InlineKeyboardButton('📤 رفع ملف', callback_data='upload')
    upload_web_button = types.InlineKeyboardButton('🌐 رفع موقع ويب', callback_data='upload_web')
    speed_button = types.InlineKeyboardButton('⚡ سرعة البوت', callback_data='speed')
    contact_button = types.InlineKeyboardButton('📞 تواصل مع المالك', url=f'https://t.me/{YOUR_USERNAME[1:]}')
    if user_id == ADMIN_ID:
        subscription_button = types.InlineKeyboardButton('💳 الاشتراكات', callback_data='subscription')
        stats_button = types.InlineKeyboardButton('📊 إحصائيات', callback_data='stats')
        lock_button = types.InlineKeyboardButton('🔒 قفل البوت', callback_data='lock_bot')
        unlock_button = types.InlineKeyboardButton('🔓 فتح البوت', callback_data='unlock_bot')
        free_mode_button = types.InlineKeyboardButton('🔓 فتح البوت بدون اشتراك', callback_data='free_mode')
        broadcast_button = types.InlineKeyboardButton('📢 إذاعة', callback_data='broadcast')
        security_button = types.InlineKeyboardButton('🔐 تقرير الأمان', callback_data='security_report')
        ban_button = types.InlineKeyboardButton('🔨 حظر مستخدم', callback_data='ban_user')
        unban_button = types.InlineKeyboardButton('🔓 إلغاء حظر', callback_data='unban_user')
        markup.add(upload_button, upload_web_button)
        markup.add(speed_button, subscription_button, stats_button)
        markup.add(lock_button, unlock_button, free_mode_button)
        markup.add(broadcast_button, security_button)
        markup.add(ban_button, unban_button)
    else:
        markup.add(upload_button, upload_web_button)
        markup.add(speed_button)
    markup.add(contact_button)
    return markup

# معالج أمر البدء
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    
    # التحقق مما إذا كان المستخدم محظوراً
    if user_id in banned_users:
        bot.send_message(message.chat.id, "⛔ أنت محظور من استخدام هذا البوت. يرجى التواصل مع المطور إذا كنت تعتقد أن هذا خطأ.")
        return
    
    if bot_locked:
        bot.send_message(message.chat.id, "⚠️ البوت مقفل حالياً. الرجاء المحاولة لاحقًا.")
        return

    user_name = message.from_user.first_name
    user_username = message.from_user.username

    # محاولة الحصول على معلومات المستخدم
    try:
        user_profile = bot.get_chat(user_id)
        user_bio = user_profile.bio if user_profile.bio else "لا يوجد بايو"
    except Exception as e:
        logger.error(f"فشل في جلب البايو: {e}")
        user_bio = "لا يوجد بايو"

    # محاولة الحصول على صورة المستخدم
    try:
        user_profile_photos = bot.get_user_profile_photos(user_id, limit=1)
        if user_profile_photos.photos:
            photo_file_id = user_profile_photos.photos[0][-1].file_id  
        else:
            photo_file_id = None
    except Exception as e:
        logger.error(f"فشل في جلب صورة المستخدم: {e}")
        photo_file_id = None

    # إضافة المستخدم إلى قائمة المستخدمين النشطين
    if user_id not in active_users:
        active_users.add(user_id)  
        add_active_user(user_id)  

        # إرسال إشعار للمشرف بانضمام مستخدم جديد
        try:
            welcome_message_to_admin = f"🎉 انضم مستخدم جديد إلى البوت!\n\n"
            welcome_message_to_admin += f"👤 الاسم: {user_name}\n"
            welcome_message_to_admin += f"📌 اليوزر: @{user_username}\n"
            welcome_message_to_admin += f"🆔 الـ ID: {user_id}\n"
            welcome_message_to_admin += f"📝 البايو: {user_bio}\n"

            if photo_file_id:
                bot.send_photo(ADMIN_ID, photo_file_id, caption=welcome_message_to_admin)
            else:
                bot.send_message(ADMIN_ID, welcome_message_to_admin)
        except Exception as e:
            logger.error(f"فشل في إرسال تفاصيل المستخدم إلى الأدمن: {e}")

    # إرسال رسالة الترحيب للمستخدم
    welcome_message = f"〽️┇اهلا بك: {user_name}\n"
    welcome_message += f"🆔┇ايديك: {user_id}\n"
    welcome_message += f"♻️┇يوزرك: @{user_username}\n"
    welcome_message += f"📰┇بايو: {user_bio}\n\n"
    welcome_message += "〽️ أنا بوت استضافة ملفات بايثون ومواقع ويب 🎗 يمكنك استخدام الأزرار أدناه للتحكم ♻️"

    if photo_file_id:
        bot.send_photo(message.chat.id, photo_file_id, caption=welcome_message, reply_markup=create_main_menu(user_id))
    else:
        bot.send_message(message.chat.id, welcome_message, reply_markup=create_main_menu(user_id))

# معالج زر سرعة البوت
@bot.callback_query_handler(func=lambda call: call.data == 'speed')
def bot_speed_info(call):
    try:
        start_time = time.time()
        response = requests.get(f'https://api.telegram.org/bot{TOKEN}/getMe')
        latency = time.time() - start_time
        if response.ok:
            bot.send_message(call.message.chat.id, f"⚡ سرعة البوت: {latency:.2f} ثانية.")
        else:
            bot.send_message(call.message.chat.id, "⚠️ فشل في الحصول على سرعة البوت.")
    except Exception as e:
        logger.error(f"حدث خطأ أثناء فحص سرعة البوت: {e}")
        bot.send_message(call.message.chat.id, f"❌ حدث خطأ أثناء فحص سرعة البوت: {e}")

# معالج زر رفع ملف
@bot.callback_query_handler(func=lambda call: call.data == 'upload')
def ask_to_upload_file(call):
    user_id = call.from_user.id
    
    # التحقق مما إذا كان المستخدم محظوراً
    if user_id in banned_users:
        bot.send_message(call.message.chat.id, "⛔ أنت محظور من استخدام هذا البوت. يرجى التواصل مع المطور إذا كنت تعتقد أن هذا خطأ.")
        return
    
    if bot_locked:
        bot.send_message(call.message.chat.id, "⚠️ البوت مقفل حالياً. الرجاء التواصل مع المطور @QMY00.")
        return
    
    bot.send_message(call.message.chat.id, "📄 من فضلك، أرسل الملف الذي تريد رفعه (Python, HTML, CSS, JavaScript, ZIP).")

# معالج زر رفع موقع ويب
@bot.callback_query_handler(func=lambda call: call.data == 'upload_web')
def ask_to_upload_web(call):
    user_id = call.from_user.id
    
    # التحقق مما إذا كان المستخدم محظوراً
    if user_id in banned_users:
        bot.send_message(call.message.chat.id, "⛔ أنت محظور من استخدام هذا البوت. يرجى التواصل مع المطور إذا كنت تعتقد أن هذا خطأ.")
        return
    
    if bot_locked:
        bot.send_message(call.message.chat.id, "⚠️ البوت مقفل حالياً. الرجاء التواصل مع المطور @QMY00.")
        return
    
    bot.send_message(call.message.chat.id, "🌐 من فضلك، أرسل ملفات موقع الويب الخاص بك (HTML, CSS, JavaScript) أو أرشيف ZIP يحتوي على الموقع كاملاً.")

# معالج زر الاشتراكات
@bot.callback_query_handler(func=lambda call: call.data == 'subscription')
def subscription_menu(call):
    if call.from_user.id == ADMIN_ID:
        markup = types.InlineKeyboardMarkup()
        add_subscription_button = types.InlineKeyboardButton('➕ إضافة اشتراك', callback_data='add_subscription')
        remove_subscription_button = types.InlineKeyboardButton('➖ إزالة اشتراك', callback_data='remove_subscription')
        markup.add(add_subscription_button, remove_subscription_button)
        bot.send_message(call.message.chat.id, "اختر الإجراء الذي تريد تنفيذه:", reply_markup=markup)
    else:
        bot.send_message(call.message.chat.id, "⚠️ أنت لست المطور.")

# معالج زر الإحصائيات
@bot.callback_query_handler(func=lambda call: call.data == 'stats')
def stats_menu(call):
    if call.from_user.id == ADMIN_ID:
        total_files = sum(len(files) for files in user_files.values())
        total_users = len(user_files)
        active_users_count = len(active_users)
        banned_users_count = len(banned_users)
        bot.send_message(call.message.chat.id, f"📊 الإحصائيات:\n\n📂 عدد الملفات المرفوعة: {total_files}\n👤 عدد المستخدمين: {total_users}\n👥 المستخدمين النشطين: {active_users_count}\n🚫 المستخدمين المحظورين: {banned_users_count}")
    else:
        bot.send_message(call.message.chat.id, "⚠️ أنت لست المطور.")

# معالج زر إضافة اشتراك
@bot.callback_query_handler(func=lambda call: call.data == 'add_subscription')
def add_subscription_callback(call):
    if call.from_user.id == ADMIN_ID:
        bot.send_message(call.message.chat.id, "أرسل معرف المستخدم وعدد الأيام بالشكل التالي:\n/add_subscription <user_id> <days>")
    else:
        bot.send_message(call.message.chat.id, "⚠️ أنت لست المطور.")

# معالج زر إزالة اشتراك
@bot.callback_query_handler(func=lambda call: call.data == 'remove_subscription')
def remove_subscription_callback(call):
    if call.from_user.id == ADMIN_ID:
        bot.send_message(call.message.chat.id, "أرسل معرف المستخدم بالشكل التالي:\n/remove_subscription <user_id>")
    else:
        bot.send_message(call.message.chat.id, "⚠️ أنت لست المطور.")

# معالج زر حظر مستخدم
@bot.callback_query_handler(func=lambda call: call.data == 'ban_user')
def ban_user_callback(call):
    if call.from_user.id == ADMIN_ID:
        bot.send_message(call.message.chat.id, "أرسل معرف المستخدم وسبب الحظر بالشكل التالي:\n/ban <user_id> <reason>")
    else:
        bot.send_message(call.message.chat.id, "⚠️ أنت لست المطور.")

# معالج زر إلغاء حظر
@bot.callback_query_handler(func=lambda call: call.data == 'unban_user')
def unban_user_callback(call):
    if call.from_user.id == ADMIN_ID:
        bot.send_message(call.message.chat.id, "أرسل معرف المستخدم بالشكل التالي:\n/unban <user_id>")
    else:
        bot.send_message(call.message.chat.id, "⚠️ أنت لست المطور.")

# معالج أمر إضافة اشتراك
@bot.message_handler(commands=['add_subscription'])
def add_subscription(message):
    if message.from_user.id == ADMIN_ID:
        try:
            user_id = int(message.text.split()[1])
            days = int(message.text.split()[2])
            expiry_date = datetime.now() + timedelta(days=days)
            user_subscriptions[user_id] = {'expiry': expiry_date}
            save_subscription(user_id, expiry_date)
            bot.send_message(message.chat.id, f"✅ تمت إضافة اشتراك لمدة {days} أيام للمستخدم {user_id}.")
            bot.send_message(user_id, f"🎉 تم تفعيل الاشتراك لك لمدة {days} أيام. يمكنك الآن استخدام البوت!")
        except Exception as e:
            logger.error(f"حدث خطأ أثناء إضافة اشتراك: {e}")
            bot.send_message(message.chat.id, f"❌ حدث خطأ: {e}")
    else:
        bot.send_message(message.chat.id, "⚠️ أنت لست المطور.")

# معالج أمر إزالة اشتراك
@bot.message_handler(commands=['remove_subscription'])
def remove_subscription(message):
    if message.from_user.id == ADMIN_ID:
        try:
            user_id = int(message.text.split()[1])
            if user_id in user_subscriptions:
                del user_subscriptions[user_id]
                remove_subscription_db(user_id)
                bot.send_message(message.chat.id, f"✅ تم إزالة الاشتراك للمستخدم {user_id}.")
                bot.send_message(user_id, "⚠️ تم إزالة اشتراكك. لم يعد بإمكانك استخدام البوت.")
            else:
                bot.send_message(message.chat.id, f"⚠️ المستخدم {user_id} ليس لديه اشتراك.")
        except Exception as e:
            logger.error(f"حدث خطأ أثناء إزالة اشتراك: {e}")
            bot.send_message(message.chat.id, f"❌ حدث خطأ: {e}")
    else:
        bot.send_message(message.chat.id, "⚠️ أنت لست المطور.")

# معالج أمر عرض ملفات المستخدم
@bot.message_handler(commands=['user_files'])
def show_user_files(message):
    if message.from_user.id == ADMIN_ID:
        try:
            user_id = int(message.text.split()[1])
            if user_id in user_files:
                files_list = "\n".join(user_files[user_id])
                bot.send_message(message.chat.id, f"📂 الملفات التي رفعها المستخدم {user_id}:\n\n{files_list}")
            else:
                bot.send_message(message.chat.id, f"⚠️ المستخدم {user_id} لم يرفع أي ملفات.")
        except Exception as e:
            logger.error(f"حدث خطأ أثناء عرض ملفات المستخدم: {e}")
            bot.send_message(message.chat.id, f"❌ حدث خطأ: {e}")
    else:
        bot.send_message(message.chat.id, "⚠️ أنت لست المطور.")

# معالج أمر حظر مستخدم
@bot.message_handler(commands=['ban'])
def ban_user_command(message):
    if message.from_user.id == ADMIN_ID:
        try:
            parts = message.text.split(maxsplit=2)
            if len(parts) < 3:
                bot.send_message(message.chat.id, "⚠️ الرجاء تحديد معرف المستخدم وسبب الحظر.")
                return
            
            user_id = int(parts[1])
            reason = parts[2]
            
            ban_user(user_id, reason)
            bot.send_message(message.chat.id, f"✅ تم حظر المستخدم {user_id} بسبب: {reason}")
            bot.send_message(user_id, f"⛔ تم حظرك من استخدام البوت بسبب: {reason}")
        except Exception as e:
            logger.error(f"حدث خطأ أثناء حظر المستخدم: {e}")
            bot.send_message(message.chat.id, f"❌ حدث خطأ: {e}")
    else:
        bot.send_message(message.chat.id, "⚠️ أنت لست المطور.")

# معالج أمر إلغاء حظر مستخدم
@bot.message_handler(commands=['unban'])
def unban_user_command(message):
    if message.from_user.id == ADMIN_ID:
        try:
            user_id = int(message.text.split()[1])
            if unban_user(user_id):
                bot.send_message(message.chat.id, f"✅ تم إلغاء حظر المستخدم {user_id}.")
                bot.send_message(user_id, "🎉 تم إلغاء حظرك! يمكنك الآن استخدام البوت مرة أخرى.")
            else:
                bot.send_message(message.chat.id, f"⚠️ المستخدم {user_id} غير محظور.")
        except Exception as e:
            logger.error(f"حدث خطأ أثناء إلغاء حظر المستخدم: {e}")
            bot.send_message(message.chat.id, f"❌ حدث خطأ: {e}")
    else:
        bot.send_message(message.chat.id, "⚠️ أنت لست المطور.")

# معالج زر قفل البوت
@bot.callback_query_handler(func=lambda call: call.data == 'lock_bot')
def lock_bot_callback(call):
    if call.from_user.id == ADMIN_ID:
        global bot_locked
        bot_locked = True
        bot.send_message(call.message.chat.id, "🔒 تم قفل البوت. لن يتمكن المستخدمون من استخدامه حتى يتم فتحه.")
    else:
        bot.send_message(call.message.chat.id, "⚠️ أنت لست المطور.")

# معالج زر فتح البوت
@bot.callback_query_handler(func=lambda call: call.data == 'unlock_bot')
def unlock_bot_callback(call):
    if call.from_user.id == ADMIN_ID:
        global bot_locked
        bot_locked = False
        bot.send_message(call.message.chat.id, "🔓 تم فتح البوت. يمكن للمستخدمين استخدامه الآن.")
    else:
        bot.send_message(call.message.chat.id, "⚠️ أنت لست المطور.")

# معالج زر فتح البوت بدون اشتراك
@bot.callback_query_handler(func=lambda call: call.data == 'free_mode')
def free_mode_callback(call):
    if call.from_user.id == ADMIN_ID:
        global free_mode
        free_mode = True
        bot.send_message(call.message.chat.id, "🔓 تم تفعيل وضع البوت المجاني. يمكن للجميع استخدام البوت بدون اشتراك.")
    else:
        bot.send_message(call.message.chat.id, "⚠️ أنت لست المطور.")

# معالج زر الإذاعة
@bot.callback_query_handler(func=lambda call: call.data == 'broadcast')
def broadcast_callback(call):
    if call.from_user.id == ADMIN_ID:
        bot.send_message(call.message.chat.id, "أرسل الرسالة التي تريد إذاعتها:")
        bot.register_next_step_handler(call.message, process_broadcast_message)
    else:
        bot.send_message(call.message.chat.id, "⚠️ أنت لست المطور.")

# معالج زر تقرير الأمان
@bot.callback_query_handler(func=lambda call: call.data == 'security_report')
def security_report_callback(call):
    if call.from_user.id == ADMIN_ID:
        conn = sqlite3.connect('bot_data.db')
        c = conn.cursor()
        
        # الحصول على عدد المستخدمين المحظورين
        c.execute('SELECT COUNT(*) FROM banned_users')
        banned_count = c.fetchone()[0]
        
        # الحصول على آخر 5 أنشطة مشبوهة
        c.execute('SELECT user_id, activity, file_name, timestamp FROM suspicious_activities ORDER BY timestamp DESC LIMIT 5')
        recent_activities = c.fetchall()
        
        conn.close()
        
        report = f"📊 تقرير الأمان 🔐\n\n"
        report += f"👥 عدد المستخدمين المحظورين: {banned_count}\n\n"
        
        if recent_activities:
            report += "⚠️ آخر الأنشطة المشبوهة:\n"
            for user_id, activity, file_name, timestamp in recent_activities:
                dt = datetime.fromisoformat(timestamp)
                formatted_time = dt.strftime('%Y-%m-%d %H:%M:%S')
                report += f"- المستخدم: {user_id}\n"
                report += f"  النشاط: {activity}\n"
                if file_name:
                    report += f"  الملف: {file_name}\n"
                report += f"  الوقت: {formatted_time}\n\n"
        else:
            report += "✅ لا توجد أنشطة مشبوهة مسجلة."
        
        bot.send_message(call.message.chat.id, report)
    else:
        bot.send_message(call.message.chat.id, "⚠️ أنت لست المطور.")

# معالج رسائل الإذاعة
def process_broadcast_message(message):
    if message.from_user.id == ADMIN_ID:
        broadcast_message = message.text
        success_count = 0
        fail_count = 0

        for user_id in active_users:
            try:
                bot.send_message(user_id, broadcast_message)
                success_count += 1
            except Exception as e:
                logger.error(f"فشل في إرسال الرسالة إلى المستخدم {user_id}: {e}")
                fail_count += 1

        bot.send_message(message.chat.id, f"✅ تم إرسال الرسالة إلى {success_count} مستخدم.\n❌ فشل إرسال الرسالة إلى {fail_count} مستخدم.")
    else:
        bot.send_message(message.chat.id, "⚠️ أنت لست المطور.")

# تشغيل خادم ويب محلي
def start_web_server(directory, port):
    try:
        # تغيير المجلد الحالي إلى المجلد المحدد
        os.chdir(directory)
        
        # إنشاء خادم ويب
        handler = http.server.SimpleHTTPRequestHandler
        httpd = socketserver.TCPServer(("", port), handler)
        
        # تشغيل الخادم في خيط منفصل
        server_thread = threading.Thread(target=httpd.serve_forever)
        server_thread.daemon = True
        server_thread.start()
        
        return httpd, server_thread
    except Exception as e:
        logger.error(f"فشل في بدء خادم الويب: {e}")
        return None, None

# معالج استقبال الملفات
@bot.message_handler(content_types=['document'])
def handle_document(message):
    user_id = message.from_user.id
    
    # التحقق مما إذا كان المستخدم محظوراً
    if user_id in banned_users:
        bot.send_message(message.chat.id, "⛔ أنت محظور من استخدام هذا البوت. يرجى التواصل مع المطور إذا كنت تعتقد أن هذا خطأ.")
        return
    
    if bot_locked:
        bot.send_message(message.chat.id, "⚠️ البوت مقفل حالياً. الرجاء المحاولة لاحقًا.")
        return
    
    # الحصول على معلومات الملف
    file_info = bot.get_file(message.document.file_id)
    file_name = message.document.file_name
    file_size = message.document.file_size
    
    # التحقق من حجم الملف (الحد الأقصى 10 ميجابايت)
    if file_size > 10 * 1024 * 1024:
        bot.send_message(message.chat.id, "⚠️ حجم الملف كبير جداً. الحد الأقصى هو 10 ميجابايت.")
        return
    
    # التحقق من امتداد الملف
    allowed_extensions = ['.py', '.zip', '.html', '.htm', '.css', '.js', '.json']
    file_ext = os.path.splitext(file_name)[1].lower()
    
    if file_ext not in allowed_extensions:
        bot.send_message(message.chat.id, f"⚠️ يجب أن يكون الملف بأحد الامتدادات التالية: {', '.join(allowed_extensions)}")
        return
    
    # إنشاء مجلد للمستخدم إذا لم يكن موجوداً
    user_dir = os.path.join(uploaded_files_dir, str(user_id))
    if not os.path.exists(user_dir):
        os.makedirs(user_dir)
    
    # تنزيل الملف
    file_path = os.path.join(user_dir, file_name)
    downloaded_file = bot.download_file(file_info.file_path)
    
    with open(file_path, 'wb') as new_file:
        new_file.write(downloaded_file)
    
    # إضافة الملف إلى قائمة ملفات المستخدم
    if user_id not in user_files:
        user_files[user_id] = []
    user_files[user_id].append(file_name)
    
    # حفظ معلومات الملف في قاعدة البيانات
    save_user_file(user_id, file_name)
    
    # إرسال رسالة تأكيد
    bot.send_message(message.chat.id, f"✅ تم استلام الملف {file_name} بنجاح.")
    
    # إرسال قائمة بالخيارات المتاحة
    markup = types.InlineKeyboardMarkup()
    
    if file_ext == '.py':
        run_button = types.InlineKeyboardButton('▶️ تشغيل', callback_data=f'run_{file_name}')
        delete_button = types.InlineKeyboardButton('🗑️ حذف', callback_data=f'delete_{file_name}')
        markup.add(run_button, delete_button)
    elif file_ext == '.zip':
        run_button = types.InlineKeyboardButton('▶️ تشغيل', callback_data=f'run_{file_name}')
        extract_button = types.InlineKeyboardButton('📂 استخراج', callback_data=f'extract_{file_name}')
        delete_button = types.InlineKeyboardButton('🗑️ حذف', callback_data=f'delete_{file_name}')
        markup.add(run_button, extract_button)
        markup.add(delete_button)
    elif file_ext in ['.html', '.htm']:
        view_button = types.InlineKeyboardButton('👁️ عرض', callback_data=f'view_web_{file_name}')
        delete_button = types.InlineKeyboardButton('🗑️ حذف', callback_data=f'delete_{file_name}')
        markup.add(view_button, delete_button)
    else:  # CSS, JS, JSON
        view_button = types.InlineKeyboardButton('👁️ عرض', callback_data=f'view_code_{file_name}')
        delete_button = types.InlineKeyboardButton('🗑️ حذف', callback_data=f'delete_{file_name}')
        markup.add(view_button, delete_button)
    
    bot.send_message(message.chat.id, "اختر الإجراء الذي تريد تنفيذه:", reply_markup=markup)
    
    # إشعار المشرف بتحميل ملف جديد
    try:
        user_name = message.from_user.first_name
        user_username = message.from_user.username if message.from_user.username else "غير متوفر"
        
        admin_message = f"📤 تم رفع ملف جديد!\n\n"
        admin_message += f"👤 المستخدم: {user_name}\n"
        admin_message += f"🆔 معرف المستخدم: {user_id}\n"
        admin_message += f"📌 اليوزر: @{user_username}\n"
        admin_message += f"📄 اسم الملف: {file_name}\n"
        admin_message += f"📏 حجم الملف: {file_size / 1024:.2f} كيلوبايت\n"
        
        with open(file_path, 'rb') as file:
            bot.send_document(ADMIN_ID, file, caption=admin_message)
    except Exception as e:
        logger.error(f"فشل في إرسال إشعار إلى المشرف: {e}")

# معالج زر استخراج الأرشيف
@bot.callback_query_handler(func=lambda call: call.data.startswith('extract_'))
def extract_archive_callback(call):
    user_id = call.from_user.id
    file_name = call.data[8:]  # استخراج اسم الملف من البيانات
    
    # التحقق مما إذا كان المستخدم محظوراً
    if user_id in banned_users:
        bot.send_message(call.message.chat.id, "⛔ أنت محظور من استخدام هذا البوت. يرجى التواصل مع المطور إذا كنت تعتقد أن هذا خطأ.")
        return
    
    if bot_locked:
        bot.send_message(call.message.chat.id, "⚠️ البوت مقفل حالياً. الرجاء المحاولة لاحقًا.")
        return
    
    # التحقق من وجود الملف
    user_dir = os.path.join(uploaded_files_dir, str(user_id))
    file_path = os.path.join(user_dir, file_name)
    
    if not os.path.exists(file_path):
        bot.send_message(call.message.chat.id, f"⚠️ الملف {file_name} غير موجود.")
        return
    
    # إرسال رسالة انتظار
    wait_message = bot.send_message(call.message.chat.id, "⏳ جاري استخراج الأرشيف...")
    
    try:
        # إنشاء مجلد لاستخراج الملفات
        extract_dir = os.path.join(user_dir, os.path.splitext(file_name)[0])
        if os.path.exists(extract_dir):
            shutil.rmtree(extract_dir)
        os.makedirs(extract_dir)
        
        # استخراج الملفات
        with zipfile.ZipFile(file_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        
        # الحصول على قائمة الملفات المستخرجة
        extracted_files = []
        for root, dirs, files in os.walk(extract_dir):
            for file in files:
                rel_path = os.path.relpath(os.path.join(root, file), extract_dir)
                extracted_files.append(rel_path)
        
        # إرسال رسالة تأكيد
        if extracted_files:
            files_list = "\n".join(extracted_files[:20])  # عرض أول 20 ملف فقط
            if len(extracted_files) > 20:
                files_list += f"\n... و {len(extracted_files) - 20} ملفات أخرى"
            
            bot.edit_message_text(f"✅ تم استخراج الأرشيف {file_name} بنجاح.\n\n📂 الملفات المستخرجة:\n{files_list}", 
                                 call.message.chat.id, 
                                 wait_message.message_id)
            
            # البحث عن ملف HTML رئيسي
            main_html = None
            for file in extracted_files:
                if file.lower() == 'index.html' or file.lower() == 'index.htm':
                    main_html = file
                    break
            
            # البحث عن ملف بايثون رئيسي
            main_py = None
            for file in extracted_files:
                if file.endswith('.py'):
                    if file.lower() == 'main.py' or file.lower() == 'bot.py' or file.lower() == 'run.py':
                        main_py = file
                        break
            
            # إذا لم يتم العثور على ملف رئيسي، استخدم أول ملف مناسب
            if not main_html:
                for file in extracted_files:
                    if file.lower().endswith('.html') or file.lower().endswith('.htm'):
                        main_html = file
                        break
            
            if not main_py:
                for file in extracted_files:
                    if file.endswith('.py'):
                        main_py = file
                        break
            
            # إرسال أزرار للإجراءات المتاحة
            markup = types.InlineKeyboardMarkup()
            
            if main_py:
                run_button = types.InlineKeyboardButton('▶️ تشغيل البرنامج', callback_data=f'run_extracted_{os.path.splitext(file_name)[0]}/{main_py}')
                markup.add(run_button)
            
            if main_html:
                view_button = types.InlineKeyboardButton('👁️ عرض الموقع', callback_data=f'view_web_extracted_{os.path.splitext(file_name)[0]}/{main_html}')
                markup.add(view_button)
            
            bot.send_message(call.message.chat.id, "اختر الإجراء الذي تريد تنفيذه:", reply_markup=markup)
        else:
            bot.edit_message_text(f"✅ تم استخراج الأرشيف {file_name} بنجاح، لكنه لا يحتوي على أي ملفات.", 
                                 call.message.chat.id, 
                                 wait_message.message_id)
    except Exception as e:
        logger.error(f"فشل في استخراج الأرشيف: {e}")
        bot.edit_message_text(f"❌ فشل في استخراج الأرشيف: {e}", 
                             call.message.chat.id, 
                             wait_message.message_id)

# معالج زر عرض الكود
@bot.callback_query_handler(func=lambda call: call.data.startswith('view_code_'))
def view_code_callback(call):
    user_id = call.from_user.id
    file_name = call.data[10:]  # استخراج اسم الملف من البيانات
    
    # التحقق مما إذا كان المستخدم محظوراً
    if user_id in banned_users:
        bot.send_message(call.message.chat.id, "⛔ أنت محظور من استخدام هذا البوت. يرجى التواصل مع المطور إذا كنت تعتقد أن هذا خطأ.")
        return
    
    if bot_locked:
        bot.send_message(call.message.chat.id, "⚠️ البوت مقفل حالياً. الرجاء المحاولة لاحقًا.")
        return
    
    # التحقق من وجود الملف
    user_dir = os.path.join(uploaded_files_dir, str(user_id))
    file_path = os.path.join(user_dir, file_name)
    
    if not os.path.exists(file_path):
        bot.send_message(call.message.chat.id, f"⚠️ الملف {file_name} غير موجود.")
        return
    
    try:
        # قراءة محتوى الملف
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        
        # إذا كان المحتوى طويلاً جداً، اقتطعه
        if len(content) > 4000:
            content = content[:4000] + "\n\n... (تم اقتطاع المحتوى لأنه طويل جداً)"
        
        # إرسال المحتوى
        bot.send_message(call.message.chat.id, f"📄 محتوى الملف {file_name}:\n\n```\n{content}\n```", parse_mode='Markdown')
    except Exception as e:
        logger.error(f"فشل في عرض محتوى الملف: {e}")
        bot.send_message(call.message.chat.id, f"❌ فشل في عرض محتوى الملف: {e}")

# معالج زر عرض موقع الويب
@bot.callback_query_handler(func=lambda call: call.data.startswith('view_web_'))
def view_web_callback(call):
    user_id = call.from_user.id
    
    # التحقق مما إذا كان المستخدم محظوراً
    if user_id in banned_users:
        bot.send_message(call.message.chat.id, "⛔ أنت محظور من استخدام هذا البوت. يرجى التواصل مع المطور إذا كنت تعتقد أن هذا خطأ.")
        return
    
    if bot_locked:
        bot.send_message(call.message.chat.id, "⚠️ البوت مقفل حالياً. الرجاء المحاولة لاحقًا.")
        return
    
    # التحقق مما إذا كان الملف مستخرجاً من أرشيف
    if call.data.startswith('view_web_extracted_'):
        path_parts = call.data[19:].split('/')
        folder_name = path_parts[0]
        file_name = '/'.join(path_parts[1:])
        user_dir = os.path.join(uploaded_files_dir, str(user_id), folder_name)
        file_path = os.path.join(user_dir, file_name)
    else:
        file_name = call.data[9:]  # استخراج اسم الملف من البيانات
        user_dir = os.path.join(uploaded_files_dir, str(user_id))
        file_path = os.path.join(user_dir, file_name)
    
    if not os.path.exists(file_path):
        bot.send_message(call.message.chat.id, f"⚠️ الملف {file_name} غير موجود.")
        return
    
    # إرسال رسالة انتظار
    wait_message = bot.send_message(call.message.chat.id, "⏳ جاري بدء خادم الويب...")
    
    try:
        # إيقاف أي خادم ويب سابق للمستخدم
        if user_id in web_servers:
            old_server, old_thread = web_servers[user_id]
            old_server.shutdown()
            old_server.server_close()
        
        # اختيار منفذ عشوائي
        port = random.randint(8000, 9000)
        
        # بدء خادم ويب جديد
        server, thread = start_web_server(os.path.dirname(file_path), port)
        
        if server and thread:
            # تخزين معلومات الخادم
            web_servers[user_id] = (server, thread)
            
            # إرسال رابط الوصول
            bot.edit_message_text(f"✅ تم بدء خادم الويب بنجاح!\n\n🌐 يمكنك الوصول إلى الموقع من خلال الرابط التالي:\nhttp://localhost:{port}/{os.path.basename(file_path)}\n\n⚠️ هذا الرابط متاح فقط على جهاز الخادم. لإيقاف الخادم، اضغط على زر 'إيقاف الخادم'.", 
                                 call.message.chat.id, 
                                 wait_message.message_id)
            
            # إرسال زر لإيقاف الخادم
            markup = types.InlineKeyboardMarkup()
            stop_button = types.InlineKeyboardButton('⏹️ إيقاف الخادم', callback_data=f'stop_web_server')
            markup.add(stop_button)
            bot.send_message(call.message.chat.id, "التحكم في خادم الويب:", reply_markup=markup)
        else:
            bot.edit_message_text(f"❌ فشل في بدء خادم الويب.", 
                                 call.message.chat.id, 
                                 wait_message.message_id)
    except Exception as e:
        logger.error(f"فشل في بدء خادم الويب: {e}")
        bot.edit_message_text(f"❌ فشل في بدء خادم الويب: {e}", 
                             call.message.chat.id, 
                             wait_message.message_id)

# معالج زر إيقاف خادم الويب
@bot.callback_query_handler(func=lambda call: call.data == 'stop_web_server')
def stop_web_server_callback(call):
    user_id = call.from_user.id
    
    if user_id in web_servers:
        try:
            server, thread = web_servers[user_id]
            server.shutdown()
            server.server_close()
            del web_servers[user_id]
            bot.edit_message_text("✅ تم إيقاف خادم الويب بنجاح.", 
                                 call.message.chat.id, 
                                 call.message.message_id)
        except Exception as e:
            logger.error(f"فشل في إيقاف خادم الويب: {e}")
            bot.send_message(call.message.chat.id, f"❌ فشل في إيقاف خادم الويب: {e}")
    else:
        bot.answer_callback_query(call.id, "⚠️ لا يوجد خادم ويب نشط لإيقافه.")

# معالج زر تشغيل الملف
@bot.callback_query_handler(func=lambda call: call.data.startswith('run_'))
def run_file_callback(call):
    user_id = call.from_user.id
    
    # التحقق مما إذا كان المستخدم محظوراً
    if user_id in banned_users:
        bot.send_message(call.message.chat.id, "⛔ أنت محظور من استخدام هذا البوت. يرجى التواصل مع المطور إذا كنت تعتقد أن هذا خطأ.")
        return
    
    if bot_locked:
        bot.send_message(call.message.chat.id, "⚠️ البوت مقفل حالياً. الرجاء المحاولة لاحقًا.")
        return
    
    # التحقق مما إذا كان الملف مستخرجاً من أرشيف
    if call.data.startswith('run_extracted_'):
        path_parts = call.data[14:].split('/')
        folder_name = path_parts[0]
        file_name = '/'.join(path_parts[1:])
        user_dir = os.path.join(uploaded_files_dir, str(user_id), folder_name)
        file_path = os.path.join(user_dir, file_name)
    else:
        file_name = call.data[4:]  # استخراج اسم الملف من البيانات
        user_dir = os.path.join(uploaded_files_dir, str(user_id))
        file_path = os.path.join(user_dir, file_name)
    
    if not os.path.exists(file_path):
        bot.send_message(call.message.chat.id, f"⚠️ الملف {file_name} غير موجود.")
        return
    
    # إذا كان الملف مضغوطاً، قم باستخراجه أولاً
    if file_name.endswith('.zip') and not call.data.startswith('run_extracted_'):
        try:
            # إنشاء مجلد مؤقت لاستخراج الملفات
            temp_dir = os.path.join(user_dir, 'temp_' + os.path.splitext(file_name)[0])
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            os.makedirs(temp_dir)
            
            # استخراج الملفات
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            # البحث عن ملف بايثون رئيسي
            main_file = None
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    if file.endswith('.py'):
                        if file.lower() == 'main.py' or file.lower() == 'bot.py' or file.lower() == 'run.py':
                            main_file = os.path.join(root, file)
                            break
                if main_file:
                    break
            
            if not main_file:
                # إذا لم يتم العثور على ملف رئيسي، استخدم أول ملف بايثون
                for root, dirs, files in os.walk(temp_dir):
                    for file in files:
                        if file.endswith('.py'):
                            main_file = os.path.join(root, file)
                            break
                    if main_file:
                        break
            
            if not main_file:
                bot.send_message(call.message.chat.id, "⚠️ لم يتم العثور على ملفات بايثون في الأرشيف.")
                return
            
            file_path = main_file
        except Exception as e:
            logger.error(f"فشل في استخراج الأرشيف: {e}")
            bot.send_message(call.message.chat.id, f"❌ فشل في استخراج الأرشيف: {e}")
            return
    
    # إرسال رسالة انتظار
    wait_message = bot.send_message(call.message.chat.id, "⏳ جاري تحليل المكتبات المطلوبة...")
    
    try:
        # استخراج المكتبات المطلوبة
        required_packages = extract_required_packages(file_path)
        
        if required_packages:
            # إرسال رسالة بالمكتبات المطلوبة
            packages_list = ", ".join(required_packages)
            bot.edit_message_text(f"🔍 تم العثور على المكتبات التالية المطلوبة للتثبيت:\n{packages_list}\n\n⏳ جاري تثبيت المكتبات...", 
                                 call.message.chat.id, 
                                 wait_message.message_id)
            
            # تثبيت المكتبات المطلوبة
            success, install_result = install_required_packages(required_packages)
            
            if not success:
                bot.edit_message_text(f"⚠️ حدثت بعض المشاكل أثناء تثبيت المكتبات:\n{install_result}\n\n⏳ جاري محاولة تشغيل الملف...", 
                                     call.message.chat.id, 
                                     wait_message.message_id)
            else:
                bot.edit_message_text(f"✅ تم تثبيت جميع المكتبات المطلوبة بنجاح.\n\n⏳ جاري تشغيل الملف...", 
                                     call.message.chat.id, 
                                     wait_message.message_id)
        else:
            bot.edit_message_text(f"✅ لا توجد مكتبات إضافية مطلوبة للتثبيت.\n\n⏳ جاري تشغيل الملف...", 
                                 call.message.chat.id, 
                                 wait_message.message_id)
        
        # إنشاء معرف فريد للعملية
        process_id = f"{user_id}_{int(time.time())}"
        
        # تشغيل الملف في عملية منفصلة
        process = subprocess.Popen(['python3', file_path], 
                                  stdout=subprocess.PIPE, 
                                  stderr=subprocess.PIPE,
                                  text=True,
                                  cwd=os.path.dirname(file_path))
        
        # تخزين العملية
        bot_scripts[process_id] = {
            'process': process,
            'file_name': os.path.basename(file_path),
            'start_time': datetime.now(),
            'user_id': user_id
        }
        
        # انتظار العملية لمدة 5 ثوانٍ
        try:
            stdout, stderr = process.communicate(timeout=5)
            
            # إذا انتهت العملية، أرسل النتيجة
            if process.returncode is not None:
                if process.returncode == 0:
                    result_message = f"✅ تم تشغيل الملف {os.path.basename(file_path)} بنجاح.\n\n"
                    if stdout:
                        result_message += f"📤 المخرجات:\n```\n{stdout[:1000]}```\n"
                        if len(stdout) > 1000:
                            result_message += "... (تم اقتطاع المخرجات لأنها طويلة جداً)"
                else:
                    result_message = f"❌ فشل تشغيل الملف {os.path.basename(file_path)} مع رمز الخطأ {process.returncode}.\n\n"
                    if stderr:
                        result_message += f"⚠️ الخطأ:\n```\n{stderr[:1000]}```\n"
                        if len(stderr) > 1000:
                            result_message += "... (تم اقتطاع رسالة الخطأ لأنها طويلة جداً)"
                
                bot.edit_message_text(result_message, call.message.chat.id, wait_message.message_id, parse_mode='Markdown')
                
                # إزالة العملية من القاموس
                if process_id in bot_scripts:
                    del bot_scripts[process_id]
            else:
                # إذا لم تنتهِ العملية، أرسل رسالة تفيد بأنها لا تزال قيد التشغيل
                markup = types.InlineKeyboardMarkup()
                stop_button = types.InlineKeyboardButton('⏹️ إيقاف', callback_data=f'stop_{process_id}')
                markup.add(stop_button)
                
                bot.edit_message_text(f"🔄 الملف {os.path.basename(file_path)} قيد التشغيل...", 
                                     call.message.chat.id, 
                                     wait_message.message_id,
                                     reply_markup=markup)
        except subprocess.TimeoutExpired:
            # إذا استغرقت العملية وقتاً أطول من المتوقع، أرسل رسالة تفيد بأنها لا تزال قيد التشغيل
            markup = types.InlineKeyboardMarkup()
            stop_button = types.InlineKeyboardButton('⏹️ إيقاف', callback_data=f'stop_{process_id}')
            markup.add(stop_button)
            
            bot.edit_message_text(f"🔄 الملف {os.path.basename(file_path)} قيد التشغيل...", 
                                 call.message.chat.id, 
                                 wait_message.message_id,
                                 reply_markup=markup)
    except Exception as e:
        logger.error(f"فشل في تشغيل الملف: {e}")
        bot.edit_message_text(f"❌ فشل في تشغيل الملف: {e}", 
                             call.message.chat.id, 
                             wait_message.message_id)

# معالج زر إيقاف العملية
@bot.callback_query_handler(func=lambda call: call.data.startswith('stop_'))
def stop_process_callback(call):
    user_id = call.from_user.id
    process_id = call.data[5:]  # استخراج معرف العملية من البيانات
    
    if process_id in bot_scripts:
        process_info = bot_scripts[process_id]
        
        # التحقق من أن المستخدم هو نفسه الذي بدأ العملية أو المشرف
        if user_id == process_info['user_id'] or user_id == ADMIN_ID:
            try:
                # إيقاف العملية
                process_info['process'].terminate()
                
                # انتظار العملية لمدة ثانية واحدة
                try:
                    process_info['process'].wait(timeout=1)
                except subprocess.TimeoutExpired:
                    # إذا لم تتوقف العملية، أجبرها على التوقف
                    process_info['process'].kill()
                
                # إزالة العملية من القاموس
                del bot_scripts[process_id]
                
                bot.edit_message_text(f"⏹️ تم إيقاف تشغيل الملف {process_info['file_name']}.", 
                                     call.message.chat.id, 
                                     call.message.message_id)
            except Exception as e:
                logger.error(f"فشل في إيقاف العملية: {e}")
                bot.send_message(call.message.chat.id, f"❌ فشل في إيقاف العملية: {e}")
        else:
            bot.answer_callback_query(call.id, "⚠️ لا يمكنك إيقاف هذه العملية لأنك لست من بدأها.")
    else:
        bot.edit_message_text("⚠️ العملية غير موجودة أو تم إيقافها بالفعل.", 
                             call.message.chat.id, 
                             call.message.message_id)

# معالج زر حذف الملف
@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_'))
def delete_file_callback(call):
    user_id = call.from_user.id
    file_name = call.data[7:]  # استخراج اسم الملف من البيانات
    
    # التحقق من وجود الملف
    user_dir = os.path.join(uploaded_files_dir, str(user_id))
    file_path = os.path.join(user_dir, file_name)
    
    if not os.path.exists(file_path):
        bot.send_message(call.message.chat.id, f"⚠️ الملف {file_name} غير موجود.")
        return
    
    try:
        # حذف الملف
        os.remove(file_path)
        
        # حذف المجلد المؤقت إذا كان موجوداً
        temp_dir = os.path.join(user_dir, 'temp_' + os.path.splitext(file_name)[0])
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        
        # حذف المجلد المستخرج إذا كان موجوداً
        extract_dir = os.path.join(user_dir, os.path.splitext(file_name)[0])
        if os.path.exists(extract_dir):
            shutil.rmtree(extract_dir)
        
        # إزالة الملف من قائمة ملفات المستخدم
        if user_id in user_files and file_name in user_files[user_id]:
            user_files[user_id].remove(file_name)
        
        # إزالة الملف من قاعدة البيانات
        remove_user_file_db(user_id, file_name)
        
        bot.edit_message_text(f"✅ تم حذف الملف {file_name} بنجاح.", 
                             call.message.chat.id, 
                             call.message.message_id)
    except Exception as e:
        logger.error(f"فشل في حذف الملف: {e}")
        bot.send_message(call.message.chat.id, f"❌ فشل في حذف الملف: {e}")

# معالج أمر عرض الملفات
@bot.message_handler(commands=['files'])
def list_files(message):
    user_id = message.from_user.id
    
    # التحقق مما إذا كان المستخدم محظوراً
    if user_id in banned_users:
        bot.send_message(message.chat.id, "⛔ أنت محظور من استخدام هذا البوت. يرجى التواصل مع المطور إذا كنت تعتقد أن هذا خطأ.")
        return
    
    if bot_locked:
        bot.send_message(message.chat.id, "⚠️ البوت مقفل حالياً. الرجاء المحاولة لاحقًا.")
        return
    
    if user_id in user_files and user_files[user_id]:
        files_list = "\n".join(user_files[user_id])
        bot.send_message(message.chat.id, f"📂 الملفات التي قمت برفعها:\n\n{files_list}")
    else:
        bot.send_message(message.chat.id, "📂 لم تقم برفع أي ملفات بعد.")

# معالج أمر المساعدة
@bot.message_handler(commands=['help'])
def help_command(message):
    help_text = """🔍 **دليل استخدام البوت** 🔍

🤖 **الأوامر المتاحة:**
/start - بدء استخدام البوت
/files - عرض الملفات التي قمت برفعها
/help - عرض هذه الرسالة

📤 **كيفية رفع ملف:**
1. اضغط على زر "رفع ملف" في القائمة الرئيسية
2. أرسل الملف الذي تريد رفعه (Python, HTML, CSS, JavaScript, ZIP)
3. بعد رفع الملف، يمكنك تشغيله أو عرضه أو حذفه

🌐 **كيفية رفع موقع ويب:**
1. اضغط على زر "رفع موقع ويب" في القائمة الرئيسية
2. أرسل ملفات الموقع (HTML, CSS, JavaScript) أو أرشيف ZIP يحتوي على الموقع كاملاً
3. بعد رفع الملفات، يمكنك عرض الموقع أو حذفه

⚙️ **ملاحظات هامة:**
- الحد الأقصى لحجم الملف هو 10 ميجابايت
- يتم تثبيت المكتبات المطلوبة تلقائياً عند تشغيل ملفات بايثون
- يمكنك رفع ملفات بايثون فردية أو أرشيفات ZIP تحتوي على مشروع كامل

📞 **للمساعدة:**
إذا واجهتك أي مشكلة، يمكنك التواصل مع المطور عبر الضغط على زر "تواصل مع المالك" في القائمة الرئيسية.
"""
    bot.send_message(message.chat.id, help_text)

# معالج أي رسالة أخرى
@bot.message_handler(func=lambda message: True)
def echo_all(message):
    bot.send_message(message.chat.id, "🤔 لم أفهم ما تريد. يمكنك استخدام /help للحصول على قائمة بالأوامر المتاحة.")

# تشغيل البوت
if __name__ == '__main__':
    try:
        logger.info("بدء تشغيل البوت...")
        bot.polling(none_stop=True)
    except Exception as e:
        logger.error(f"حدث خطأ أثناء تشغيل البوت: {e}")
