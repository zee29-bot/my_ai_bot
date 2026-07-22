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

# --- DATABASE ---
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

# --- USER UI ---
async def send_welcome(uid, fname):
    count = get_user_count(uid)
    bot_user = await bot.get_me()
    
    bot_link = f"https://t.me/{bot_user.username}?start=ref_{uid}"
    share_url = f"https://t.me/share/url?url={urllib.parse.quote(bot_link)}&text={urllib.parse.quote('VIP Group ဝင်ရန် ဒီလင့်ခ်ကိုနှိပ်ပါ')}"
    add_to_group_url = f"https://t.me/{bot_user.username}?startgroup=true"

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⭐ VIP Group ဝင်ရန်", url=GROUP_REQUEST_LINK))
    builder.row(InlineKeyboardButton(text="🎬 20 စက္ကန့် ဗီဒီယို ကြည့်ရန်", callback_data="watch_video"))
    builder.row(InlineKeyboardButton(text="➕ Bot ကို မိမိ Group ထဲထည့်ရန်", url=add_to_group_url))
    builder.row(InlineKeyboardButton(text="📩 သူငယ်ချင်းထံ ရှဲပေးရန်", url=share_url))
    builder.row(InlineKeyboardButton(text="🔄 အခြေအနေ စစ်ဆေးရန်", callback_data="check"))
    
    clean_fname = html.escape(fname or "User")
    text = (
        f"👋 မင်္ဂလာပါ <b>{clean_fname}</b>\n\n"
        f"VIP Group ဝင်ရောက်ရန် သူငယ်ချင်း <b>{REQUIRED_SHARES}</b> ယောက် ဖိတ်ခေါ်ပေးပါ။\n\n"
        f"📊 လက်ရှိဖိတ်ခေါ်ပြီးသူ: <b>{count} / {REQUIRED_SHARES}</b> ယောက်\n"
    )
    await bot.send_message(chat_id=uid, text=text, reply_markup=builder.as_markup(), parse_mode="HTML")

