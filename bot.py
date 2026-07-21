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
MAIN_GROUP_ID = -1003913717685             
REQUIRED_SHARES = 1                   
GROUP_REQUEST_LINK = "https://t.me/+LFpe_NpuiO1mOTA1"
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
    waiting_for_group_broadcast_msg = State()

# --- DATABASE ---
DATA_DIR = os.getenv("DATA_DIR", "/app/data")
os.makedirs(DATA_DIR, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "group_gate.db")

conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, first_name TEXT, count INTEGER DEFAULT 0, referred_by INTEGER, has_requested INTEGER DEFAULT 0)")
cursor.execute("CREATE TABLE IF NOT EXISTS groups (group_id INTEGER PRIMARY KEY, group_title TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
conn.commit()

# --- DB FUNCTIONS ---
def save_group(group_id, title):
    try:
        cursor.execute("INSERT OR REPLACE INTO groups (group_id, group_title) VALUES (?, ?)", (group_id, title))
        conn.commit()
    except Exception as e:
        logging.error(f"Group DB Error: {e}")

def get_promo_video():
    cursor.execute("SELECT value FROM settings WHERE key='promo_video'")
    res = cursor.fetchone()
    return res[0] if res else None

def set_promo_video(file_id):
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('promo_video', ?)", (file_id,))
    conn.commit()

def get_user_count(uid):
    cursor.execute("SELECT count FROM users WHERE user_id=?", (uid,))
    res = cursor.fetchone()
    return res[0] if res else 0

def get_admin_stats():
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM users WHERE count >= ?", (REQUIRED_SHARES,))
    total_completed = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM groups")
    total_groups = cursor.fetchone()[0]
    return total_users, total_completed, total_groups

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
    
    # Bot ကို မိမိ Group ထဲ ထည့်ရန် Link
    add_to_group_url = f"https://t.me/{bot_user.username}?startgroup=true"

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="VIP Group ဝင်ရန်", url=GROUP_REQUEST_LINK))
    builder.row(InlineKeyboardButton(text="🎬 20 စက္ကန့် ဗီဒီယို ကြည့်ရန်", callback_data="watch_video"))
    builder.row(InlineKeyboardButton(text="➕ Bot ကို မိမိ Group ထဲထည့်ရန်", url=add_to_group_url))
    builder.row(InlineKeyboardButton(text="သူငယ်ချင်းထံ ရှဲပေးရန်", url=share_url))
    builder.row(InlineKeyboardButton(text="အခြေအနေ စစ်ဆေးရန်", callback_data="check"))
    
    # 📝 Group ထဲမှာ Bot ဘာလုပ်ပေးနိုင်လဲဆိုသည့် စာသားပါ ထည့်သွင်းထားသည်
    text = (
        f"မင်္ဂလာပါ {fname}\n\n"
        f"VIP Group ဝင်ရောက်ရန် အောက်ပါအတိုင်း လုပ်ဆောင်ပါ။\n\n"
        f"၁။ VIP Group ဝင်ရန် (နှိပ်ပါ)\n"
        f"၂။ သူငယ်ချင်းတစ်ယောက်ကို ဖိတ်ခေါ်ပေးပါ\n\n"
        f"လက်ရှိဖိတ်ခေါ်ပြီးသူ: {count} / {REQUIRED_SHARES}\n"
        f"⚡️ [သူငယ်ချင်း ၁ ယောက် ဝင်လာတာနဲ့ VIP Group ထဲ အလိုအလျောက် တန်းထည့်ပေးမှာ ဖြစ်ပါတယ်။]\n\n"
        f"----------------------------------\n"
        f"🤖 **Bot ကို မိမိ Group ထဲ ထည့်သွင်းပါက ရရှိမည့် အကျိုးကျေးဇူးများ:**\n\n"
        f"🛡️ **Anti-Link စနစ်:** Group ထဲသို့ မလိုအပ်သော Spam Link / Telegram Link များ တင်ပါက အလိုအလျောက် ရှာဖွေ ဖျက်ဆီးပေးပါသည်။\n"
        f"🧹 **Clean-Up စနစ်:** Member အသစ်ဝင်/ထွက် Noti စာကြောင်းများနှင့် မလိုအပ်သော Notification များကို သန့်ရှင်းပေးပါသည်။\n"
        f"👑 **Admin Security:** Group Owner နှင့် Admin များ၏ Link များကိုမူ ဖျက်မည်မဟုတ်ဘဲ ကင်းလွတ်ခွင့် ပေးထားပါသည်။\n\n"
        f"👉 မိမိ Group ထဲသို့ Bot ကို ထည့်သွင်းရန် အောက်ပါ **'➕ Bot ကို မိမိ Group ထဲထည့်ရန်'** ခလုတ်ကို နှိပ်ပါဗျာ။"
    )
    await bot.send_message(chat_id=uid, text=text, reply_markup=builder.as_markup())

