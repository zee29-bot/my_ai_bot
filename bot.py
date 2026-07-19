import logging
import sqlite3
import os
import urllib.parse
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
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

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- STATES ---
class AdminStates(StatesGroup):
    waiting_for_broadcast_msg = State()

# --- DATABASE ---
conn = sqlite3.connect("group_gate.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, first_name TEXT, count INTEGER DEFAULT 0, referred_by INTEGER, has_requested INTEGER DEFAULT 0)")
cursor.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
conn.commit()

def get_user_count(uid):
    cursor.execute("SELECT count FROM users WHERE user_id=?", (uid,))
    res = cursor.fetchone()
    return res[0] if res else 0

def get_admin_stats():
    # စုစုပေါင်း User အရေအတွက် တွက်ရန်
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    
    # Share ပြီးမြောက်မှု အောင်မြင်သူ အရေအတွက် တွက်ရန် (count >= REQUIRED_SHARES)
    cursor.execute("SELECT COUNT(*) FROM users WHERE count >= ?", (REQUIRED_SHARES,))
    total_completed = cursor.fetchone()[0]
    
    return total_users, total_completed

# --- UI FOR USER ---
async def send_welcome(uid, fname):
    count = get_user_count(uid)
    bot_user = await bot.get_me()
    
    bot_link = f"https://t.me/{bot_user.username}?start=ref_{uid}"
    share_url = f"https://t.me/share/url?url={urllib.parse.quote(bot_link)}&text={urllib.parse.quote('VIP Group ဝင်ရန် ဒီလင့်ခ်ကိုနှိပ်ပါ')}"

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="VIP Group ဝင်ရန်", url=GROUP_REQUEST_LINK))
    builder.row(InlineKeyboardButton(text="သူငယ်ချင်းထံ ရှဲပေးရန်", url=share_url))
    builder.row(InlineKeyboardButton(text="အခြေအနေ စစ်ဆေးရန်", callback_data="check"))
    
    text = (
        f"မင်္ဂလာပါ {fname}\n\n"
        f"VIP Group ဝင်ရောက်ရန် အောက်ပါအတိုင်း လုပ်ဆောင်ပါ။\n\n"
        f"၁။ VIP Group ဝင်ရန် (နှိပ်ပါ)\n"
        f"၂။ သူငယ်ချင်းတစ်ယောက်ကို ဖိတ်ခေါ်ပေးပါ\n\n"
        f"လက်ရှိဖိတ်ခေါ်ပြီးသူ: {count} / {REQUIRED_SHARES}\n\n"
        f"⚡️ [သူငယ်ချင်း ၁ ယောက် ဝင်လာတာနဲ့ VIP Group ထဲ အလိုအလျောက် တန်းထည့်ပေးမှာ ဖြစ်ပါတယ်။]"
    )
    
    await bot.send_message(chat_id=uid, text=text, reply_markup=builder.as_markup())

# --- COMMAND START ---
@dp.message(Command("start"))
async def start(message: types.Message):
    uid = message.from_user.id
    
    # 👑 ADMIN PANEL (WITH LIVE STATS)
    if uid == ADMIN_ID:
        total_users, total_completed = get_admin_stats()
        
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="📢 လူအားလုံးဆီ စာ/လင့်ခ် ပို့ရန် (Broadcast)", callback_data="admin_broadcast"))
        builder.row(InlineKeyboardButton(text="🔄 အချက်အလက်များ Refresh လုပ်ရန်", callback_data="admin_refresh"))
        builder.row(InlineKeyboardButton(text="👤 User Interface အတိုင်းကြည့်ရန်", callback_data="view_as_user"))
        
        admin_text = (
            f"⚙️ **Admin Control Panel**\n\n"
            f"📊 **လက်ရှိ Bot ရဲ့ အခြေအနေ**\n"
            f"• စုစုပေါင်း သုံးစွဲသူ (Total Users): {total_users} ယောက်\n"
            f"• Share အောင်မြင်ပြီးသူ (Completed Shares): {total_completed} ယောက်\n\n"
            f"အောက်က ခလုတ်များကို အသုံးပြုနိုင်ပါသည်။"
        )
        await message.reply(admin_text, reply_markup=builder.as_markup())
        return

    # NORMAL USER
    cursor.execute("INSERT OR IGNORE INTO users (user_id, first_name) VALUES (?, ?)", (uid, message.from_user.first_name))
    
    args = message.text.split()
    if len(args) > 1 and args[1].startswith("ref_"):
        referrer = int(args[1].split("_")[1])
        if referrer != uid:
            cursor.execute("SELECT referred_by FROM users WHERE user_id=?", (uid,))
            if cursor.fetchone()[0] is None:
                cursor.execute("UPDATE users SET referred_by=? WHERE user_id=?", (referrer, uid))
                cursor.execute("UPDATE users SET count = count + 1 WHERE user_id=?", (referrer,))
                conn.commit()
                
                count = get_user_count(referrer)
                cursor.execute("SELECT has_requested FROM users WHERE user_id=?", (referrer,))
                has_req = cursor.fetchone()[0]
                
                if count >= REQUIRED_SHARES and has_req == 1:
                    try: await bot.approve_chat_join_request(chat_id=GROUP_ID, user_id=referrer)
                    except: pass
    conn.commit()
    await send_welcome(uid, message.from_user.first_name)

