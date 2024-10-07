import os
import aiohttp
import asyncio
import json
from bs4 import BeautifulSoup
from telethon import TelegramClient, events, Button
import re
from telethon.errors.rpcerrorlist import FloodWaitError

# تحميل المتغيرات البيئية
api_id = os.getenv('API_ID')
api_hash = os.getenv('API_HASH')
bot_token = os.getenv('BOT_TOKEN')

# تهيئة عميل Telethon
client = TelegramClient('bot', api_id, api_hash).start(bot_token=bot_token)

# الحد الأقصى لحجم الملف (1 جيجابايت)
MAX_FILE_SIZE = 1 * 1024 * 1024 * 1024  # 1 GB

# ملف تخزين لغات المستخدمين
LANG_FILE = 'user_languages.json'

# تحميل لغات المستخدمين من الملف
if os.path.exists(LANG_FILE):
    with open(LANG_FILE, 'r', encoding='utf-8') as f:
        user_languages = json.load(f)
else:
    user_languages = {}

# حفظ لغات المستخدمين في الملف
def save_user_languages():
    with open(LANG_FILE, 'w', encoding='utf-8') as f:
        json.dump(user_languages, f, ensure_ascii=False, indent=4)

# دالة لتحديد لغة المستخدم
def get_user_language(user_id):
    return user_languages.get(str(user_id), 'en')  # اللغة الافتراضية الإنجليزية