# --- COMMAND START ---
@dp.message(Command("start"))
async def start(message: types.Message):
    if message.chat.type != "private":
        return

    uid = message.from_user.id
    auto_collect_user(uid, message.from_user.first_name)

    # 👑 ADMIN PANEL
    if uid == ADMIN_ID:
        total_users, total_completed, total_groups = get_admin_stats()
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="📢 User အားလုံးဆီ Broadcast ပို့ရန်", callback_data="admin_broadcast"))
        builder.row(InlineKeyboardButton(text="📢 Group အားလုံးဆီ ကြော်ငြာ စာပို့ရန်", callback_data="admin_group_broadcast"))
        builder.row(InlineKeyboardButton(text="🔄 အချက်အလက်များ Refresh လုပ်ရန်", callback_data="admin_refresh"))
        builder.row(InlineKeyboardButton(text="⚡️ လူဟောင်းများစာရင်း အကုန်ပြန်ယူရန်", callback_data="admin_fetch_users"))
        builder.row(InlineKeyboardButton(text="👤 User Interface အတိုင်းကြည့်ရန်", callback_data="view_as_user"))
        
        admin_text = (
            f"⚙️ **Admin Control Panel**\n\n"
            f"📊 **လက်ရှိ Bot ရဲ့ အခြေအနေ**\n"
            f"• စုစုပေါင်း သုံးစွဲသူ (Total Users): {total_users} ယောက်\n"
            f"• Share အောင်မြင်ပြီးသူ: {total_completed} ယောက်\n"
            f"• Bot ရောက်ရှိနေသော Group ပမာဏ: {total_groups} ခု\n"
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
                    try: await bot.approve_chat_join_request(chat_id=MAIN_GROUP_ID, user_id=referrer)
                    except: pass
    
    await send_welcome(uid, message.from_user.first_name)

# --- BROADCAST TO USER SYSTEM ---
@dp.callback_query(F.data == "admin_broadcast", F.from_user.id == ADMIN_ID)
async def start_broadcast(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_broadcast_msg)
    await call.message.edit_text("💬 User အားလုံးဆီ ပို့ချင်တဲ့ 'စာသား' သို့မဟုတ် 'လင့်ခ်' ကို ရိုက်ပြီး ပို့ပေးပါဗျာ -")
    await call.answer()

@dp.message(AdminStates.waiting_for_broadcast_msg, F.from_user.id == ADMIN_ID)
async def do_broadcast(message: types.Message, state: FSMContext):
    broadcast_text = message.text
    await state.clear()
    
    cursor.execute("SELECT user_id, first_name FROM users")
    all_users = cursor.fetchall()
    
    total_to_send = len(all_users)
    status_msg = await message.reply(f"⏳ စုစုပေါင်း User ({total_to_send}) ယောက်ဆီ Broadcast စတင်ပို့ဆောင်နေပါပြီ...")
    success, fail = 0, 0
    
    for index, user in enumerate(all_users, start=1):
        u_id, f_name = user[0], user[1]
        if u_id == ADMIN_ID: continue
            
        try:
            count = get_user_count(u_id)
            bot_user = await bot.get_me()
            bot_link = f"https://t.me/{bot_user.username}?start=ref_{u_id}"
            share_url = f"https://t.me/share/url?url={urllib.parse.quote(bot_link)}&text={urllib.parse.quote('VIP Group ဝင်ရန် ဒီလင့်ခ်ကိုနှိပ်ပါ')}"
            add_to_group_url = f"https://t.me/{bot_user.username}?startgroup=true"

            builder = InlineKeyboardBuilder()
            builder.row(InlineKeyboardButton(text="VIP Group ဝင်ရန်", url=GROUP_REQUEST_LINK))
            builder.row(InlineKeyboardButton(text="➕ Bot ကို မိမိ Group ထဲထည့်ရန်", url=add_to_group_url))
            builder.row(InlineKeyboardButton(text="သူငယ်ချင်းထံ ရှဲပေးရန်", url=share_url))
            builder.row(InlineKeyboardButton(text="အခြေအနေ စစ်ဆေးရန်", callback_data="check"))
            
            full_text = f"{broadcast_text}\n\n-----------\nလက်ရှိဖိတ်ခေါ်ပြီးသူ: {count} / {REQUIRED_SHARES}\n"
            await bot.send_message(chat_id=u_id, text=full_text, reply_markup=builder.as_markup())
            success += 1
            await asyncio.sleep(0.04)
        except:
            fail += 1

    await status_msg.edit_text(f"📢 **User Broadcast ပြီးစီးပါပြီ!**\n\n✅ အောင်မြင်: {success}\n❌ ကျရှုံး: {fail}")

# --- BROADCAST TO ALL GROUPS ---
@dp.callback_query(F.data == "admin_group_broadcast", F.from_user.id == ADMIN_ID)
async def start_group_broadcast(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_group_broadcast_msg)
    await call.message.edit_text("💬 Group အားလုံးဆီ တင်ချင်သည့် ကြော်ငြာစာ သို့မဟုတ် လင့်ခ်ကို ရိုက်ပြီး ပို့ပေးပါဗျာ -")
    await call.answer()

@dp.message(AdminStates.waiting_for_group_broadcast_msg, F.from_user.id == ADMIN_ID)
async def do_group_broadcast(message: types.Message, state: FSMContext):
    broadcast_text = message.text
    await state.clear()

    cursor.execute("SELECT group_id FROM groups")
    all_groups = cursor.fetchall()
    
    success, fail = 0, 0
    status_msg = await message.reply(f"⏳ စုစုပေါင်း Group ({len(all_groups)}) ခုဆီ ကြော်ငြာ ပို့ဆောင်နေပါပြီ...")

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="VIP Group ဝင်ရန်", url=GROUP_REQUEST_LINK))

    for g_id in all_groups:
        try:
            await bot.send_message(chat_id=g_id[0], text=broadcast_text, reply_markup=builder.as_markup())
            success += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            logging.error(f"Failed group broadcast to {g_id[0]}: {e}")
            fail += 1

    await status_msg.edit_text(
        f"📢 **Group ကြော်ငြာ ပို့ဆောင်မှု ပြီးစီးပါပြီ!**\n\n"
        f"✅ အောင်မြင်သည့် Group: {success} ခု\n"
        f"❌ မရောက်သည့် Group: {fail} ခု"
    )