# --- ADMIN CALLBACKS & BROADCAST LOGIC ---
@dp.callback_query(F.data == "admin_broadcast", F.from_user.id == ADMIN_ID)
async def start_broadcast(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_broadcast_msg)
    await call.message.edit_text("💬 လူအားလုံးဆီ ပို့ချင်တဲ့ 'စာသား' သို့မဟုတ် 'လင့်ခ်' ကို ရိုက်ပြီး ပို့ပေးပါဗျာ -")
    await call.answer()

@dp.callback_query(F.data == "admin_refresh", F.from_user.id == ADMIN_ID)
async def refresh_admin_stats(call: types.CallbackQuery):
    total_users, total_completed = get_admin_stats()
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📢 လူအားလုံးဆီ စာ/လင့်ခ် ပို့ရန် (Broadcast)", callback_data="admin_broadcast"))
    builder.row(InlineKeyboardButton(text="🔄 အချက်အလက်များ Refresh လုပ်ရန်", callback_data="admin_refresh"))
    builder.row(InlineKeyboardButton(text="👤 User Interface အတိုင်းကြည့်ရန်", callback_data="view_as_user"))
    
    admin_text = (
        f"⚙️ **Admin Control Panel**\n\n"
        f"📊 **လက်ရှိ Bot ရဲ့ အခြေအနေ (Updated)**\n"
        f"• စုစုပေါင်း သုံးစွဲသူ (Total Users): {total_users} ယောက်\n"
        f"• Share အောင်မြင်ပြီးသူ (Completed Shares): {total_completed} ယောက်\n\n"
        f"အောက်က ခလုတ်များကို အသုံးပြုနိုင်ပါသည်။"
    )
    try:
        await call.message.edit_text(admin_text, reply_markup=builder.as_markup())
    except Exception:
        pass
    await call.answer("အချက်အလက်များကို Update လုပ်လိုက်ပါပြီ။")

@dp.callback_query(F.data == "view_as_user", F.from_user.id == ADMIN_ID)
async def view_as_user(call: types.CallbackQuery):
    await call.message.delete()
    await send_welcome(call.from_user.id, call.from_user.first_name)
    await call.answer()

@dp.message(AdminStates.waiting_for_broadcast_msg, F.from_user.id == ADMIN_ID)
async def do_broadcast(message: types.Message, state: FSMContext):
    broadcast_text = message.text
    await state.clear()
    
    cursor.execute("SELECT user_id, first_name FROM users")
    all_users = cursor.fetchall()
    
    status_msg = await message.reply("⏳ လူအားလုံးဆီ လင့်ခ်/စာသားများ စတင်ပို့ဆောင်နေပါပြီ...")
    success, fail = 0, 0
    
    for user in all_users:
        u_id, f_name = user[0], user[1]
        if u_id == ADMIN_ID: continue
        try:
            count = get_user_count(u_id)
            bot_user = await bot.get_me()
            bot_link = f"https://t.me/{bot_user.username}?start=ref_{u_id}"
            share_url = f"https://t.me/share/url?url={urllib.parse.quote(bot_link)}&text={urllib.parse.quote('VIP Group ဝင်ရန် ဒီလင့်ခ်ကိုနှိပ်ပါ')}"

            builder = InlineKeyboardBuilder()
            builder.row(InlineKeyboardButton(text="VIP Group ဝင်ရန်", url=GROUP_REQUEST_LINK))
            builder.row(InlineKeyboardButton(text="သူငယ်ချင်းထံ ရှဲပေးရန်", url=share_url))
            builder.row(InlineKeyboardButton(text="အခြေအနေ စစ်ဆေးရန်", callback_data="check"))
            
            full_text = f"{broadcast_text}\n\n-----------\nလက်ရှိဖိတ်ခေါ်ပြီးသူ: {count} / {REQUIRED_SHARES}"
            await bot.send_message(chat_id=u_id, text=full_text, reply_markup=builder.as_markup())
            success += 1
            await asyncio.sleep(0.05)
        except Exception:
            fail += 1
            
    await status_msg.edit_text(f"📢 Broadcast ပို့ဆောင်မှု ပြီးဆုံးပါပြီ။\n\nအောင်မြင်: {success}\nကျရှုံး: {fail}")

# --- USER CALLBACKS ---
@dp.callback_query(F.data == "check")
async def check_status(call: types.CallbackQuery):
    count = get_user_count(call.from_user.id)
    await call.answer(f"သင်ဖိတ်ခေါ်ထားသူ: {count} ယောက်", show_alert=True)

@dp.chat_join_request()
async def join_req(update: types.ChatJoinRequest):
    uid = update.from_user.id
    cursor.execute("UPDATE users SET has_requested = 1 WHERE user_id=?", (uid,))
    conn.commit()
    
    count = get_user_count(uid)
    if count >= REQUIRED_SHARES:
        await bot.approve_chat_join_request(chat_id=GROUP_ID, user_id=uid)
    else:
        await bot.send_message(uid, "VIP Group ဝင်ရန်အတွက် လူ (၁) ယောက် ဖိတ်ခေါ်ပေးရန် လိုအပ်ပါသည်။")

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
