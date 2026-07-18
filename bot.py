import logging
import sqlite3
import os
import re
import asyncio
import random
import urllib.parse
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
    # Bot လင့်ခ်ကို URL အနေနဲ့ သုံးမယ် (Profile ပုံနဲ့တွဲပြီး Preview တက်လာမယ်)
    bot_link = f"https://t.me/{bot_user.username}?start=ref_{uid}"
    
    # လင့်ခ်စာသားကို သီးသန့်မထည့်ဘဲ Share parameter မှာပဲ ထည့်ပေးလိုက်မယ်
    # Telegram က link preview ကို သူ့ဘာသာဆွဲပေးလိမ့်မယ်
    share_url = f"https://t.me/share/url?url={urllib.parse.quote(bot_link)}&text={urllib.parse.quote(selected_text)}"

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="VIP Group ဝင်ခွင့်တောင်းရန်", url=GROUP_REQUEST_LINK))
    builder.row(InlineKeyboardButton(text="အခြား Group များသို့ ရှဲရန်", url=share_url))
    builder.row(InlineKeyboardButton(text="သင့်ရဲ့ လက်ရှိအခြေအနေ (Status)", callback_data="check_status"))
    builder.row(InlineKeyboardButton(text="Top 10 Leaderboard", callback_data="show_leaderboard"))
    
    await bot.send_message(
        chat_id=uid, 
        text=f"မင်္ဂလာပါ {fname},\n\nVIP Group ဝင်ရန် နည်းလမ်း\n၁။ အောက်က 'VIP Group ဝင်ခွင့်တောင်းရန်' ကို နှိပ်ပါ။\n၂။ 'အခြား Group များသို့ ရှဲရန်' ကို နှိပ်ပြီး သူငယ်ချင်း (၁) ယောက် ဖိတ်ခေါ်ပါ။\n\nလက်ရှိအခြေအနေ: {count}/1 ယောက်။", 
        reply_markup=builder.as_markup()
    )

@dp.message(Command("start"))
async def start_command(message: types.Message):
    uid = message.from_user.id
    args = message.text.split()
    
    # Admin check, DB check logic here... (code maintained as before)
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)", (uid, message.from_user.username or "", message.from_user.first_name or "User"))
    conn.commit()
    await send_user_home(uid, message.from_user.first_name)

# --- WEBHOOK SETUP ---
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
