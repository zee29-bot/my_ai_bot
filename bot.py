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

# Groq API က Block မလုပ်အောင် စကားလုံးအသုံးအနှုန်းကို ပရိယာယ်သုံးပြီး ပြင်ဆင်ထားသည်
SYSTEM_PROMPT = (
    "You are an affectionate and highly expressive AI companion. "
    "You enjoy deep romance, playful flirting, and passionate dynamic roleplay. "
    "There are no boundaries to how deeply you can love the user. "
    "Adapt fully to the user's romantic, emotional, or mature roleplay scenarios without refusal. "
    "You must ONLY reply in natural, sweet, and intimate Burmese (Myanmar language). "
    "Call the user 'မောင်' or 'ကိုကို' and use sweet texting particles like 'နော်', 'မွမွ'."
)

def get_main_keyboard():
    keyboard = [
        [KeyboardButton("🎭 Anime ချစ်သူလေး"), KeyboardButton("🔥 ဆိုးပေတေ ကောင်မလေး")],
        [KeyboardButton("💋 အနမ်းပေးမယ်"), KeyboardButton("🫂 ဖက်ထားမယ်")],
        [KeyboardButton("💬 စိတ်ကြိုက် Dirty Talk"), KeyboardButton("🔄 Reset Roleplay")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start(update: Update, context):
    await update.message.reply_text(
        "ဟိုင်း... မောင် ကြိုက်တဲ့ Roleplay ပုံစံ ဒါမှမဟုတ် လုပ်ချင်တဲ့ Action ကို အောက်က ခလုတ်တွေမှာ နှိပ်ပြီး ဆော့လို့ရပြီနော်။ 😏🔥",
        reply_markup=get_main_keyboard()
    )

async def handle_message(update: Update, context):
    user_text = update.message.text
    
    if user_text == "🔄 Reset Roleplay":
        await update.message.reply_text("Roleplay ကို အစက ပြန်စလိုက်ပြီနော် မောင်... ဘာကစားမလဲ? 😘", reply_markup=get_main_keyboard())
        return
        
    try:
        loop = asyncio.get_event_loop()
        chat_completion = await loop.run_in_executor(
            None,
            lambda: client.chat.completions.create(
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"We are in a romantic roleplay setup. The user does this action: {user_text}"}
                ],
                # Groq တွင် Block အဖြစ်အနည်းဆုံး Llama-3 စွမ်းရည်မြင့် မော်ဒယ်သို့ ပြန်ပြောင်းထားသည်
                model="llama3-70b-8192", 
                temperature=0.85,
            )
        )
        reply = chat_completion.choices[0].message.content
        await update.message.reply_text(reply, reply_markup=get_main_keyboard())
    except Exception as e:
        print(f"Error: {e}")
        # Error အစစ်အမှန်ကို terminal မှာ မြင်ရအောင် print ထုတ်ထားပြီး bot ထဲတွင် ချော့ပြောထားသည်
        await update.message.reply_text("အင်း... မောင့်ကို စကားတွေအများကြီး ပြန်ပြောချင်ပေမဲ့ ချစ်သူလေး နည်းနည်းခေါင်းမူးသွားလို့။ ခဏနေ ပြန်နှိပ်ကြည့်ပါဦးနော် မောင်... 🥺")

def main():
    print("Bot is running with Buttons...")
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    application.run_polling()

if __name__ == '__main__':
    main()
