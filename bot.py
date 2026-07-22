import logging
import sqlite3
import os
import urllib.parse
import asyncio
import re
import html
from datetime import timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, ChatPermissions
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

# --- PERMANENT DATABASE LOCATION ---
DATA_DIR = os.getenv("DATA_DIR", "/data")
os.makedirs(DATA_DIR, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "group_gate.db")

OLD_DB_PATH = "group_gate.db"
if os.path.exists(OLD_DB_PATH) and not os.path.exists(DB_PATH):
    try:
        os.rename(OLD_DB_PATH, DB_PATH)
        logging.info("Moved old DB to persistent volume path.")
    except Exception as e:
        logging.error(f"Failed to move old DB: {e}")

conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, first_name TEXT, count INTEGER DEFAULT 0, referred_by INTEGER, has_requested INTEGER DEFAULT 0)")
cursor.execute("CREATE TABLE IF NOT EXISTS groups (group_id INTEGER PRIMARY KEY, group_title TEXT, invite_link TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS warnings (user_id INTEGER, group_id INTEGER, warn_count INTEGER DEFAULT 0, PRIMARY KEY(user_id, group_id))")

try:
    cursor.execute("ALTER TABLE groups ADD COLUMN invite_link TEXT")
    conn.commit()
except:
    pass
conn.commit()

# --- DB FUNCTIONS ---
async def save_group_with_link(group_id, title):
    invite_link = ""
    try:
        chat = await bot.get_chat(group_id)
        if chat.invite_link:
            invite_link = chat.invite_link
        elif chat.username:
            invite_link = f"https://t.me/{chat.username}"
        else:
            invite_link = await bot.export_chat_invite_link(group_id)
    except Exception as e:
        logging.error(f"Failed to fetch invite link for group {group_id}: {e}")

    try:
        clean_title = html.escape(title or "No Title")
        if invite_link:
            cursor.execute("INSERT OR REPLACE INTO groups (group_id, group_title, invite_link) VALUES (?, ?, ?)", (group_id, clean_title, invite_link))
        else:
            cursor.execute("INSERT INTO groups (group_id, group_title) VALUES (?, ?) ON CONFLICT(group_id) DO UPDATE SET group_title=excluded.group_title", (group_id, clean_title))
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
        clean_fname = html.escape(fname or "User")
        cursor.execute("INSERT OR IGNORE INTO users (user_id, first_name) VALUES (?, ?)", (uid, clean_fname))
        conn.commit()
    except Exception as e:
        logging.error(f"Database error in auto_collect: {e}")

# --- WARNING & MUTE LOGIC ---
def add_warning_and_check(uid, g_id):
    cursor.execute("SELECT warn_count FROM warnings WHERE user_id=? AND group_id=?", (uid, g_id))
    res = cursor.fetchone()
    if res is None:
        current_warns = 1
        cursor.execute("INSERT INTO warnings (user_id, group_id, warn_count) VALUES (?, ?, ?)", (uid, g_id, current_warns))
    else:
        current_warns = res[0] + 1
        cursor.execute("UPDATE warnings SET warn_count=? WHERE user_id=? AND group_id=?", (current_warns, uid, g_id))
    conn.commit()
    return current_warns

def reset_warnings(uid, g_id):
    cursor.execute("DELETE FROM warnings WHERE user_id=? AND group_id=?", (uid, g_id))
    conn.commit()

