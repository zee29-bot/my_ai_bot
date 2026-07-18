import logging
import sqlite3
import os
import random
import urllib.parse
import asyncio
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

WEBHOOK_HOST = "https://Myaibot-production.up.railway.app"
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
WEB_SERVER_HOST = "0.0.0.0"
WEB_SERVER_PORT = int(os.getenv("PORT", 8080))

SHARE_MESSAGES = [
    "VIP Group ကို အခမဲ့ ဝင်လို့ရနေပြီနော်။ အမြန်ဆုံး ဝင်ထားလိုက်တော့",
    "VIP အလန်းစားတွေ နေ့တိုင်းတင်ပေးနေတဲ့ Bot ဖြစ်ပါတယ်။ အောက်ကလင့်ခ်မှာ ဝင်ပါ",
    "ဝင်ကြေးပေးစရာမလိုဘဲ VIP Group ဝင်ချင်သူများ အခုပဲ ဒီ Bot လေးကို နှိပ်ဝင်လိုက်ပါ",
    "VIP Group ဝင်ခွင့်ကို Free ပေးနေပြီမို့ နောက်မကျခင် အခုပဲ လင့်ခ်ကို နှိပ်ဝင်ထားပါ"
]

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- DATABASE ---
conn = sqlite3.connect("group_gate.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, count INTEGER DEFAULT 0, referred_by INTEGER)")
cursor.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
conn.commit()

def get_user_count(uid):
    cursor.execute("SELECT count FROM users WHERE user_id=?", (uid,))
    res = cursor.fetchone()
    return res[0] if res else 0

def get_latest_video():
    cursor.execute("SELECT value FROM settings WHERE key='latest_video'")
    res = cursor.fetchone()
    return res[0] if res else None

# --- MAIN LOGIC ---
async def send_user_home(uid, fname):
    count = get_user_count(uid)
    bot_user = await bot.get_me()
    
    selected_text = random.choice(SHARE_MESSAGES)
    bot_link = f"https://t.me/{bot_user.username}?start=ref_{uid}"
    
    # 🌟 ဒီမှာ ကောင်မလေးပုံ Direct Link ကို သုံးပြီး Share တဲ့အခါ ပုံသေချာပေါက် ပေါ်အောင် လုပ်ထားပါတယ်
    share_url = f"https://t.me/share/url?url={urllib.parse.quote(bot_link)}&text={urllib.parse.quote(selected_text)}&image=https://i.ibb.co/BqpCrxH/ZR482YQD.jpg"

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="VIP Group ဝင်ခွင့်တောင်းရန်", url=GROUP_REQUEST_LINK))
    builder.row(InlineKeyboardButton(text="အခြား Group များသို့ ရှဲရန်", url=share_url))
    builder.row(InlineKeyboardButton(text="သင့်ရဲ့ လက်ရှိအခြေအနေ (Status)", callback_data="check_status"))
    builder.row(InlineKeyboardButton(text="Top 10 Leaderboard", callback_data="show_leaderboard"))
    
    text_message = (
        f"မင်္ဂလာပါ {fname},\n\n"
        f"VIP Group ဝင်ရန် နည်းလမ်း\n"
        f"၁။ အောက်က 'VIP Group ဝင်ခွင့်တောင်းရန်' ကို အရင်နှိပ်ထားပါ။\n"
        f"၂။ 'အခြား Group များသို့ ရှဲရန်' ကို နှိပ်ပြီး သူငယ်ချင်း (၁) ယောက် ဖိတ်ခေါ်ပေးပါ။\n\n"
        f"လက်ရှိအခြေအနေ: {count}/1 ယောက်။"
    )
    
    await bot.send_message(chat_id=uid, text=text_message, reply_markup=builder.as_markup())

async def send_admin_home(uid):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="ကိန်းဂဏန်းများကြည့်ရန်", callback_data="admin_stats"))
    builder.row(InlineKeyboardButton(text="အားလုံးဆီ စာပို့ရန် (Broadcast)", callback_data="admin_broadcast"))
    await bot.send_message(chat_id=uid, text="Admin Control Panel\n\nလုပ်ဆောင်လိုသည့် လုပ်ငန်းစဉ်ကို ရွေးချယ်ပါ။", reply_markup=builder.as_markup())

