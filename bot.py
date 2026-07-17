import logging
import sqlite3
import os
import re
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiohttp import web
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

# --- CONFIGURATION (ပြင်ဆင်ရန်) ---
BOT_TOKEN = "8463292751:AAFcS2jd50RPs79yrFdYcJvtvw5DMhAkDX8"      
GROUP_ID = -1003913717685             
REQUIRED_SHARES = 5                   
GROUP_REQUEST_LINK = "https://t.me/+LFpe_NpuiO1mOTA1"

# ပြသမည့် Content (ဒီနေရာမှာ မင်းပြချင်တဲ့ ဗီဒီယို သို့မဟုတ် ပုံရဲ့ Telegram File ID သို့မဟုတ် Direct Link ကို ထည့်ပါ)
# လက်ရှိတွင် နမူနာစာသားဖြင့် ပြထားပါသည်
LOCKED_CONTENT_TEXT = "🔥 VIP Group ထဲမှာ အခုလိုမျိုး လုံးဝ အလန်းစား ဗီဒီယိုတွေနဲ့ ပုံတွေ အများကြီး အပြည့်အစုံ ရှိနေပါပြီဗျာ!"

WEBHOOK_HOST = "https://Myaibot-production.up.railway.app"
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
WEB_SERVER_HOST = "0.0.0.0"
WEB_SERVER_PORT = int(os.getenv("PORT", 8080))
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
conn.commit()

def get_user_count(uid):
    cursor.execute("SELECT count FROM users WHERE user_id=?", (uid,))
    res = cursor.fetchone()
    return res[0] if res else 0

# --- AUTO-DELETE (ဝင်စာ/ထွက်စာ/လင့်ခ် ဖျက်မည့်အပိုင်း) ---

@dp.message(F.chat.id == GROUP_ID, F.new_chat_members | F.left_chat_member)
async def delete_join_left_message(message: types.Message):
    try:
        await message.delete()
    except Exception:
        pass

@dp.message(F.chat.id == GROUP_ID)
async def delete_links(message: types.Message):
    has_link = False
    if message.text and (re.search(r"t\.me", message.text, re.IGNORECASE) or message.entities):
        for entity in message.entities or []:
            if entity.type in ["url", "text_link"]:
                has_link = True
                break
                
    if message.caption and (re.search(r"t\.me", message.caption, re.IGNORECASE) or message.caption_entities):
        for entity in message.caption_entities or []:
            if entity.type in ["url", "text_link"]:
                has_link = True
                break

    if has_link:
        try:
            member = await bot.get_chat_member(chat_id=GROUP_ID, user_id=message.from_user.id)
            if member.status in ["creator", "administrator"]:
                return  
            await message.delete()
        except Exception:
            pass

# --- BOT HANDLERS ---

@dp.message(Command("start"))
async def start_command(message: types.Message):
    if message.chat.type != "private":
        return
        
    uid = message.from_user.id
    uname = message.from_user.username or "No Username"
    fname = message.from_user.first_name or "User"
    args = message.text.split()
    
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
                            await bot.send_message(referrer_id, "🎉 အောင်မြင်ပါပြီ! လူ ၅ ယောက် တကယ်ဝင်လာခဲ့လို့ သင့်ကို Group ထဲ auto သွတ်သွင်းပေးလိုက်ပါပြီ။")
                        else:
                            await bot.send_message(referrer_id, f"➕ လူသစ်တစ်ယောက် တိုးလာပါပြီ။ လက်ရှိအခြေအနေ: [{current_points}/{REQUIRED_SHARES}] ယောက် ရှိပါပြီ။")
                    except Exception:
                        pass
            except ValueError:
                pass
        
        cursor.execute("INSERT INTO users (user_id, count, referred_by, username, first_name) VALUES (?, 0, ?, ?, ?)", (uid, referrer_id, uname, fname))
        conn.commit()
    else:
        # ရှိပြီးသားလူဆိုလျှင်လည်း အချက်အလက် Update လုပ်ရန်
        cursor.execute("UPDATE users SET username=?, first_name=? WHERE user_id=?", (uname, fname, uid))
        conn.commit()

    bot_user = await bot.get_me()
    share_url = f"https://t.me/share/url?url=https://t.me/{bot_user.username}?start=ref_{uid}&text=ညစာ 1.0 VIP Group ဝင်ချင်ရင် ဒီလင့်ခ်ကနေ ဝင်ပါဦး။"
    count = get_user_count(uid)

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔓 ၁။ VIP Group ဝင်ခွင့်တောင်းရန်", url=GROUP_REQUEST_LINK))
    builder.row(InlineKeyboardButton(text="📢 ၂။ အခြား Group များသို့ ရှဲရန်", url=share_url))
    builder.row(InlineKeyboardButton(text="🏆 Top 10 Leaderboard ကိုကြည့်ရန်", callback_data="show_leaderboard"))
    
    await message.answer(
        f"👋 မင်္ဂလာပါ {fname} ဗျာ။\n\n"
        f"🎬 **Preview Content:**\n{LOCKED_CONTENT_TEXT}\n\n"
        f"⚠️ **စည်းကမ်းချက်:** ဤအရာ၏ အပြည့်အစုံနှင့် VIP Group ထဲသို့ ဝင်ရောက်နိုင်ရန် အောက်ပါအတိုင်း လုပ်ဆောင်ပေးရပါမည် -\n"
        f"၁။ **'၁။ VIP Group ဝင်ခွင့်တောင်းရန်'** ကိုနှိပ်ပြီး ဝင်ခွင့်တောင်းထားပါ။\n"
        f"၂။ **'၂။ အခြား Group များသို့ ရှဲရန်'** ကိုနှိပ်ပြီး လူ (၅) ယောက်ခေါ်ပေးပါ။\n\n"
        f"📊 လက်ရှိ သင့်လင့်ခ်မှ ဝင်လာသူ: [{count}/{REQUIRED_SHARES}] ယောက်။\n"
        f"🏆 အောက်က Leaderboard ခလုတ်ကိုနှိပ်ပြီး လူအများဆုံးခေါ်ထားတဲ့သူတွေကိုလည်း ကြည့်နိုင်ပါတယ်ဗျာ။",
        reply_markup=builder.as_markup()
    )