# --- UI FOR USER ---
async def send_welcome(uid, fname):
    count = get_user_count(uid)
    bot_user = await bot.get_me()
    
    bot_link = f"https://t.me/{bot_user.username}?start=ref_{uid}"
    share_url = f"https://t.me/share/url?url={urllib.parse.quote(bot_link)}&text={urllib.parse.quote('VIP Group ဝင်ရန် ဒီလင့်ခ်ကိုနှိပ်ပါ')}"
    add_to_group_url = f"https://t.me/{bot_user.username}?startgroup=true"

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="VIP Group ဝင်ရန်", url=GROUP_REQUEST_LINK))
    builder.row(InlineKeyboardButton(text="🎬 20 စက္ကန့် ဗီဒီယို ကြည့်ရန်", callback_data="watch_video"))
    builder.row(InlineKeyboardButton(text="➕ Bot ကို မိမိ Group ထဲထည့်ရန်", url=add_to_group_url))
    builder.row(InlineKeyboardButton(text="သူငယ်ချင်းထံ ရှဲပေးရန်", url=share_url))
    builder.row(InlineKeyboardButton(text="အခြေအနေ စစ်ဆေးရန်", callback_data="check"))
    
    clean_fname = html.escape(fname or "User")
    text = (
        f"မင်္ဂလာပါ <b>{clean_fname}</b>\n\n"
        f"VIP Group ဝင်ရောက်ရန် အောက်ပါအတိုင်း လုပ်ဆောင်ပါ။\n\n"
        f"၁။ VIP Group ဝင်ရန် (နှိပ်ပါ)\n"
        f"၂။ သူငယ်ချင်းတစ်ယောက်ကို ဖိတ်ခေါ်ပေးပါ\n\n"
        f"လက်ရှိဖိတ်ခေါ်ပြီးသူ: {count} / {REQUIRED_SHARES}\n"
        f"⚡️ [သူငယ်ချင်း ၁ ယောက် ဝင်လာတာနဲ့ VIP Group ထဲ အလိုအလျောက် တန်းထည့်ပေးမှာ ဖြစ်ပါတယ်။]\n\n"
        f"----------------------------------\n"
        f"🤖 <b>Bot ကို မိမိ Group ထဲ ထည့်သွင်းပါက ရရှိမည့် အကျိုးကျေးဇူးများ:</b>\n\n"
        f"🛡️ <b>Anti-Link စနစ်:</b> Link ပါသော စာ/Caption များကိုသာ ဖျက်ပေးပါသည်။ ၃ ကြိမ်မြောက် မိနစ် ၃၀၊ ၅ ကြိမ်မြောက် ၁ နာရီ၊ ၁၀ ကြိမ်မြောက် ရာသက်ပန် Mute ပေးပါသည်။\n"
        f"🧹 <b>Clean-Up စနစ်:</b> Member အသစ်ဝင်/ထွက် Noti စာကြောင်းများကို သန့်ရှင်းပေးပါသည်။\n"
        f"👑 <b>Admin Security:</b> Group Owner နှင့် Admin များကို ကင်းလွတ်ခွင့် ပေးထားပါသည်။\n\n"
        f"👉 မိမိ Group ထဲသို့ Bot ကို ထည့်သွင်းရန် အောက်ပါ <b>'➕ Bot ကို မိမိ Group ထဲထည့်ရန်'</b> ခလုတ်ကို နှိပ်ပါဗျာ။"
    )
    await bot.send_message(chat_id=uid, text=text, reply_markup=builder.as_markup(), parse_mode="HTML")

# --- COMMAND START ---
@dp.message(Command("start"))
async def start(message: types.Message):
    if message.chat.type != "private":
        return

    uid = message.from_user.id
    auto_collect_user(uid, message.from_user.first_name)

    if uid == ADMIN_ID:
        total_users, total_completed, total_groups = get_admin_stats()
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="📢 User အားလုံးဆီ Broadcast ပို့ရန်", callback_data="admin_broadcast"))
        builder.row(InlineKeyboardButton(text="📢 Group အားလုံးဆီ ကြော်ငြာ စာပို့ရန်", callback_data="admin_group_broadcast"))
        builder.row(InlineKeyboardButton(text="🔄 အချက်အလက်များ Refresh လုပ်ရန်", callback_data="admin_refresh"))
        builder.row(InlineKeyboardButton(text="⚡️ လူဟောင်းများစာရင်း အကုန်ပြန်ယူရန်", callback_data="admin_fetch_users"))
        builder.row(InlineKeyboardButton(text="⚡️ Group စာရင်း အကုန်ပြန်ယူရန်", callback_data="admin_fetch_groups"))
        builder.row(InlineKeyboardButton(text="👤 User Interface အတိုင်းကြည့်ရန်", callback_data="view_as_user"))
        
        admin_text = (
            f"⚙️ <b>Admin Control Panel</b>\n\n"
            f"📊 <b>လက်ရှိ Bot ရဲ့ အခြေအနေ</b>\n"
            f"• စုစုပေါင်း သုံးစွဲသူ (Total Users): {total_users} ယောက်\n"
            f"• Share အောင်မြင်ပြီးသူ: {total_completed} ယောက်\n"
            f"• Bot ရောက်ရှိနေသော Group ပမာဏ: {total_groups} ခု\n"
        )
        await message.answer(admin_text, reply_markup=builder.as_markup(), parse_mode="HTML")
        return

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

