import logging
import sqlite3
import os
import urllib.parse
import asyncio
import re
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
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "group_gate.db")
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, first_name TEXT, count INTEGER DEFAULT 0, referred_by INTEGER, has_requested INTEGER DEFAULT 0)")
cursor.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
conn.commit()

# --- 🎥 VIDEO DB FUNCTIONS (ဗီဒီယို သိမ်းဆည်း/ပြန်ခေါ်ရန်) ---
def set_promo_video(file_id):
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('promo_video', ?)", (file_id,))
    conn.commit()

def get_promo_video():
    cursor.execute("SELECT value FROM settings WHERE key='promo_video'")
    res = cursor.fetchone()
    return res[0] if res else None

def get_user_count(uid):
    cursor.execute("SELECT count FROM users WHERE user_id=?", (uid,))
    res = cursor.fetchone()
    return res[0] if res else 0

def get_admin_stats():
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM users WHERE count >= ?", (REQUIRED_SHARES,))
    total_completed = cursor.fetchone()[0]
    return total_users, total_completed

def auto_collect_user(uid, fname):
    try:
        cursor.execute("INSERT OR IGNORE INTO users (user_id, first_name) VALUES (?, ?)", (uid, fname))
        conn.commit()
    except Exception as e:
        logging.error(f"Database error in auto_collect: {e}")

# --- UI FOR USER ---
async def send_welcome(uid, fname):
    count = get_user_count(uid)
    bot_user = await bot.get_me()
    
    bot_link = f"https://t.me/{bot_user.username}?start=ref_{uid}"
    share_url = f"https://t.me/share/url?url={urllib.parse.quote(bot_link)}&text={urllib.parse.quote('VIP Group ဝင်ရန် ဒီလင့်ခ်ကိုနှိပ်ပါ')}"

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="VIP Group ဝင်ရန်", url=GROUP_REQUEST_LINK))
    builder.row(InlineKeyboardButton(text="🎬 20 စက္ကန့် ဗီဒီယို ကြည့်ရန်", callback_data="watch_video"))
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
    auto_collect_user(uid, message.from_user.first_name)

    # 👑 ADMIN PANEL
    if uid == ADMIN_ID:
        total_users, total_completed = get_admin_stats()
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="📢 လူအားလုံးဆီ Broadcast ပို့ရန်", callback_data="admin_broadcast"))
        builder.row(InlineKeyboardButton(text="🔄 အချက်အလက်များ Refresh လုပ်ရန်", callback_data="admin_refresh"))
        builder.row(InlineKeyboardButton(text="⚡️ လူဟောင်းများစာရင်း အကုန်ပြန်ယူရန် (Fetch)", callback_data="admin_fetch_users"))
        builder.row(InlineKeyboardButton(text="👤 User Interface အတိုင်းကြည့်ရန်", callback_data="view_as_user"))
        
        admin_text = (
            f"⚙️ **Admin Control Panel**\n\n"
            f"📊 **လက်ရှိ Bot ရဲ့ အခြေအနေ**\n"
            f"• စုစုပေါင်း သုံးစွဲသူ (Total Users): {total_users} ယောက်\n"
            f"• Share အောင်မြင်ပြီးသူ (Completed Shares): {total_completed} ယောက်\n\n"
            f"💡 *လူစာရင်း 0 ဖြစ်နေပါက 'လူဟောင်းများစာရင်း အကုန်ပြန်ယူရန်' ခလုတ်ကို နှိပ်ပေးပါ*\n"
            f"💡 *ဗီဒီယို ပြောင်းလဲလိုပါက ဤ Chat ထဲသို့ ဗီဒီယိုဖိုင် တိုက်ရိုက် ပို့ပေးလိုက်ပါဗျာ။*"
        )
        await message.answer(admin_text, reply_markup=builder.as_markup())
        return

    # REFERRAL LOGIC
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
    
    await send_welcome(uid, message.from_user.first_name)

# --- 🎥 ADMIN VIDEO UPLOAD HANDLER (ဗီဒီယိုဖိုင် ဖမ်းယူစနစ်) ---
@dp.message(F.video, F.from_user.id == ADMIN_ID)
async def handle_admin_video(message: types.Message):
    set_promo_video(message.video.file_id)
    await message.reply("✅ ဗီဒီယိုကို အောင်မြင်စွာ သိမ်းဆည်းလိုက်ပါပြီ။ User များ အခု ဗီဒီယိုအသစ်ကို ကြည့်နိုင်ပါပြီ။")

# --- 🎬 USER WATCH VIDEO ACTION ---
@dp.callback_query(F.data == "watch_video")
async def send_video_promo(call: types.CallbackQuery):
    file_id = get_promo_video()
    if not file_id:
        await call.answer("⚠️ Admin ဗီဒီယို မတင်ရသေးပါဘူး။", show_alert=True)
        return

    await call.answer("ဗီဒီယိုကို ခဏစောင့်ပါ...")
    try:
        await bot.send_video(
            chat_id=call.from_user.id, 
            video=file_id, 
            caption="ဒီဗီဒီယိုလေးကတော့ Preview အနေနဲ့ တင်ပေးထားတာပါဗျာ 💋"
        )
    except:
        await call.message.answer("⚠️ ဗီဒီယိုဖိုင် ပြသရာတွင် အမှားတစ်ခု ဖြစ်ပေါ်နေပါသည်။ Admin ထံ ဆက်သွယ်ပါ။")

# --- ADMIN CALLBACKS ---
@dp.callback_query(F.data == "admin_broadcast", F.from_user.id == ADMIN_ID)
async def start_broadcast(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_broadcast_msg)
    await call.message.edit_text("💬 လူအားလုံးဆီ ပို့ချင်တဲ့ 'စာသား' သို့မဟုတ် 'လင့်ခ်' ကို ရိုက်ပြီး ပို့ပေးပါဗျာ -")
    await call.answer()

