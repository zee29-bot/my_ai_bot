import logging
import sqlite3
import os
import re
import asyncio
import random
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiohttp import web
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

# --- CONFIGURATION ---
BOT_TOKEN = "8962171444:AAGfz63sO6HQwlWms51RbaRE5WlROji6aYk"      
GROUP_ID = -1003913717685             
REQUIRED_SHARES = 1                   
GROUP_REQUEST_LINK = "https://t.me/Myanmar_girls01"
ADMIN_ID = 5238487314  

IMAGE_URL = "https://ibb.co/ZR482YQD"

WEBHOOK_HOST = "https://Myaibot-production.up.railway.app"
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
WEB_SERVER_HOST = "0.0.0.0"
WEB_SERVER_PORT = int(os.getenv("PORT", 8080))

# 🛡️ Anti-Ban စနစ်အတွက် ရှင်းလင်းသော စာသားပုံစံ ၄ မျိုး (HTML tags တွေ မပါဝင်စေရန် သန့်စင်ထားသည်)
SHARE_MESSAGES = [
    "VIP Group ကို အခမဲ့ ဝင်လို့ရနေပြီနော်။ အမြန်ဆုံး ဝင်ထားလိုက်တော့",
    "VIP အလန်းစားတွေ နေ့တိုင်းတင်ပေးနေတဲ့ Bot ဖြစ်ပါတယ်။ အောက်ကလင့်ခ်မှာ ဝင်ပါ",
    "ဝင်ကြေးပေးစရာမလိုဘဲ VIP Group ဝင်ချင်သူများ အခုပဲ ဒီ Bot လေးကို နှိပ်ဝင်လိုက်ပါ",
    "VIP Group ဝင်ခွင့်ကို Free ပေးနေပြီမို့ နောက်မကျခင် အခုပဲ လင့်ခ်ကို နှိပ်ဝင်ထားပါ"
]
# ----------------------------------

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- DATABASE SETUP ---
conn = sqlite3.connect("group_gate.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY, 
    username TEXT,
    first_name TEXT,
    count INTEGER DEFAULT 0, 
    referred_by INTEGER
)""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
)""")
conn.commit()

def get_user_count(uid):
    cursor.execute("SELECT count FROM users WHERE user_id=?", (uid,))
    res = cursor.fetchone()
    return res[0] if res else 0

def get_latest_video():
    cursor.execute("SELECT value FROM settings WHERE key='latest_video'")
    res = cursor.fetchone()
    return res[0] if res else None

def set_latest_video(file_id):
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('latest_video', ?)", (file_id,))
    conn.commit()

async def delete_preview_video(chat_id: int, message_id: int, delay: int = 20):
    await asyncio.sleep(delay)
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception:
        pass

# --- ADMIN CONTROL PANEL ---
@dp.callback_query(F.data == "admin_stats")
async def admin_stats_callback(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM users WHERE count > 0")
    active_sharers = cursor.fetchone()[0]
    
    stats_text = (
        f"Admin Control Panel\n\n"
        f"စုစုပေါင်း User အရေအတွက်: {total_users} ယောက်\n"
        f"အနည်းဆုံး လူ ၁ ယောက်ခေါ်ထားသူ: {active_sharers} ယောက်"
    )
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="နောက်သို့", callback_data="admin_back"))
    await callback.message.edit_text(stats_text, reply_markup=builder.as_markup())
    await callback.answer()

@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_callback(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    await callback.message.edit_text("Broadcast စနစ်:\n\nUser အားလုံးဆီ ပို့ချင်တဲ့စာသား၊ ပုံ သို့မဟုတ် ဗီဒီယိုကို ဒီ Message ကို Reply ပြန်ပြီး ပို့ပေးပါ။")
    await callback.answer()

@dp.callback_query(F.data == "admin_back")
async def admin_back_callback(callback: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="ကိန်းဂဏန်းများကြည့်ရန်", callback_data="admin_stats"))
    builder.row(InlineKeyboardButton(text="အားလုံးဆီ စာပို့ရန် (Broadcast)", callback_data="admin_broadcast"))
    await callback.message.edit_text("Admin Control Panel\n\nလုပ်ဆောင်လိုသည့် လုပ်ငန်းစဉ်ကို ရွေးချယ်ပါ။", reply_markup=builder.as_markup())
    await callback.answer()

@dp.message(F.chat.type == "private", F.from_user.id == ADMIN_ID, F.reply_to_message)
async def do_broadcast(message: types.Message):
    if "User အားလုံးဆီ ပို့ချင်တဲ့စာသား" not in message.reply_to_message.text: return
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    status_msg = await message.reply(f"User စစုပေါင်း {len(users)} ယောက်ဆီသို့ စတင်ပို့ဆောင်နေပါပြီ...")
    success, fail = 0, 0
    for user in users:
        uid = user[0]
        try:
            await bot.copy_message(chat_id=uid, from_chat_id=message.chat.id, message_id=message.message_id)
            success += 1
            await asyncio.sleep(0.05)
        except Exception:
            fail += 1
    await status_msg.edit_text(f"Broadcast ပို့ဆောင်ပြီးပါပြီ။\n\nအောင်မြင်: {success}\nကျရှုံး: {fail}")

@dp.message(F.chat.type == "private", F.from_user.id == ADMIN_ID, F.video)
async def save_admin_preview_video(message: types.Message):
    set_latest_video(message.video.file_id)
    await message.reply("Preview ဗီဒီယိုကို သိမ်းဆည်းလိုက်ပါပြီ။")

# --- GROUP MESSAGES AUTO-DELETE ---
@dp.message(F.chat.id == GROUP_ID)
async def handle_group_messages(message: types.Message):
    if message.new_chat_members or message.left_chat_member:
        try: await message.delete()
        except: pass
        return
    has_link = False
    if message.text and (re.search(r"t\.me", message.text, re.IGNORECASE) or message.entities):
        for entity in message.entities or []:
            if entity.type in ["url", "text_link"]: has_link = True; break
    if message.caption and (re.search(r"t\.me", message.caption, re.IGNORECASE) or message.caption_entities):
        for entity in message.caption_entities or []:
            if entity.type in ["url", "text_link"]: has_link = True; break
    if has_link:
        try:
            member = await bot.get_chat_member(chat_id=GROUP_ID, user_id=message.from_user.id)
            if member.status not in ["creator", "administrator"]: await message.delete()
        except: pass

# --- MAIN USER PROCESS ---
@dp.message(Command("start"))
async def start_command(message: types.Message):
    if message.chat.type != "private": return
    uid = message.from_user.id
    uname = message.from_user.username or ""
    fname = message.from_user.first_name or "User"
    args = message.text.split()
    
    if uid == ADMIN_ID:
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="ကိန်းဂဏန်းများကြည့်ရန်", callback_data="admin_stats"))
        builder.row(InlineKeyboardButton(text="အားလုံးဆီ စာပို့ရန် (Broadcast)", callback_data="admin_broadcast"))
        await message.answer("Admin Control Panel\n\nလုပ်ဆောင်လိုသည့် လုပ်ငန်းစဉ်ကို ရွေးချယ်ပါ။", reply_markup=builder.as_markup())
        return

    cursor.execute("SELECT user_id FROM users WHERE user_id=?", (uid,))
    user_exists = cursor.fetchone()
    
    if not user_exists:
        referrer_id = None
        if len(args) > 1 and args[1].startswith("ref_"):
            try:
                referrer_id = int(args[1].replace("ref_", ""))
                if referrer_id != uid:
                    cursor.execute("INSERT OR IGNORE INTO users (user_id, count, username, first_name) VALUES (?, 0, '', '')", (referrer_id,))
                    cursor.execute("UPDATE users SET count = count + 1 WHERE user_id=?", (referrer_id,))
                    conn.commit()
                    current_points = get_user_count(referrer_id)
                    try:
                        if current_points >= REQUIRED_SHARES:
                            await bot.approve_chat_join_request(chat_id=GROUP_ID, user_id=referrer_id)
                            await bot.send_message(referrer_id, "အောင်မြင်ပါပြီ! လူ ၁ ယောက် ဝင်လာခဲ့လို့ Group ထဲ auto သွတ်သွင်းပေးလိုက်ပါပြီ။")
                        else:
                            await bot.send_message(referrer_id, f"လူသစ်တစ်ယောက် တိုးလာပါပြီ။ လက်ရှိ: {current_points}/{REQUIRED_SHARES} ယောက်။")
                    except: pass
            except ValueError: pass
        cursor.execute("INSERT INTO users (user_id, count, referred_by, username, first_name) VALUES (?, 0, ?, ?, ?)", (uid, referrer_id, uname, fname))
        conn.commit()
    else:
        cursor.execute("UPDATE users SET username=?, first_name=? WHERE user_id=?", (uname, fname, uid))
        conn.commit()

    await send_user_home(uid, fname)

async def send_user_home(uid, fname):
    count = get_user_count(uid)
    bot_user = await bot.get_me()
    
    selected_text = random.choice(SHARE_MESSAGES)
    bot_link = f"https://t.me/{bot_user.username}?start=ref_{uid}"
    
    # 🌟 Telegram HTML Formatting ကိုသုံးပြီး စာသားရဲ့ ပထမဆုံး စကားလုံးမှာ ပုံလင့်ခ်ကို ဝှက်ထားလိုက်ပါတယ် (လင့်ခ်စာသား လုံးဝမပေါ်တော့ဘဲ ပုံ Preview အလုပ်လုပ်ပါတယ်)
    # စာသားပုံစံအတိုင်း သန့်သန့်လေးထွက်လာပါမယ်
    share_content = f'<a href="{IMAGE_URL}"> </a>{selected_text}\n\n{bot_link}'
    
    # URL parameter များကို သေချာချိတ်ဆက်ပေးခြင်းဖြင့် အမှားကင်းစင်စေပါတယ်
    import urllib.parse
    encoded_content = urllib.parse.quote(share_content)
    share_url = f"https://t.me/share/url?url={encoded_content}"

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="VIP Group ဝင်ခွင့်တောင်းရန်", url=GROUP_REQUEST_LINK))
    builder.row(InlineKeyboardButton(text="အခြား Group များသို့ ရှဲရန်", url=share_url))
    builder.row(InlineKeyboardButton(text="သင့်ရဲ့ လက်ရှိအခြေအနေ (Status)", callback_data="check_status"))
    builder.row(InlineKeyboardButton(text="Top 10 Leaderboard", callback_data="show_leaderboard"))
    
    instructions_text = (
        f"မင်္ဂလာပါ {fname},\n\n"
        f"VIP Group ဝင်ရန် နည်းလမ်း\n"
        f"၁။ အောက်က 'VIP Group ဝင်ခွင့်တောင်းရန်' ခလုတ်ကို အရင်နှိပ်ထားပါ။\n"
        f"၂။ 'အခြား Group များသို့ ရှဲရန်' ခလုတ်ကို နှိပ်ပြီး သူငယ်ချင်း (၁) ယောက်ကို ဖိတ်ခေါ်ပေးပါ။\n\n"
        f"လက်ရှိအခြေအနေ\n"
        f"သင် ဖိတ်ခေါ်ထားသူ - {count}/1 ယောက်။"
    )

    video_to_send = get_latest_video()
    if video_to_send:
        try:
            preview_msg = await bot.send_video(chat_id=uid, video=video_to_send, caption="Preview Video (၂၀ စက္ကန့်သာပြမည်)")
            asyncio.create_task(delete_preview_video(chat_id=uid, message_id=preview_msg.message_id, delay=20))
        except: pass

    await bot.send_message(chat_id=uid, text=instructions_text, reply_markup=builder.as_markup())

# --- CALLBACK HANDLERS FOR USER BUTTONS ---
@dp.callback_query(F.data == "check_status")
async def check_status_callback(callback: types.CallbackQuery):
    uid = callback.from_user.id
    count = get_user_count(uid)
    await callback.answer(f"လက်ရှိ သင်ဖိတ်ခေါ်ထားသူ: {count}/1 ယောက်", show_alert=True)

@dp.callback_query(F.data == "show_leaderboard")
async def leaderboard_callback(callback: types.CallbackQuery):
    cursor.execute("SELECT user_id, username, first_name, count FROM users WHERE count > 0 ORDER BY count DESC LIMIT 10")
    top_users = cursor.fetchall()
    text = "Top 10 - လူခေါ်နိုင်သူများ\n\n"
    if not top_users: text += "လက်ရှိတွင် လူခေါ်ထားသူ မရှိသေးပါ။"
    else:
        for i, user in enumerate(top_users, 1):
            user_id, username, first_name, count = user
            user_display = f"@{username}" if username and username.strip() else f"{first_name or 'User'}"
            text += f"{i}. {user_display} — {count} ယောက်\n"
    text += "\nသင်လည်း အဆင့် (၁) ရအောင် အခုပဲ သူငယ်ချင်းတွေကို ထပ်ဖိတ်ခေါ်လိုက်ပါ။"
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="နောက်သို့", callback_data="back_to_start"))
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()

@dp.callback_query(F.data == "back_to_start")
async def back_to_start_callback(callback: types.CallbackQuery):
    try: await callback.message.delete()
    except: pass
    await send_user_home(callback.from_user.id, callback.from_user.first_name)
    await callback.answer()

@dp.chat_join_request()
async def handle_join_request(update: types.ChatJoinRequest):
    uid = update.from_user.id
    count = get_user_count(uid)
    if count >= REQUIRED_SHARES:
        try: await bot.approve_chat_join_request(chat_id=GROUP_ID, user_id=uid); return
        except: pass
        
    bot_user = await bot.get_me()
    selected_text = random.choice(SHARE_MESSAGES)
    bot_link = f"https://t.me/{bot_user.username}?start=ref_{uid}"
    
    share_content = f'<a href="{IMAGE_URL}"> </a>{selected_text}\n\n{bot_link}'
    import urllib.parse
    encoded_content = urllib.parse.quote(share_content)
    share_url = f"https://t.me/share/url?url={encoded_content}"
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Share လုပ်ရန်", url=share_url))
    try:
        await bot.send_message(
            chat_id=uid,
            text=f"မင်္ဂလာပါ {update.from_user.first_name}။\n\nVIP Group ဝင်ခွင့်တောင်းထားတာကို လက်ခံရရှိပါတယ်၊ ဒါပေမယ့် စည်းကမ်းချက်အတိုင်း လူ ၁ ယောက် မပြည့်သေးပါဘူးဗျာ။\nအောက်ကခလုတ်ကို နှိပ်ပြီး လူ (၁) ယောက်ပြည့်အောင် အရင်ဆုံး ခေါ်ပေးပါဦးနော်။\n\n%s: {count}/1 ယောက်။" % "လက်ရှိ သင့်လင့်ခ်မှ ဝင်လာသူ",
            reply_markup=builder.as_markup()
        )
    except: pass

async def on_startup(bot: Bot) -> None:
    await bot.set_webhook(WEBHOOK_URL)

def main():
    dp.startup.register(on_startup)
    app = web.Application()
    webhook_requests_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_requests_handler.register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)
    web.run_app(app, host=WEB_SERVER_HOST, port=WEB_SERVER_PORT)

if __name__ == "__main__":
    main()