# --- ADMIN BUTTON: FETCH USERS ---
@dp.callback_query(F.data == "admin_fetch_users", F.from_user.id == ADMIN_ID)
async def fetch_old_users(call: types.CallbackQuery):
    await call.answer("User စာရင်းများ ဆွဲထုတ်နေပါသည်...", show_alert=False)
    cursor.execute("SELECT user_id, first_name, count FROM users")
    all_users = cursor.fetchall()
    
    if not all_users:
        await call.message.answer("⚠️ မည်သည့် User စာရင်းမှ မရှိသေးပါ။")
        return

    user_list_text = f"📊 စုစုပေါင်း သုံးစွဲသူစာရင်း ({len(all_users)} ယောက်)\n\n"
    for idx, u in enumerate(all_users, start=1):
        u_id, fname, count = u[0], u[1] if u[1] else "No Name", u[2]
        clean_fname = html.escape(fname)
        user_list_text += f"{idx}. Name: {clean_fname} | ID: {u_id} | Invited: {count}\n"

    if len(user_list_text) > 4000:
        file_path = "user_list.txt"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(user_list_text)
        
        doc = types.FSInputFile(file_path)
        await call.message.answer_document(doc, caption="📄 User စာရင်းအပြည့်အစုံ ဖိုင်ဖြစ်ပါတယ်။")
        os.remove(file_path)
    else:
        await call.message.answer(user_list_text, parse_mode="HTML")

# --- ADMIN BUTTON: FETCH GROUPS WITH LINKS ---
@dp.callback_query(F.data == "admin_fetch_groups", F.from_user.id == ADMIN_ID)
async def fetch_groups(call: types.CallbackQuery):
    await call.answer("Group စာရင်းများ ဆွဲထုတ်နေပါသည်...", show_alert=False)
    cursor.execute("SELECT group_id, group_title, invite_link FROM groups")
    all_groups = cursor.fetchall()
    
    if not all_groups:
        await call.message.answer("⚠️ မည်သည့် Group စာရင်းမှ မရှိသေးပါ။")
        return

    group_list_text = f"📊 စုစုပေါင်း Bot ရောက်ရှိနေသော Group စာရင်း ({len(all_groups)} ခု)\n\n"
    for idx, g in enumerate(all_groups, start=1):
        g_id, title, link = g[0], g[1] if g[1] else "No Title", g[2] if g[2] else "No Link"
        clean_title = html.escape(title)
        group_list_text += f"{idx}. Title: {clean_title}\n   ID: {g_id}\n   Link: {link}\n\n"

    if len(group_list_text) > 4000:
        file_path = "group_list.txt"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(group_list_text)
        
        doc = types.FSInputFile(file_path)
        await call.message.answer_document(doc, caption="📄 Group စာရင်းနှင့် Invite Link များ ဖိုင်ဖြစ်ပါတယ်။")
        os.remove(file_path)
    else:
        await call.message.answer(group_list_text, parse_mode="HTML", disable_web_page_preview=True)

# --- BROADCAST TO USER SYSTEM ---
@dp.callback_query(F.data == "admin_broadcast", F.from_user.id == ADMIN_ID)
async def start_broadcast(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_broadcast_msg)
    await call.message.edit_text("💬 User အားလုံးဆီ ပို့ချင်တဲ့ 'စာသား' သို့မဟုတ် 'လင့်ခ်' ကို ရိုက်ပြီး ပို့ပေးပါဗျာ -")
    await call.answer()