@dp.message(Command("start"))
async def start_command(message: types.Message):
    uid = message.from_user.id
    
    # 👑 Admin ဖြစ်ခဲ့ရင် ရိုးရိုးခလုတ်တွေမပြဘဲ Admin Control Panel ပဲ ပြပေးမှာပါ
    if uid == ADMIN_ID:
        await send_admin_home(uid)
        return

    cursor.execute("INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)", 
                   (uid, message.from_user.username or "", message.from_user.first_name or "User"))
    
    args = message.text.split()
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            referrer_id = int(args[1].split("_")[1])
            if referrer_id != uid:
                cursor.execute("SELECT referred_by FROM users WHERE user_id=?", (uid,))
                already_referred = cursor.fetchone()
                if already_referred and already_referred[0] is None:
                    cursor.execute("UPDATE users SET referred_by=? WHERE user_id=?", (referrer_id, uid))
                    cursor.execute("UPDATE users SET count = count + 1 WHERE user_id=?", (referrer_id,))
                    conn.commit()
                    try:
                        await bot.send_message(chat_id=referrer_id, text="🎉 သင့်လင့်ခ်မှ လူသစ်တစ်ယောက် ဝင်ရောက်လာပါပြီ။")
                    except: pass
        except Exception as e:
            logging.error(f"Referral error: {e}")
            
    conn.commit()
    await send_user_home(uid, message.from_user.first_name)

# --- ADMIN PANEL ACTIONS ---
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
    if callback.from_user.id != ADMIN_ID: return
    try: await callback.message.delete()
    except: pass
    await send_admin_home(callback.from_user.id)
    await callback.answer()

# --- USER CALLBACKS ---
@dp.callback_query(F.data == "check_status")
async def check_status(callback: types.CallbackQuery):
    count = get_user_count(callback.from_user.id)
    await callback.answer(f"သင်ဖိတ်ခေါ်ထားသူ: {count}/{REQUIRED_SHARES} ယောက်", show_alert=True)

@dp.callback_query(F.data == "show_leaderboard")
async def show_leaderboard(callback: types.CallbackQuery):
    cursor.execute("SELECT first_name, count FROM users ORDER BY count DESC LIMIT 10")
    top_users = cursor.fetchall()
    if not top_users:
        await callback.answer("Leaderboard မှာ အချက်အလက်မရှိသေးပါ", show_alert=True)
        return
    text = "🏆 Top 10 Leaderboard 🏆\n\n"
    for idx, user in enumerate(top_users, 1):
        text += f"{idx}. {user[0]} - {user[1]} ယောက်\n"
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="နောက်သို့", callback_data="user_back"))
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()

@dp.callback_query(F.data == "user_back")
async def user_back_callback(callback: types.CallbackQuery):
    try: await callback.message.delete()
    except: pass
    await send_user_home(callback.from_user.id, callback.from_user.first_name)
    await callback.answer()

@dp.chat_join_request()
async def handle_join_request(update: types.ChatJoinRequest):
    uid = update.from_user.id
    count = get_user_count(uid)
    if count >= REQUIRED_SHARES:
        try:
            await bot.approve_chat_join_request(chat_id=GROUP_ID, user_id=uid)
            return
        except: pass
        
    bot_user = await bot.get_me()
    selected_text = random.choice(SHARE_MESSAGES)
    bot_link = f"https://t.me/{bot_user.username}?start=ref_{uid}"
    share_url = f"https://t.me/share/url?url={urllib.parse.quote(bot_link)}&text={urllib.parse.quote(selected_text)}&image=https://i.ibb.co/BqpCrxH/ZR482YQD.jpg"
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Share လုပ်ရန်", url=share_url))
    try:
        await bot.send_message(
            chat_id=uid,
            text=f"မင်္ဂလာပါ {update.from_user.first_name}။\n\nVIP Group ဝင်ခွင့်တောင်းထားတာကို လက်ခံရရှိပါတယ်၊ ဒါပေမယ့် စည်းကမ်းချက်အတိုင်း လူ ၁ ယောက် မပြည့်သေးပါဘူးဗျာ။\nအောက်ကခလုတ်ကို နှိပ်ပြီး လူ (၁) ယောက်ပြည့်အောင် အရင်ဆုံး ခေါ်ပေးပါဦးနော်။\n\nလက်ရှိ သင့်လင့်ခ်မှ ဝင်လာသူ: {count}/1 ယောက်။",
            reply_markup=builder.as_markup()
        )
    except: pass

async def on_startup(bot: Bot) -> None:
    await bot.delete_webhook(drop_pending_updates=True)
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