# --- OTHER CALLBACKS & HANDLERS ---
@dp.callback_query(F.data == "admin_refresh", F.from_user.id == ADMIN_ID)
async def refresh_admin_stats(call: types.CallbackQuery):
    total_users, total_completed, total_groups = get_admin_stats()
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📢 User အားလုံးဆီ Broadcast ပို့ရန်", callback_data="admin_broadcast"))
    builder.row(InlineKeyboardButton(text="📢 Group အားလုံးဆီ ကြော်ငြာ စာပို့ရန်", callback_data="admin_group_broadcast"))
    builder.row(InlineKeyboardButton(text="🔄 အချက်အလက်များ Refresh လုပ်ရန်", callback_data="admin_refresh"))
    builder.row(InlineKeyboardButton(text="⚡️ လူဟောင်းများစာရင်း အကုန်ပြန်ယူရန်", callback_data="admin_fetch_users"))
    builder.row(InlineKeyboardButton(text="👤 User Interface အတိုင်းကြည့်ရန်", callback_data="view_as_user"))
    
    admin_text = (
        f"⚙️ **Admin Control Panel**\n\n"
        f"📊 **လက်ရှိ Bot ရဲ့ အခြေအနေ (Updated)**\n"
        f"• စုစုပေါင်း သုံးစွဲသူ (Total Users): {total_users} ယောက်\n"
        f"• Share အောင်မြင်ပြီးသူ: {total_completed} ယောက်\n"
        f"• Bot ရောက်ရှိနေသော Group ပမာဏ: {total_groups} ခု\n"
    )
    try: await call.message.edit_text(admin_text, reply_markup=builder.as_markup())
    except: pass
    await call.answer("Updated!")