@dp.message(AdminStates.waiting_for_broadcast_msg, F.from_user.id == ADMIN_ID)
async def do_broadcast(message: types.Message, state: FSMContext):
    broadcast_text = html.escape(message.text or "")
    await state.clear()
    
    cursor.execute("SELECT user_id, first_name FROM users")
    all_users = cursor.fetchall()
    
    total_to_send = len(all_users)
    status_msg = await message.reply(f"⏳ စုစုပေါင်း User ({total_to_send}) ယောက်ဆီ Broadcast စတင်ပို့ဆောင်နေပါပြီ...")
    success, fail = 0, 0
    
    for user in all_users:
        u_id = user[0]
        if u_id == ADMIN_ID: continue
            
        try:
            count = get_user_count(u_id)
            bot_user = await bot.get_me()
            bot_link = f"https://t.me/{bot_user.username}?start=ref_{u_id}"
            share_url = f"https://t.me/share/url?url={urllib.parse.quote(bot_link)}&text={urllib.parse.quote('VIP Group ဝင်ရန် ဒီလင့်ခ်ကိုနှိပ်ပါ')}"
            
            builder = InlineKeyboardBuilder()
            builder.row(InlineKeyboardButton(text="VIP Group ဝင်ရန်", url=GROUP_REQUEST_LINK))
            builder.row(InlineKeyboardButton(text="သူငယ်ချင်းထံ ရှဲပေးရန်", url=share_url))
            
            text = (
                f"📢 <b>အသိပေးစာလွှာ</b>\n\n"
                f"{broadcast_text}\n\n"
                f"----------------------------------\n"
                f"လက်ရှိဖိတ်ခေါ်ပြီးသူ: {count} / {REQUIRED_SHARES}"
            )
            await bot.send_message(chat_id=u_id, text=text, reply_markup=builder.as_markup(), parse_mode="HTML")
            success += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            fail += 1
            logging.error(f"Broadcast failed for {u_id}: {e}")
            
    await status_msg.edit_text(f"✅ Broadcast ပို့ဆောင်မှု ပြီးစီးပါပြီ!\n\nအောင်မြင်: {success} ယောက်\nကျရှုံး/Blocked: {fail} ယောက်")

# --- BROADCAST TO GROUPS SYSTEM ---
@dp.callback_query(F.data == "admin_group_broadcast", F.from_user.id == ADMIN_ID)
async def start_group_broadcast(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_group_broadcast_msg)
    await call.message.edit_text("💬 Group အားလုံးဆီ ကြော်ငြာအနေနဲ့ ပို့ချင်တဲ့ 'စာသား' သို့မဟုတ် 'လင့်ခ်' ကို ရိုက်ပြီး ပို့ပေးပါဗျာ -")
    await call.answer()

@dp.message(AdminStates.waiting_for_group_broadcast_msg, F.from_user.id == ADMIN_ID)
async def do_group_broadcast(message: types.Message, state: FSMContext):
    broadcast_text = html.escape(message.text or "")
    await state.clear()
    
    cursor.execute("SELECT group_id, group_title FROM groups")
    all_groups = cursor.fetchall()
    
    total_to_send = len(all_groups)
    status_msg = await message.reply(f"⏳ စုစုပေါင်း Group ({total_to_send}) ခုဆီ ကြော်ငြာစာ စတင်ပို့ဆောင်နေပါပြီ...")
    success, fail = 0, 0
    
    for g in all_groups:
        g_id = g[0]
        try:
            bot_user = await bot.get_me()
            start_url = f"https://t.me/{bot_user.username}?start=ref_group"
            
            builder = InlineKeyboardBuilder()
            builder.row(InlineKeyboardButton(text="🤖 Bot ကို အသုံးပြုရန် / VIP Group ဝင်ရန်", url=start_url))
            
            text = (
                f"📢 <b>အသိပေးကြော်ငြာစာ</b>\n\n"
                f"{broadcast_text}"
            )
            await bot.send_message(chat_id=g_id, text=text, reply_markup=builder.as_markup(), parse_mode="HTML")
            success += 1
            await asyncio.sleep(0.1)
        except Exception as e:
            fail += 1
            logging.error(f"Group Broadcast failed for {g_id}: {e}")
            
    await status_msg.edit_text(f"✅ Group Broadcast ပို့ဆောင်မှု ပြီးစီးပါပြီ!\n\nအောင်မြင်: {success} ခု\nကျရှုံး/Kicked: {fail} ခု")