# Leaderboard ခလုတ်နှိပ်လျှင် ထိပ်ဆုံး ၁၀ ယောက်စာရင်းပြပေးမည့်အပိုင်း
@dp.callback_query(F.data == "show_leaderboard")
async def leaderboard_callback(callback: types.CallbackQuery):
    cursor.execute("SELECT first_name, count FROM users WHERE count > 0 ORDER BY count DESC LIMIT 10")
    top_users = cursor.fetchall()
    
    text = "🏆 **ထိပ်ဆုံး လူအများဆုံးခေါ်နိုင်သူ ၁၀ ဦး (Top 10 Leaderboard)** 🏆\n\n"
    if not top_users:
        text += "လက်ရှိတွင် လူခေါ်ထားသူ မရှိသေးပါခင်ဗျာ။"
    else:
        for i, user in enumerate(top_users, 1):
            name = user[0] if user[0] else "User"
            text += f"{i}️⃣ {name} — {user[1]} ယောက်\n"
            
    text += "\n🔥 သင်လည်း ပထမရအောင် အမြန်ဆုံး ရှဲပြီး လူလိုက်ခေါ်လိုက်တော့နော်!"
    
    # ရှင်းလင်းသွားအောင် Message မှာ တန်းပြပေးခြင်း
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔙 နောက်သို့", callback_data="back_to_start"))
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()

@dp.callback_query(F.data == "back_to_start")
async def back_to_start_callback(callback: types.CallbackQuery):
    # မူလ Start စာမျက်နှာသို့ ပြန်သွားရန်
    uid = callback.from_user.id
    count = get_user_count(uid)
    bot_user = await bot.get_me()
    share_url = f"https://t.me/share/url?url=https://t.me/{bot_user.username}?start=ref_{uid}&text=ညစာ 1.0 VIP Group ဝင်ချင်ရင် ဒီလင့်ခ်ကနေ ဝင်ပါဦး။"
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔓 ၁။ VIP Group ဝင်ခွင့်တောင်းရန်", url=GROUP_REQUEST_LINK))
    builder.row(InlineKeyboardButton(text="📢 ၂။ အခြား Group များသို့ ရှဲရန်", url=share_url))
    builder.row(InlineKeyboardButton(text="🏆 Top 10 Leaderboard ကိုကြည့်ရန်", callback_data="show_leaderboard"))
    
    await callback.message.edit_text(
        f"👋 မင်္ဂလာပါ {callback.from_user.first_name} ဗျာ။\n\n"
        f"🎬 **Preview Content:**\n{LOCKED_CONTENT_TEXT}\n\n"
        f"📊 လက်ရှိ သင့်လင့်ခ်မှ ဝင်လာသူ: [{count}/{REQUIRED_SHARES}] ယောက်။",
        reply_markup=builder.as_markup()
    )
    await callback.answer()

@dp.chat_join_request()
async def handle_join_request(update: types.ChatJoinRequest):
    uid = update.from_user.id
    count = get_user_count(uid)
    
    if count >= REQUIRED_SHARES:
        try:
            await bot.approve_chat_join_request(chat_id=GROUP_ID, user_id=uid)
            return
        except Exception:
            pass
            
    bot_user = await bot.get_me()
    share_url = f"https://t.me/share/url?url=https://t.me/{bot_user.username}?start=ref_{uid}&text=ညစာ 1.0 VIP Group ဝင်ချင်ရင် ဒီလင့်ခ်ကနေ ဝင်ပါဦး။"
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=f"📢 Share/Forward to Groups", url=share_url))
    
    try:
        await bot.send_message(
            chat_id=uid,
            text=f"👋 မင်္ဂလာပါ {update.from_user.first_name}။\n\n"
                 f"သင် Group ဝင်ခွင့်တောင်းထားတာကို လက်ခံရရှိပါတယ်၊ ဒါပေမယ့် စည်းကမ်းချက်အတိုင်း လူ ၅ ယောက် မပြည့်သေးပါဘူးခင်ဗျာ။\n"
                 f"အောက်ကခလုတ်ကို နှိပ်ပြီး လူ (၅) ယောက်ပြည့်အောင် အရင်ဆုံး ခေါ်ပေးပါဦးနော်။\n\n"
                 f"📊 လက်ရှိ သင့်လင့်ခ်မှ ဝင်လာသူ: [{count}/{REQUIRED_SHARES}] ယောက်။",
            reply_markup=builder.as_markup()
        )
    except Exception:
        pass

# --- SERVER STARTUP ---
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