# دالة لاستخراج رابط التحميل المباشر من صفحة MediaFire
async def get_download_link(mediafire_url):
    """استخراج الرابط المباشر للتحميل من صفحة MediaFire."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/58.0.3029.110 Safari/537.3',
        'Referer': mediafire_url
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(mediafire_url, headers=headers) as response:
            if response.status == 200:
                text = await response.text()
                soup = BeautifulSoup(text, 'html.parser')
                download_link = soup.find('a', {'id': 'downloadButton'})
                if download_link and 'href' in download_link.attrs:
                    return download_link['href']
                else:
                    return None
            else:
                return None

# دالة لتحميل الملف مع تحديث التقدم
async def download_file(download_url, file_path, progress_callback):
    """تحميل ملف بشكل غير متزامن وتحديث التقدم عبر callback."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/58.0.3029.110 Safari/537.3'
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(download_url, headers=headers) as response:
            if response.status != 200:
                raise Exception(f"فشل في تحميل الملف. كود الحالة: {response.status}")

            total_size = int(response.headers.get('content-length', 0))
            if total_size > MAX_FILE_SIZE:
                raise Exception("حجم الملف يتجاوز الحد الأقصى المسموح به (1 جيجابايت).")

            chunk_size = 1024
            downloaded = 0

            with open(file_path, 'wb') as f:
                async for chunk in response.content.iter_chunked(chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            percentage = downloaded / total_size * 100
                            await progress_callback(percentage)

# تعريف الرسائل باللغتين الإنجليزية والعربية
messages = {
    'en': {
        'start': "Hello! Send me a MediaFire link, and I'll download the file and send it back to you.",
        'invalid_link': "Please send a valid MediaFire link.",
        'starting_download': "Starting download...",
        'download_progress': "Download progress: {percentage:.2f}%",
        'download_completed': "Download completed. Sending the file...",
        'file_sent': "File sent successfully!",
        'error_downloading': "Error downloading file: {error}",
        'error_processing': "An error occurred while processing your request.",
        'cannot_determine_filename': "Sorry, couldn't determine the file name.",
        'cannot_extract_link': "Sorry, couldn't extract the direct download link from MediaFire.",
        'file_too_large': "Sorry, the file is too large to download. Maximum allowed size is 1 GB.",
        'select_language': "Please select your preferred language:",
        'language_set': "Language set to English."
    },
    'ar': {
        'start': "مرحباً! أرسل لي رابط MediaFire، وسأقوم بتحميل الملف وإرساله إليك.",
        'invalid_link': "يرجى إرسال رابط MediaFire صحيح.",
        'starting_download': "بدء التحميل...",
        'download_progress': "تقدم التحميل: {percentage:.2f}%",
        'download_completed': "اكتمل التحميل. جارٍ إرسال الملف...",
        'file_sent': "تم إرسال الملف بنجاح!",
        'error_downloading': "حدث خطأ أثناء تحميل الملف: {error}",
        'error_processing': "حدث خطأ أثناء معالجة طلبك.",
        'cannot_determine_filename': "عذراً، لم أتمكن من تحديد اسم الملف.",
        'cannot_extract_link': "عذراً، لم أتمكن من استخراج الرابط المباشر من MediaFire.",
        'file_too_large': "عذراً، حجم الملف كبير جداً للتحميل. الحد الأقصى المسموح به هو 1 جيجابايت.",
        'select_language': "يرجى اختيار لغتك المفضلة:",
        'language_set': "تم تعيين اللغة إلى العربية."
    }
}

# معالج الرسائل الجديدة
@client.on(events.NewMessage)
async def handler(event):
    try:
        user_id = event.sender_id
        message = event.message.message.strip()
        user_lang = get_user_language(user_id)

        # إذا لم يقم المستخدم باختيار لغة بعد
        if str(user_id) not in user_languages:
            if message.startswith("/start") or message.startswith("/ابدأ"):
                # إرسال خيارات اختيار اللغة
                await event.respond(
                    messages['en']['select_language'] if user_lang == 'en' else messages['ar']['select_language'],
                    buttons=[
                        [Button.inline("English", b"lang_en")],
                        [Button.inline("العربية", b"lang_ar")]
                    ]
                )
            else:
                await event.respond(
                    messages['en']['select_language'] if user_lang == 'en' else messages['ar']['select_language'],
                    buttons=[
                        [Button.inline("English", b"lang_en")],
                        [Button.inline("العربية", b"lang_ar")]
                    ]
                )
            return

        # التعامل مع أوامر /start و /ابدأ بعد اختيار اللغة
        if message.startswith("/start") or message.startswith("/ابدأ"):
            await event.respond(messages[user_lang]['start'])
            return

        # التحقق مما إذا كانت الرسالة تحتوي على رابط MediaFire
        if 'mediafire.com' in message:
            mediafire_url = message

            # استخراج الرابط المباشر
            download_link = await get_download_link(mediafire_url)

            if download_link:
                # استخراج اسم الملف
                file_name_match = re.findall(r"([^/]+)$", download_link)
                if not file_name_match:
                    await event.reply(messages[user_lang]['cannot_determine_filename'])
                    return
                file_name = file_name_match[0].split('?')[0]

                # إرسال رسالة تشير إلى بدء التحميل
                progress_message = await event.reply(messages[user_lang]['starting_download'])

                # دالة لتحديث التقدم
                async def update_progress(percentage):
                    await progress_message.edit(messages[user_lang]['download_progress'].format(percentage=percentage))

                # تحميل الملف مع تحديث التقدم
                try:
                    await download_file(download_link, file_name, update_progress)
                except Exception as e:
                    error_text = str(e)
                    if "exceeds" in error_text or "الحجم" in error_text:
                        await progress_message.edit(messages[user_lang]['file_too_large'])
                    else:
                        await progress_message.edit(messages[user_lang]['error_downloading'].format(error=error_text))
                    return

                # تحديث الرسالة للإشارة إلى اكتمال التحميل
                await progress_message.edit(messages[user_lang]['download_completed'])

                # إرسال الملف إلى المستخدم
                try:
                    await client.send_file(event.chat_id, file_name)
                    # حذف الملف من الخادم بعد الإرسال
                    os.remove(file_name)
                    await progress_message.edit(messages[user_lang]['file_sent'])
                except FloodWaitError as fwe:
                    await progress_message.edit(f"Flood wait error. Please try again after {fwe.seconds} seconds.")
                    # يمكنك إضافة تأخير هنا إذا رغبت
                except Exception as e:
                    await progress_message.edit(messages[user_lang]['error_downloading'].format(error=str(e)))

            else:
                await event.reply(messages[user_lang]['cannot_extract_link'])
        else:
            await event.reply(messages[user_lang]['invalid_link'])
    except FloodWaitError as fwe:
        # الانتظار لمدة المحددة ثم المحاولة مرة أخرى
        print(f"FloodWaitError: must wait for {fwe.seconds} seconds")
        await asyncio.sleep(fwe.seconds)
        # يمكن إرسال رسالة للمستخدم لإعلامه بالانتظار
        try:
            user_lang = get_user_language(event.sender_id)
            await event.reply(
                "You are sending messages too quickly. Please wait before trying again."
                if user_lang == 'en' else
                "أنت ترسل الرسائل بسرعة كبيرة. يرجى الانتظار قبل المحاولة مرة أخرى."
            )
        except Exception:
            pass
    except Exception as e:
        user_lang = get_user_language(event.sender_id)
        error_messages = {
            'en': "An error occurred while processing your request.",
            'ar': "حدث خطأ أثناء معالجة طلبك."
        }
        try:
            await event.reply(error_messages.get(user_lang, "An error occurred while processing your request."))
        except FloodWaitError as fwe:
            print(f"FloodWaitError: must wait for {fwe.seconds} seconds")
            await asyncio.sleep(fwe.seconds)
        except Exception:
            pass
        # يمكن تسجيل الخطأ للاطلاع عليه لاحقاً
        # print(f"Error handling message: {e}")

# معالج للأزرار
@client.on(events.CallbackQuery)
async def callback_handler(event):
    try:
        user_id = event.sender_id
        data = event.data.decode('utf-8')

        if data == "lang_en":
            user_languages[str(user_id)] = 'en'
            save_user_languages()
            await event.edit(messages['en']['language_set'])
        elif data == "lang_ar":
            user_languages[str(user_id)] = 'ar'
            save_user_languages()
            await event.edit(messages['ar']['language_set'])
    except FloodWaitError as fwe:
        print(f"FloodWaitError: must wait for {fwe.seconds} seconds")
        await asyncio.sleep(fwe.seconds)
        try:
            user_lang = get_user_language(event.sender_id)
            await event.respond(
                "You are sending messages too quickly. Please wait before trying again."
                if user_lang == 'en' else
                "أنت ترسل الرسائل بسرعة كبيرة. يرجى الانتظار قبل المحاولة مرة أخرى."
            )
    except Exception as e:
        # يمكن تسجيل الخطأ للاطلاع عليه لاحقاً
        # print(f"Error handling callback: {e}")
        pass

# بدء تشغيل البوت
if __name__ == "__main__":
    try:
        print("Bot started successfully.")
        client.run_until_disconnected()
    except Exception as e:
        print(f"Error starting the bot: {e}")