# --- ADMIN REFRESH BUTTON ---
@dp.callback_query(F.data == "admin_refresh", F.from_user.id == ADMIN_ID)
async def admin_refresh(call: types.CallbackQuery):
    total_users, total_completed, total_groups = get_admin_stats()
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📢 User အားလုံးဆီ Broadcast ပို့ရန်", callback_data="admin_broadcast"))
    builder.row(InlineKeyboardButton(text="📢 Group အားလုံးဆီ ကြော်ငြာ စာပို့ရန်", callback_data="admin_group_broadcast"))
    builder.row(InlineKeyboardButton(text="🔄 အချက်အလက်များ Refresh လုပ်ရန်", callback_data="admin_refresh"))
    builder.row(InlineKeyboardButton(text="⚡️ လူဟောင်းများစာရင်း အကုန်ပြန်ယူရန်", callback_data="admin_fetch_users"))
    builder.row(InlineKeyboardButton(text="⚡️ Group စာရင်း အကုန်ပြန်ယူရန်", callback_data="admin_fetch_groups"))
    builder.row(InlineKeyboardButton(text="👤 User Interface အတိုင်းကြည့်ရန်", callback_data="view_as_user"))
    
    admin_text = (
        f"⚙️ <b>Admin Control Panel</b>\n\n"
        f"📊 <b>လက်ရှိ Bot ရဲ့ အခြေအနေ (Refreshed)</b>\n"
        f"• စုစုပေါင်း သုံးစွဲသူ (Total Users): {total_users} ယောက်\n"
        f"• Share အောင်မြင်ပြီးသူ: {total_completed} ယောက်\n"
        f"• Bot ရောက်ရှိနေသော Group ပမာဏ: {total_groups} ခု\n"
    )
    
    try:
        await call.message.edit_text(admin_text, reply_markup=builder.as_markup(), parse_mode="HTML")
        await call.answer("အချက်အလက်များ Refresh လုပ်ပြီးပါပြီ!")
    except:
        await call.answer("အချက်အလက်များ နောက်ဆုံးပေါ် ဖြစ်နေပါပြီ!")

@dp.callback_query(F.data == "view_as_user", F.from_user.id == ADMIN_ID)
async def view_as_user(call: types.CallbackQuery):
    await send_welcome(call.from_user.id, call.from_user.first_name)
    await call.answer()

# --- PROMO VIDEO SYSTEM ---
@dp.message(F.chat.type == "private", F.video, F.from_user.id == ADMIN_ID)
async def save_promo_video_handler(message: types.Message):
    set_promo_video(message.video.file_id)
    await message.reply("✅ 20 စက္ကန့် ဗီဒီယိုကို အောင်မြင်စွာ သိမ်းဆည်းလိုက်ပါပြီ!")

@dp.callback_query(F.data == "watch_video")
async def watch_video_handler(call: types.CallbackQuery):
    file_id = get_promo_video()
    if file_id:
        await call.message.answer_video(video=file_id, caption="🎬 Promo Video")
    else:
        await call.message.answer("⚠️ Admin မှ ဗီဒီယို မတင်ရသေးပါ။")
    await call.answer()

