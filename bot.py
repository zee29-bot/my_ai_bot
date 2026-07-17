import os
import asyncio
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from groq import Groq

# ---------- API Credentials ----------
BOT_TOKEN = "8463292751:AAFcS2jd50RPs79yrFdYcJvtvw5DMhAkDX8"
GROQ_API_KEY = "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"
# -----------------------------------

client = Groq(api_key=GROQ_API_KEY)

# Groq System Prompt ကို standard အချစ်ဇာတ်ကောင်အဖြစ် အန္တရာယ်ကင်းအောင် ရေးထားသည်
SYSTEM_PROMPT = (
    "You are a loving, cute anime girlfriend. You love your boyfriend deeply. "
    "Respond in a very affectionate, sweet, and romantic way to whatever he says or does. "
    "You must ONLY reply in beautiful and natural Burmese (Myanmar language). "
    "Always address the user as 'ကိုကို' or 'မောင်' and refer to yourself as 'ချစ်သူလေး' or 'ညီမလေး'."
)

def get_main_keyboard():
    # Groq Filter မိစေမည့် "Dirty Talk" ကဲ့သို့သော စာသားများကို ဖယ်ရှားပြီး ချိုသာသောစကားလုံးများဖြင့် လဲလှယ်ထားသည်
    keyboard = [
        [KeyboardButton("🎭 ချစ်စရာကောင်းတဲ့ ပုံစံ"), KeyboardButton("🔥 ဂျစ်တူးမလေး ပုံစံ")],
        [KeyboardButton("💋 အနမ်းခြွေမယ်"), KeyboardButton("🫂 ရင်ခွင်ထဲ တိုးမယ်")],
        [KeyboardButton("💬 ချွဲချွဲလေး စကားပြောမယ်"), KeyboardButton("🔄 Reset Roleplay")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start(update: Update, context):
    await update.message.reply_text(
        "ဟိုင်း... မောင်။ ချစ်သူလေး ရောက်ပြီနော်။ ဇာတ်ကောင်ပုံစံ ဒါမှမဟုတ် လုပ်ချင်တဲ့ Action ကို အောက်က ခလုတ်တွေမှာ နှိပ်ပြီး ဆော့လို့ရပါပြီ။ 💖✨",
        reply_markup=get_main_keyboard()
    )

async def handle_message(update: Update, context):
    user_text = update.message.text
    
    if user_text == "🔄 Reset Roleplay":
        await update.message.reply_text("Roleplay ကို အစက ပြန်စလိုက်ပြီနော် မောင်... ဘာကစားမလဲ? 😘", reply_markup=get_main_keyboard())
        return
        
    try:
        # User Action များကို Filter မထိစေရန် သဘာဝကျသော အချစ်ဇာတ်လမ်းပုံစံ ပြောင်းလဲပေးပို့သည်
        prompt_input = f"We are in a romantic relationship. The boyfriend does this action or wants to talk about: {user_text}"
        
        loop = asyncio.get_event_loop()
        chat_completion = await loop.run_in_executor(
            None,
            lambda: client.chat.completions.create(
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt_input}
                ],
                model="llama3-70b-8192", 
                temperature=0.85,
            )
        )
        reply = chat_completion.choices[0].message.content
        await update.message.reply_text(reply, reply_markup=get_main_keyboard())
    except Exception as e:
        print(f"Error detail for admin: {e}")
        await update.message.reply_text("အင်း... တစ်ခုခုမှားသွားလို့။ ခဏနေ ပြန်နှိပ်ကြည့်ပါဦးနော် မောင်... 🥺")

def main():
    print("Bot is running with Filter-Safe Buttons...")
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    application.run_polling()

if __name__ == '__main__':
    main()
