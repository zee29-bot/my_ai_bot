import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from groq import Groq

# ---------- ဒီနေရာ ၂ ခုကို ပြင်ရန် ----------
BOT_TOKEN = "8463292751:AAFcS2jd50RPs79yrFdYcJvtvw5DMhAkDX8"
GROQ_API_KEY = "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"
# ---------------------------------------

client = Groq(api_key=GROQ_API_KEY)

# ခင်ဗျား ကြိုက်တဲ့ ဇာတ်ကောင်ပုံစံ ဒီမှာ ပြောင်းလို့ရပါတယ်
SYSTEM_PROMPT = "You are a cute and caring anime girlfriend. Only reply in Burmese (Myanmar language). Be very romantic and sweet."

async def start(update: Update, context):
    await update.message.reply_text("ဟိုင်း! ငါက ခင်ဗျားရဲ့ AI ချစ်သူလေး။ ဘာတွေပြောချင်လဲ?")

async def handle_message(update: Update, context):
    user_text = update.message.text
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_text}
            ],
            model="llama3-70b-8192",
        )
        reply = chat_completion.choices[0].message.content
        await update.message.reply_text(reply)
    except Exception as e:
        await update.message.reply_text("အင်း... နည်းနည်းတော့ စိတ်ရှုပ်နေမိတယ်။ ခဏနေပြန်ပြောကြည့်လေ။")

if __name__ == '__main__':
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Bot is running...")
    application.run_polling()