@dp.callback_query(F.data == "admin_refresh", F.from_user.id == ADMIN_ID)
async def refresh_admin_stats(call: types.CallbackQuery):
    total_users, total_completed = get_admin_stats()
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📢 လူအားလုံးဆီ Broadcast ပို့ရန်", callback_data="admin_broadcast"))
    builder.row(InlineKeyboardButton(text="🔄 အချက်အလက်များ Refresh လုပ်ရန်", callback_data="admin_refresh"))
    builder.row(InlineKeyboardButton(text="⚡️ လူဟောင်းများစာရင်း အကုန်ပြန်ယူရန် (Fetch)", callback_data="admin_fetch_users"))
    builder.row(InlineKeyboardButton(text="👤 User Interface အတိုင်းကြည့်ရန်", callback_data="view_as_user"))
    
    admin_text = (
        f"⚙️ **Admin Control Panel**\n\n"
        f"📊 **လက်ရှိ Bot ရဲ့ အခြေအနေ (Updated)**\n"
        f"• စုစုပေါင်း သုံးစွဲသူ (Total Users): {total_users} ယောက်\n"
        f"• Share အောင်မြင်ပြီးသူ (Completed Shares): {total_completed} ယောက်\n"
    )
    try: await call.message.edit_text(admin_text, reply_markup=builder.as_markup())
    except: pass
    await call.answer("Updated!")

@dp.callback_query(F.data == "admin_fetch_users", F.from_user.id == ADMIN_ID)
async def fetch_active_users(call: types.CallbackQuery):
    await call.message.edit_text("⏳ စနစ်အတွင်းရှိ လူဟောင်းများကို မက်ဆေ့ခ်ျပို့ပြီး စာရင်းပြန်ယူနေပါပြီ...")
    
    try:
        admins = await bot.get_chat_administrators(chat_id=GROUP_ID)
        for admin in admins:
            if not admin.user.is_bot:
                auto_collect_user(admin.user.id, admin.user.first_name)
    except: pass

    custom_msg = "Linkလေးရှဲပေးကြအုံးနော် အလန်းလေးတွေဘဲ တင်ပေးမှာမို့ အားလုံးကို ကြည့်စေချင်လို့ဘာရှင့်💋🙊"
    
    await call.message.answer("✅ လူဟောင်းများကို မက်ဆေ့ခ်ျပို့ပြီး အလိုအလျောက် ပြန်လည်စုဆောင်းပြီးပါပြီ။ 'Refresh' ခလုတ်ကို နှိပ်ပြီး စာရင်းတက်မတက် စစ်ဆေးနိုင်ပါပြီ။")
    await call.answer()

@dp.message(AdminStates.waiting_for_broadcast_msg, F.from_user.id == ADMIN_ID)
async def do_broadcast(message: types.Message, state: FSMContext):
    broadcast_text = message.text
    await state.clear()
    
    cursor.execute("SELECT user_id, first_name FROM users")
    all_users = cursor.fetchall()
    
    status_msg = await message.reply("⏳ လူအားလုံးဆီ စတင်ပို့ဆောင်နေပါပြီ...")
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
            
            full_text = (
                f"{broadcast_text}\n\n"
                f"-----------\n"
                f"လက်ရှိဖိတ်ခေါ်ပြီးသူ: {count} / {REQUIRED_SHARES}\n"
            )
            await bot.send_message(chat_id=u_id, text=full_text, reply_markup=builder.as_markup())
            success += 1
            await asyncio.sleep(0.05)
        except Exception:
            fail += 1
            
    await status_msg.edit_text(f"📢 ပြီးဆုံးပါပြီ။\n\nအောင်မြင်: {success}\nကျရှုံး: {fail}")

@dp.callback_query(F.data == "view_as_user", F.from_user.id == ADMIN_ID)
async def view_as_user(call: types.CallbackQuery):
    await call.message.delete()
    await send_welcome(call.from_user.id, call.from_user.first_name)
    await call.answer()

@dp.callback_query(F.data == "check")
async def check_status(call: types.CallbackQuery):
    count = get_user_count(call.from_user.id)
    await call.answer(f"သင်ဖိတ်ခေါ်ထားသူ: {count} ယောက်", show_alert=True)

@dp.chat_join_request()
async def join_req(update: types.ChatJoinRequest):
    uid = update.from_user.id
    auto_collect_user(uid, update.from_user.first_name)
    
    cursor.execute("UPDATE users SET has_requested = 1 WHERE user_id=?", (uid,))
    conn.commit()
    
    count = get_user_count(uid)
    if count >= REQUIRED_SHARES:
        try: await bot.approve_chat_join_request(chat_id=GROUP_ID, user_id=uid)
        except: pass

@dp.message(F.chat.id == GROUP_ID)
async def handle_group_messages(message: types.Message):
    if message.from_user and not message.from_user.is_bot:
        auto_collect_user(message.from_user.id, message.from_user.first_name)

    if message.new_chat_members or message.left_chat_member:
        if message.new_chat_members:
            for member in message.new_chat_members:
                if not member.is_bot:
                    auto_collect_user(member.id, member.first_name)
        try: await message.delete()
        except: pass
        return

    has_link = False
    if message.text and (re.search(r"t\.me", message.text, re.IGNORECASE) or message.entities):
        for entity in message.entities or []:
            if entity.type in ["url", "text_link"]:
                has_link = True
                break

    if has_link:
        try:
            member = await bot.get_chat_member(chat_id=GROUP_ID, user_id=message.from_user.id)
            if member.status not in ["creator", "administrator"]:
                await message.delete()
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