@dp.callback_query(F.data == "watch_video")
async def send_video_promo(call: types.CallbackQuery):
    file_id = get_promo_video()
    if not file_id:
        await call.answer("⚠️ Admin ဗီဒီယို မတင်ရသေးပါဘူး။", show_alert=True)
        return
    await call.answer("ဗီဒီယိုကို ခဏစောင့်ပါ...")
    try:
        await bot.send_video(chat_id=call.from_user.id, video=file_id, caption="ဒီဗီဒီယိုလေးကတော့ Preview အနေနဲ့ တင်ပေးထားတာပါဗျာ 💋")
    except:
        await call.message.answer("⚠️ ဗီဒီယိုဖိုင် ပြသရာတွင် အမှားတစ်ခု ဖြစ်ပေါ်နေပါသည်။")

@dp.callback_query(F.data == "view_as_user", F.from_user.id == ADMIN_ID)
async def view_as_user(call: types.CallbackQuery):
    await call.message.delete()
    await send_welcome(call.from_user.id, call.from_user.first_name)
    await call.answer()

@dp.callback_query(F.data == "check")
async def check_status(call: types.CallbackQuery):
    count = get_user_count(call.from_user.id)
    await call.answer(f"သင်ဖိတ်ခေါ်ထားသူ: {count} ယောက်", show_alert=True)

@dp.message(F.video, F.from_user.id == ADMIN_ID)
async def handle_admin_video(message: types.Message):
    set_promo_video(message.video.file_id)
    await message.reply("✅ ဗီဒီယိုကို အောင်မြင်စွာ သိမ်းဆည်းလိုက်ပါပြီ။")

@dp.chat_join_request()
async def join_req(update: types.ChatJoinRequest):
    uid = update.from_user.id
    auto_collect_user(uid, update.from_user.first_name)
    cursor.execute("UPDATE users SET has_requested = 1 WHERE user_id=?", (uid,))
    conn.commit()
    try: await send_welcome(uid, update.from_user.first_name)
    except: pass
    
    count = get_user_count(uid)
    if count >= REQUIRED_SHARES:
        try: await bot.approve_chat_join_request(chat_id=MAIN_GROUP_ID, user_id=uid)
        except: pass

@dp.my_chat_member()
async def bot_added_to_group(event: types.ChatMemberUpdated):
    if event.new_chat_member.status in ["member", "administrator"]:
        save_group(event.chat.id, event.chat.title)
        if event.new_chat_member.status == "member":
            try:
                await bot.send_message(
                    chat_id=event.chat.id,
                    text="⚠️ **သတိပြုရန်:** Bot ကို ပုံမှန်အတိုင်း အပြည့်အဝ အလုပ်လုပ်စေချင်ပါက Admin Right ပေးထားပါရန် လိုအပ်ပါသည်။"
                )
            except: pass

@dp.message(F.chat.type.in_({"group", "supergroup"}))
async def handle_group_messages(message: types.Message):
    save_group(message.chat.id, message.chat.title)
    if message.from_user and not message.from_user.is_bot:
        auto_collect_user(message.from_user.id, message.from_user.first_name)

    # Notification များ ဖျက်ခြင်း
    is_notification = any([
        message.new_chat_members, message.left_chat_member, message.pinned_message,
        message.new_chat_title, message.new_chat_photo, message.delete_chat_photo,
        message.group_chat_created, message.supergroup_chat_created,
        message.video_chat_started, message.video_chat_ended
    ])

    if is_notification:
        try: await message.delete()
        except: pass
        return

    # Main Group အတွက် Anti-Link စနစ်
    if message.chat.id == MAIN_GROUP_ID:
        has_link = False
        content_to_check = message.text or message.caption or ""
        if re.search(r"(https?://|t\.me|telegram\.me|www\.)", content_to_check, re.IGNORECASE):
            has_link = True
        elif message.entities or message.caption_entities:
            entities = message.entities or message.caption_entities
            for entity in entities:
                if entity.type in ["url", "text_link"]:
                    has_link = True
                    break

        if has_link:
            try:
                member = await bot.get_chat_member(chat_id=MAIN_GROUP_ID, user_id=message.from_user.id)
                if member.status not in ["creator", "administrator"]:
                    await message.delete()
            except Exception as e:
                logging.error(f"Failed to delete link: {e}")

# --- WEBHOOK & STARTUP ---
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
