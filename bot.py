import logging
import sqlite3
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiohttp import web
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

# --- CONFIGURATION (ပြင်ဆင်ရန်) ---
BOT_TOKEN = "8463292751:AAFcS2jd50RPs79yrFdYcJvtvw5DMhAkDX8"      # မိမိဘော့တ် တိုကင် (Token) ကို ဒီနေရာမှာ ထည့်ပါ
GROUP_ID = -1003913717685             # သင့် Group ID ကို ထည့်ပေးထားပြီးပါပြီ
REQUIRED_SHARES = 5                   # ရှဲခိုင်းမည့် အကြိမ်အရေအတွက်

# Webhook အတွက် Hosting တင်လျှင် သုံးမည့် Setting (ဥပမာ - Render.com)
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST", "https://your-app-name.onrender.com") 
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
cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, count INTEGER)")
conn.commit()

def get_user_count(uid):
    cursor.execute("SELECT count FROM users WHERE user_id=?", (uid,))
    res = cursor.fetchone()
    return res[0] if res else 0

def add_user_count(uid):
    count = get_user_count(uid) + 1
    cursor.execute("INSERT OR REPLACE INTO users (user_id, count) VALUES (?, ?)", (uid, count))
    conn.commit()
    return count

# --- BOT HANDLERS ---

# ၁။ လူတစ်ယောက်က Group ဝင်ခွင့်လင့်ခ်ကို နှိပ်လိုက်လျှင် (Join Request ပို့လျှင်) အလိုအလျောက် စစ်ဆေးမည့်အပိုင်း
@dp.chat_join_request()
async def handle_join_request(update: types.ChatJoinRequest):
    uid = update.from_user.id
    count = get_user_count(uid)
    
    bot_user = await bot.get_me()
    share_url = f"https://t.me/share/url?url=https://t.me/{bot_user.username}?start=ref_{uid}&text=ဒီထဲဝင်ကြည့်စရာတွေ အများကြီးရှိတယ်!"
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=f"📢 Share to Groups [{count}/{REQUIRED_SHARES}]", url=share_url))
    builder.row(InlineKeyboardButton(text="🔄 စစ်ဆေးမည် (Check)", callback_data="check_join"))
    
    try:
        await bot.send_message(
            chat_id=uid,
            text=f"👋 မင်္ဂလာပါ {update.from_user.first_name}။\n\n"
                 f"သင်သည် Group ထဲသို့ ဝင်ခွင့်တောင်းဆိုထားပါသည်။ အထဲက ပုံ၊ စာ၊ ဗီဒီယိုများကို ကြည့်ရှုနိုင်ရန်အတွက် "
                 f"အောက်ပါခလုတ်ကိုနှိပ်ပြီး ခြားနားသော Telegram Group (၅) ခုသို့ အရင်ဆုံး Share ပေးရပါမည်။",
            reply_markup=builder.as_markup()
        )
    except Exception:
        pass

# ၂။ ရှဲပြီးလို့ စစ်ဆေးမည် (Check) ခလုတ်နှိပ်သည့်အခါ စိစစ်ပြီး ဝင်ခွင့်ပေးမည့်အပိုင်း
@dp.callback_query(F.data == "check_join")
async def check_and_approve(callback: types.CallbackQuery):
    uid = callback.from_user.id
    new_count = add_user_count(uid)
    
    if new_count >= REQUIRED_SHARES:
        try:
            # ၅ ကြိမ်ပြည့်ပါက Group ထဲဝင်ခွင့်ကို Auto Approve (အတည်ပြု) လုပ်ပေးခြင်း
            await bot.approve_chat_join_request(chat_id=GROUP_ID, user_id=uid)
            await callback.message.edit_text("🎉 ဂုဏ်ယူပါတယ်! သင် ၅ ကြိမ်ပြည့်အောင် ရှဲပြီးပြီဖြစ်၍ Group ထဲသို့ အလိုအလျောက် သွတ်သွင်းပေးလိုက်ပါပြီ။ အခုပဲ ဝင်ရောက်ကြည့်ရှုနိုင်ပါပြီဗျာ။")
        except Exception:
            await callback.message.edit_text("❌ Error: Bot အား Group ထဲတွင် အက်ဒမင်ခန့်ပြီး 'Approve New Members' ပေးထားရန် လိုအပ်ပါသည်။")
    else:
        bot_user = await bot.get_me()
        share_url = f"https://t.me/share/url?url=https://t.me/{bot_user.username}?start=ref_{uid}"
        
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text=f"📢 Share to Groups [{new_count}/{REQUIRED_SHARES}]", url=share_url))
        builder.row(InlineKeyboardButton(text="🔄 စစ်ဆေးမည် (Check)", callback_data="check_join"))
        
        await callback.message.edit_text(
            f"⚠️ မပြည့်သေးပါခင်ဗျာ။ လက်ရှိ [{new_count}/{REQUIRED_SHARES}] ကြိမ်ပဲ ရှိပါသေးသည်။ ကျေးဇူးပြု၍ ထပ်မံ Share ပေးပါ။",
            reply_markup=builder.as_markup()
        )
    await callback.answer()

# --- SERVER STARTUP (WEBHOOK) ---
async def on_startup(bot: Bot) -> None:
    await bot.set_webhook(WEBHOOK_URL)

def main():
    dp.startup.register(on_startup)
    app = web.Application()
    
    webhook_requests_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot
    )
    webhook_requests_handler.register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)
    
    print("Auto-Approve Webhook Server စတင်ပွင့်ပါပြီ...")
    web.run_app(app, host=WEB_SERVER_HOST, port=WEB_SERVER_PORT)

if __name__ == "__main__":
    main()