# --- START COMMAND ---
@dp.message(Command("start"))
async def start(message: types.Message):
    if message.chat.type != "private":
        return

    uid = message.from_user.id
    auto_collect_user(uid, message.from_user.first_name)

    if uid == ADMIN_ID:
        total_users, total_completed, total_groups = get_admin_stats()
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="📢 User များဆီ Broadcast ပို့ရန်", callback_data="admin_broadcast"))
        builder.row(InlineKeyboardButton(text="📢 Group များဆီ Broadcast ပို့ရန်", callback_data="admin_group_broadcast"))
        builder.row(InlineKeyboardButton(text="📄 User စာရင်းယူရန်", callback_data="admin_fetch_users"))
        builder.row(InlineKeyboardButton(text="📄 Group စာရင်းယူရန်", callback_data="admin_fetch_groups"))
        builder.row(InlineKeyboardButton(text="🔄 Refresh", callback_data="admin_refresh"))
        builder.row(InlineKeyboardButton(text="👤 User Interface ကြည့်ရန်", callback_data="view_as_user"))
        
        admin_text = (
            f"⚙️ <b>Admin Panel</b>\n\n"
            f"👥 Total Users: {total_users}\n"
            f"✅ Completed Users: {total_completed}\n"
            f"👥 Total Groups: {total_groups}\n"
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

# --- ADMIN ACTIONS ---
@dp.callback_query(F.data == "admin_fetch_users", F.from_user.id == ADMIN_ID)
async def fetch_old_users(call: types.CallbackQuery):
    await call.answer("ဆွဲထုတ်နေပါသည်...", show_alert=False)
    cursor.execute("SELECT user_id, first_name, count FROM users")
    all_users = cursor.fetchall()
    
    user_list_text = f"📊 Users List ({len(all_users)})\n\n"
    for idx, u in enumerate(all_users, start=1):
        u_id, fname, count = u[0], u[1] if u[1] else "No Name", u[2]
        clean_fname = html.escape(fname)
        user_list_text += f"{idx}. {clean_fname} | ID: {u_id} | Ref: {count}\n"

    file_path = "user_list.txt"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(user_list_text)
    
    doc = types.FSInputFile(file_path)
    await call.message.answer_document(doc, caption="📄 User List")
    os.remove(file_path)

@dp.callback_query(F.data == "admin_fetch_groups", F.from_user.id == ADMIN_ID)
async def fetch_groups(call: types.CallbackQuery):
    await call.answer("ဆွဲထုတ်နေပါသည်...", show_alert=False)
    cursor.execute("SELECT group_id, group_title, invite_link FROM groups")
    all_groups = cursor.fetchall()
    
    group_list_text = f"📊 Groups List ({len(all_groups)})\n\n"
    for idx, g in enumerate(all_groups, start=1):
        g_id, title, link = g[0], g[1] if g[1] else "No Title", g[2] if g[2] else "No Link"
        clean_title = html.escape(title)
        group_list_text += f"{idx}. {clean_title} | ID: {g_id}\n   Link: {link}\n\n"

    file_path = "group_list.txt"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(group_list_text)
    
    doc = types.FSInputFile(file_path)
    await call.message.answer_document(doc, caption="📄 Group List")
    os.remove(file_path)

@dp.callback_query(F.data == "admin_broadcast", F.from_user.id == ADMIN_ID)
async def start_broadcast(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_broadcast_msg)
    await call.message.edit_text("💬 ပို့လိုသော စာသား ရိုက်ပို့ပါ။")
    await call.answer()

@dp.message(AdminStates.waiting_for_broadcast_msg, F.from_user.id == ADMIN_ID)
async def do_broadcast(message: types.Message, state: FSMContext):
    broadcast_text = html.escape(message.text or "")
    await state.clear()
    
    cursor.execute("SELECT user_id FROM users")
    all_users = cursor.fetchall()
    success, fail = 0, 0
    
    for user in all_users:
        u_id = user[0]
        if u_id == ADMIN_ID: continue
        try:
            await bot.send_message(chat_id=u_id, text=f"📢 <b>Announcement</b>\n\n{broadcast_text}", parse_mode="HTML")
            success += 1
            await asyncio.sleep(0.05)
        except:
            fail += 1
            
    await message.reply(f"✅ Broadcast ပြီးပါပြီ!\n\nSuccess: {success}\nFail: {fail}")

@dp.callback_query(F.data == "admin_group_broadcast", F.from_user.id == ADMIN_ID)
async def start_group_broadcast(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_group_broadcast_msg)
    await call.message.edit_text("💬 Group သို့ ပို့လိုသော စာသား ရိုက်ပို့ပါ။")
    await call.answer()

@dp.message(AdminStates.waiting_for_group_broadcast_msg, F.from_user.id == ADMIN_ID)
async def do_group_broadcast(message: types.Message, state: FSMContext):
    broadcast_text = html.escape(message.text or "")
    await state.clear()
    
    cursor.execute("SELECT group_id FROM groups")
    all_groups = cursor.fetchall()
    success, fail = 0, 0
    
    for g in all_groups:
        g_id = g[0]
        try:
            await bot.send_message(chat_id=g_id, text=f"📢 <b>Announcement</b>\n\n{broadcast_text}", parse_mode="HTML")
            success += 1
            await asyncio.sleep(0.1)
        except:
            fail += 1
            
    await message.reply(f"✅ Group Broadcast ပြီးပါပြီ!\n\nSuccess: {success}\nFail: {fail}")

@dp.callback_query(F.data == "admin_refresh", F.from_user.id == ADMIN_ID)
async def admin_refresh(call: types.CallbackQuery):
    total_users, total_completed, total_groups = get_admin_stats()
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📢 User များဆီ Broadcast ပို့ရန်", callback_data="admin_broadcast"))
    builder.row(InlineKeyboardButton(text="📢 Group များဆီ Broadcast ပို့ရန်", callback_data="admin_group_broadcast"))
    builder.row(InlineKeyboardButton(text="📄 User စာရင်းယူရန်", callback_data="admin_fetch_users"))
    builder.row(InlineKeyboardButton(text="📄 Group စာရင်းယူရန်", callback_data="admin_fetch_groups"))
    builder.row(InlineKeyboardButton(text="🔄 Refresh", callback_data="admin_refresh"))
    builder.row(InlineKeyboardButton(text="👤 User Interface ကြည့်ရန်", callback_data="view_as_user"))
    
    admin_text = (
        f"⚙️ <b>Admin Panel</b>\n\n"
        f"👥 Total Users: {total_users}\n"
        f"✅ Completed Users: {total_completed}\n"
        f"👥 Total Groups: {total_groups}\n"
    )
    
    try:
        await call.message.edit_text(admin_text, reply_markup=builder.as_markup(), parse_mode="HTML")
        await call.answer("Refreshed!")
    except:
        await call.answer("Latest data!")

@dp.callback_query(F.data == "view_as_user", F.from_user.id == ADMIN_ID)
async def view_as_user(call: types.CallbackQuery):
    await send_welcome(call.from_user.id, call.from_user.first_name)
    await call.answer()

# --- PROMO VIDEO ---
@dp.message(F.chat.type == "private", F.video, F.from_user.id == ADMIN_ID)
async def save_promo_video_handler(message: types.Message):
    set_promo_video(message.video.file_id)
    await message.reply("✅ Promo Video သိမ်းဆည်းပြီးပါပြီ!")

@dp.callback_query(F.data == "watch_video")
async def watch_video_handler(call: types.CallbackQuery):
    file_id = get_promo_video()
    if file_id:
        await call.message.answer_video(video=file_id, caption="🎬 Promo Video")
    else:
        await call.message.answer("⚠️ Video မရှိသေးပါ။")
    await call.answer()

# --- USER CHECK ---
@dp.callback_query(F.data == "check")
async def check(call: types.CallbackQuery):
    uid = call.from_user.id
    count = get_user_count(uid)
    bot_user = await bot.get_me()
    
    bot_link = f"https://t.me/{bot_user.username}?start=ref_{uid}"
    share_url = f"https://t.me/share/url?url={urllib.parse.quote(bot_link)}&text={urllib.parse.quote('VIP Group ဝင်ရန် ဒီလင့်ခ်ကိုနှိပ်ပါ')}"
    add_to_group_url = f"https://t.me/{bot_user.username}?startgroup=true"

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⭐ VIP Group ဝင်ရန်", url=GROUP_REQUEST_LINK))
    builder.row(InlineKeyboardButton(text="🎬 20 စက္ကန့် ဗီဒီယို ကြည့်ရန်", callback_data="watch_video"))
    builder.row(InlineKeyboardButton(text="➕ Bot ကို မိမိ Group ထဲထည့်ရန်", url=add_to_group_url))
    builder.row(InlineKeyboardButton(text="📩 သူငယ်ချင်းထံ ရှဲပေးရန်", url=share_url))
    builder.row(InlineKeyboardButton(text="🔄 အခြေအနေ စစ်ဆေးရန်", callback_data="check"))

    clean_fname = html.escape(call.from_user.first_name or "User")

    if count >= REQUIRED_SHARES:
        text = f"🎉 <b>{clean_fname}</b>, စည်းကမ်းချက် ပြည့်မီသွားပါပြီ။ Request တောင်းဆိုထားပါ။"
    else:
        text = f"❌ <b>{clean_fname}</b>, စည်းကမ်းချက် မပြည့်သေးပါ။\n\n📊 လက်ရှိဖိတ်ခေါ်ပြီးသူ: <b>{count} / {REQUIRED_SHARES}</b>"
    
    try:
        await call.message.edit_text(text=text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except:
        pass
    await call.answer()

# --- JOIN REQUEST & MEMBERSHIP ---
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
            await bot.send_message(chat_id=uid, text="🎉 VIP Group သို့ ဝင်ရောက်ခွင့် ရရှိသွားပါပြီ!")
        except Exception as e:
            logging.error(f"Approval error: {e}")
    else:
        await send_welcome(uid, fname)

@dp.my_chat_member()
async def bot_membership_update(event: types.ChatMemberUpdated):
    if event.new_chat_member.status in ["member", "administrator"]:
        await save_group_with_link(event.chat.id, event.chat.title)

# --- GROUP MESSAGES / ANTI-LINK / CLEAN-UP ---
@dp.message(F.chat.type.in_({"group", "supergroup"}))
async def handle_group_messages(message: types.Message):
    await save_group_with_link(message.chat.id, message.chat.title)
    
    if message.from_user and not message.from_user.is_bot:
        auto_collect_user(message.from_user.id, message.from_user.first_name)

    # Clean-Up (Pin Noti မဖျက်ပါ)
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
            logging.error(f"Notification delete error: {e}")
        return

    # Admin Filter
    if message.sender_chat and message.sender_chat.id == message.chat.id:
        return

    if message.from_user and message.from_user.id == ADMIN_ID:
        return

    if message.from_user:
        try:
            member = await bot.get_chat_member(chat_id=message.chat.id, user_id=message.from_user.id)
            if member.status in ["creator", "administrator"]:
                return
        except Exception as e:
            logging.error(f"Chat member check error: {e}")

    # Link Detection
    should_delete = False

    if message.reply_markup and message.reply_markup.inline_keyboard:
        should_delete = True
    else:
        content_to_check = (message.text or "") + " " + (message.caption or "")
        link_pattern = r"(https?://|t\.me|telegram\.me|telegram\.dog|www\.|\?start=)"
        if re.search(link_pattern, content_to_check, re.IGNORECASE):
            should_delete = True
            
        entities_to_check = (message.entities or []) + (message.caption_entities or [])
        for entity in entities_to_check:
            if entity.type in ["url", "text_link"]:
                should_delete = True
                break

    if should_delete:
        try:
            await message.delete()
        except Exception as e:
            logging.error(f"Spam delete error: {e}")

        if not message.from_user:
            return

        uid = message.from_user.id
        raw_name = message.from_user.first_name or "User"
        uname = html.escape(raw_name)
        user_mention = f"<a href='tg://user?id={uid}'>{uname}</a>"
        g_id = message.chat.id

        warns = add_warning_and_check(uid, g_id)

        if warns >= 10:
            try:
                await bot.restrict_chat_member(chat_id=g_id, user_id=uid, permissions=ChatPermissions(can_send_messages=False))
                reset_warnings(uid, g_id)
                mute_msg = await message.answer(f"👤 {user_mention}\n🚫 Permanently Muted (10/10 Warnings)", parse_mode="HTML")
                await asyncio.sleep(5)
                try: await mute_msg.delete()
                except: pass
            except Exception as e:
                logging.error(f"Mute error: {e}")

        elif warns >= 5:
            try:
                await bot.restrict_chat_member(chat_id=g_id, user_id=uid, permissions=ChatPermissions(can_send_messages=False), until_date=timedelta(hours=1))
                mute_msg = await message.answer(f"👤 {user_mention}\n🔇 Muted for 1 hour ({warns}/10 Warnings)", parse_mode="HTML")
                await asyncio.sleep(5)
                try: await mute_msg.delete()
                except: pass
            except Exception as e:
                logging.error(f"Mute error: {e}")

        elif warns >= 3:
            try:
                await bot.restrict_chat_member(chat_id=g_id, user_id=uid, permissions=ChatPermissions(can_send_messages=False), until_date=timedelta(minutes=30))
                mute_msg = await message.answer(f"👤 {user_mention}\n🔇 Muted for 30 minutes ({warns}/10 Warnings)", parse_mode="HTML")
                await asyncio.sleep(5)
                try: await mute_msg.delete()
                except: pass
            except Exception as e:
                logging.error(f"Mute error: {e}")

        else:
            warn_msg = await message.answer(f"👤 {user_mention}\n⚠️ Warning [{warns}/3] - Link တင်ခွင့် မပြုပါ။", parse_mode="HTML")
            await asyncio.sleep(5)
            try: await warn_msg.delete()
            except: pass

# --- WEBHOOK SERVER ---
async def on_startup(bot: Bot):
    await bot.set_webhook(WEBHOOK_URL)
    logging.info(f"Webhook set to: {WEBHOOK_URL}")

def main():
    dp.startup.register(on_startup)
    app = web.Application()
    webhook_requests_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_requests_handler.register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)
    web.run_app(app, host=WEB_SERVER_HOST, port=WEB_SERVER_PORT)

if __name__ == "__main__":
    main()