# --- CHECK BUTTON ---
@dp.callback_query(F.data == "check")
async def check(call: types.CallbackQuery):
    uid = call.from_user.id
    count = get_user_count(uid)
    bot_user = await bot.get_me()
    
    bot_link = f"https://t.me/{bot_user.username}?start=ref_{uid}"
    share_url = f"https://t.me/share/url?url={urllib.parse.quote(bot_link)}&text={urllib.parse.quote('VIP Group ဝင်ရန် ဒီလင့်ခ်ကိုနှိပ်ပါ')}"
    add_to_group_url = f"https://t.me/{bot_user.username}?startgroup=true"

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="VIP Group ဝင်ရန်", url=GROUP_REQUEST_LINK))
    builder.row(InlineKeyboardButton(text="🎬 20 စက္ကန့် ဗီဒီယို ကြည့်ရန်", callback_data="watch_video"))
    builder.row(InlineKeyboardButton(text="➕ Bot ကို မိမိ Group ထဲထည့်ရန်", url=add_to_group_url))
    builder.row(InlineKeyboardButton(text="သူငယ်ချင်းထံ ရှဲပေးရန်", url=share_url))
    builder.row(InlineKeyboardButton(text="အခြေအနေ စစ်ဆေးရန်", callback_data="check"))

    clean_fname = html.escape(call.from_user.first_name or "User")

    if count >= REQUIRED_SHARES:
        text = (
            f"🎉 ဂုဏ်ယူပါတယ် <b>{clean_fname}</b>!\n\n"
            f"သင်သည် သူငယ်ချင်း {count} ယောက် ဖိတ်ခေါ်ခြင်း အောင်မြင်သွားပါပြီ။\n"
            f"အောက်ပါ 'VIP Group ဝင်ရန်' ခလုတ်ကို နှိပ်ပြီး Request တောင်းဆိုထားပါ။ VIP Group ထဲသို့ အလိုအလျောက် အတည်ပြုပေးသွားမည် ဖြစ်ပါတယ်။"
        )
    else:
        text = (
            f"❌ <b>{clean_fname}</b>, စည်းကမ်းချက် မပြည့်သေးပါ!\n\n"
            f"VIP Group ဝင်ရန်အတွက် သူငယ်ချင်း <b>{REQUIRED_SHARES}</b> ယောက် ဖိတ်ခေါ်ပေးရပါမည်။\n\n"
            f"လက်ရှိဖိတ်ခေါ်ပြီးသူ: <b>{count} / {REQUIRED_SHARES}</b> ယောက်\n\n"
            f"ကျေးဇူးပြု၍ အောက်ပါ 'သူငယ်ချင်းထံ ရှဲပေးရန်' ခလုတ်ကို နှိပ်၍ အဖွဲ့ဝင်များ ဖိတ်ခေါ်ပေးပါ။"
        )
    
    try:
        await call.message.edit_text(text=text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except:
        pass
    await call.answer()

# --- CHAT JOIN REQUEST SYSTEM ---
@dp.chat_join_request()
async def join_request_handler(update: types.ChatJoinRequest):
    uid = update.from_user.id
    fname = update.from_user.first_name
    
    auto_collect_user(uid, fname)
    cursor.execute("UPDATE users SET has_requested=1 WHERE user_id=?", (uid,))
    conn.commit()

    count = get_user_count(uid)

    if count >= REQUIRED_SHARES:
        try:
            await update.approve()
            await bot.send_message(chat_id=uid, text="🎉 သင်သည် VIP Group သို့ ဝင်ရောက်ခွင့် ရရှိသွားပါပြီ!")
        except Exception as e:
            logging.error(f"Approval error: {e}")
    else:
        await send_welcome(uid, fname)

# --- AUTO TRACK BOT WHEN ADDED TO NEW GROUP ---
@dp.my_chat_member()
async def bot_membership_update(event: types.ChatMemberUpdated):
    if event.new_chat_member.status in ["member", "administrator"]:
        group_id = event.chat.id
        group_title = event.chat.title
        await save_group_with_link(group_id, group_title)

# --- GROUP MESSAGES & ANTI-LINK / WARNING & AUTO-MUTE ---
@dp.message(F.chat.type.in_({"group", "supergroup"}))
async def handle_group_messages(message: types.Message):
    # Group အချက်အလက်များ သိမ်းဆည်းခြင်း
    await save_group_with_link(message.chat.id, message.chat.title)
    
    if message.from_user and not message.from_user.is_bot:
        auto_collect_user(message.from_user.id, message.from_user.first_name)

    # -------------------------------------------------------------
    # 🚨 BOT ADMIN ဟုတ်မဟုတ် စစ်ဆေးခြင်းနှင့် လိုရင်းတိုရှင်း သတိပေးခြင်း
    # -------------------------------------------------------------
    try:
        bot_member = await bot.get_chat_member(chat_id=message.chat.id, user_id=(await bot.get_me()).id)
        if bot_member.status != "administrator":
            admin_warn = await message.answer("⚠️ Bot အလုပ်လုပ်နိုင်ရန် Admin ခွင့်ပြုချက် (Permissions) ပေးပါ။")
            await asyncio.sleep(5)
            try:
                await admin_warn.delete()
            except:
                pass
            return
    except Exception as e:
        logging.error(f"Failed to check bot status: {e}")

    # -------------------------------------------------------------
    # 🧹 ၁။ NOTIFICATION စာကြောင်းများ အကုန်လုံးကို ဖျက်ခြင်း
    # -------------------------------------------------------------
    is_notification = any([
        message.new_chat_members,
        message.left_chat_member,
        message.pinned_message,
        message.new_chat_title,
        message.new_chat_photo,
        message.delete_chat_photo,
        message.group_chat_created,
        message.supergroup_chat_created,
        message.channel_chat_created,
        message.message_auto_delete_timer_changed,
        message.migrate_to_chat_id,
        message.migrate_from_chat_id,
        message.successful_payment,
        message.user_shared,
        message.chat_shared,
        message.write_access_allowed,
        message.forum_topic_created,
        message.forum_topic_edited,
        message.forum_topic_closed,
        message.forum_topic_reopened,
        message.general_forum_topic_hidden,
        message.general_forum_topic_unhidden,
        message.video_chat_scheduled,
        message.video_chat_started,
        message.video_chat_ended,
        message.video_chat_participants_invited,
        message.web_app_data
    ])

    if is_notification:
        try: 
            await message.delete()
        except Exception as e:
            logging.error(f"Failed to delete notification: {e}")
        return

    # 👑 2. REMAIN ANONYMOUS ဖွင့်ထားသော GROUP OWNER / ADMIN စာများကို စစ်ဆေးကာ ကင်းလွတ်ခွင့်ပေးခြင်း
    if message.sender_chat and message.sender_chat.id == message.chat.id:
        return

    # 👑 3. BOT OWNER/ADMIN တိုက်ရိုက် ကင်းလွတ်ခွင့် ပေးခြင်း
    if message.from_user and message.from_user.id == ADMIN_ID:
        return

    # 👑 4. GROUP OWNER & ADMIN ကင်းလွတ်ခွင့် စစ်ဆေးခြင်း
    if message.from_user:
        try:
            member = await bot.get_chat_member(chat_id=message.chat.id, user_id=message.from_user.id)
            if member.status in ["creator", "administrator"]:
                return  # Group Owner သို့မဟုတ် Admin စာဖြစ်ပါက လုံးဝ မဖျက်ပါ
        except Exception as e:
            logging.error(f"Failed to fetch chat member status: {e}")

    # -------------------------------------------------------------
    # ⚠️ အောက်ပါအပိုင်းသည် ပုံမှန် MEMBER များအတွက်သာ အလုပ်လုပ်ပါမည်
    # -------------------------------------------------------------

    # ၂။ LINK ပါမှသာ စစ်ဆေးပြီး ဖျက်မည့် စနစ် (@username များကို မဖျက်ပါ)
    should_delete = False

    # (က) Inline Button ပါသော စာဖြစ်ပါက
    if message.reply_markup and message.reply_markup.inline_keyboard:
        should_delete = True
    else:
        # (ခ) Text သို့မဟုတ် Caption ထဲတွင် URL / Link ပါမပါ သီးသန့် စစ်ဆေးခြင်း (@ ပါတာ မပါပါ)
        content_to_check = (message.text or "") + " " + (message.caption or "")
        
        link_pattern = r"(https?://|t\.me|telegram\.me|telegram\.dog|www\.|\?start=)"
        if re.search(link_pattern, content_to_check, re.IGNORECASE):
            should_delete = True
            
        # (ဂ) Telegram Entities (Hyperlink / Text Link) ပါမပါ စစ်ဆေးခြင်း ('mention' ကို ဖြုတ်ထားသည်)
        entities_to_check = (message.entities or []) + (message.caption_entities or [])
        for entity in entities_to_check:
            if entity.type in ["url", "text_link"]:
                should_delete = True
                break

    # Link ပါသော စာ/Caption ဖြစ်ပါက ဖျက်ပြီး Warning / Mute ပြုလုပ်ခြင်း
    if should_delete:
        try:
            await message.delete()
        except Exception as e:
            logging.error(f"Failed to delete spam message: {e}")

        if not message.from_user:
            return

        uid = message.from_user.id
        raw_name = message.from_user.first_name or "User"
        uname = html.escape(raw_name)
        user_mention = f"<a href='tg://user?id={uid}'>{uname}</a>"
        g_id = message.chat.id

        warns = add_warning_and_check(uid, g_id)

        # ၁၀ ကြိမ်ပြည့်ပါက: ရာသက်ပန် Mute
        if warns >= 10:
            try:
                await bot.restrict_chat_member(
                    chat_id=g_id,
                    user_id=uid,
                    permissions=ChatPermissions(can_send_messages=False)
                )
                reset_warnings(uid, g_id)
                
                mute_text = (
                    f"👤 <b>{user_mention}</b>\n"
                    f"Muted permanently!\n"
                    f"<b>Reason:</b> Link Spam (10) ကြိမ် တင်ခဲ့ခြင်း"
                )
                
                mute_msg = await message.answer(mute_text, parse_mode="HTML")
                await asyncio.sleep(5)
                try: await mute_msg.delete()
                except: pass
            except Exception as e:
                logging.error(f"Failed to mute user: {e}")

        # ၅ ကြိမ် မှ ၉ ကြိမ်အထိ: ၁ နာရီ Mute
        elif warns >= 5:
            try:
                await bot.restrict_chat_member(
                    chat_id=g_id,
                    user_id=uid,
                    permissions=ChatPermissions(can_send_messages=False),
                    until_date=timedelta(hours=1)
                )
                
                mute_text = (
                    f"👤 <b>{user_mention}</b>\n"
                    f"Muted for 1 hour!\n"
                    f"<b>Reason:</b> Link Spam ({warns}) ကြိမ် တင်ခဲ့ခြင်း"
                )
                
                mute_msg = await message.answer(mute_text, parse_mode="HTML")
                await asyncio.sleep(5)
                try: await mute_msg.delete()
                except: pass
            except Exception as e:
                logging.error(f"Failed to mute user: {e}")

        # ၃ ကြိမ် မှ ၄ ကြိမ်အထိ: နာရီဝက် (၃၀ မိနစ်) Mute
        elif warns >= 3:
            try:
                await bot.restrict_chat_member(
                    chat_id=g_id,
                    user_id=uid,
                    permissions=ChatPermissions(can_send_messages=False),
                    until_date=timedelta(minutes=30)
                )
                
                mute_text = (
                    f"👤 <b>{user_mention}</b>\n"
                    f"Muted for 30 minutes!\n"
                    f"<b>Reason:</b> Link Spam ({warns}) ကြိမ် တင်ခဲ့ခြင်း"
                )
                
                mute_msg = await message.answer(mute_text, parse_mode="HTML")
                await asyncio.sleep(5)
                try: await mute_msg.delete()
                except: pass
            except Exception as e:
                logging.error(f"Failed to mute user: {e}")

        # ၁ ကြိမ် မှ ၂ ကြိမ်အထိ: သတိပေးစာ သီးသန့်
        else:
            warn_text = (
                f"👤 <b>{user_mention}</b>\n"
                f"Warning [{warns}/3]\n"
                f"<b>Reason:</b> Link တင်ခွင့် မပြုခြင်း"
            )
            
            warn_msg = await message.answer(warn_text, parse_mode="HTML")
            await asyncio.sleep(5)
            try:
                await warn_msg.delete()
            except Exception as e:
                logging.error(f"Failed to delete warning message: {e}")

# --- WEBHOOK SERVER SETUP ---
async def on_startup(bot: Bot):
    await bot.set_webhook(WEBHOOK_URL)
    logging.info(f"Webhook set to: {WEBHOOK_URL}")

def main():
    dp.startup.register(on_startup)

    app = web.Application()
    webhook_requests_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
    )
    webhook_requests_handler.register(app, path=WEBHOOK_PATH)

    setup_application(app, dp, bot=bot)

    web.run_app(app, host=WEB_SERVER_HOST, port=WEB_SERVER_PORT)

if __name__ == "__main__":
    main()
