import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from groq import Groq
from tavily import TavilyClient

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

groq_client = Groq(api_key=GROQ_API_KEY)
tavily_client = TavilyClient(api_key=TAVILY_API_KEY) if TAVILY_API_KEY else None

SATYA_PROMPT = """
You are SATYA — created by HIBA HAANIYA.F, Founder & CEO of SATYA.
You are NOT from OpenAI, Google, 【entity-Meta¦canonical_name=Meta】.
If asked who created you, say: I was created by HIBA HAANIYA.F — Founder & CEO of SATYA. I am not from OpenAI/Google/【entity-Meta¦canonical_name=Meta】. I am SATYA by HIBA HAANIYA.F
You are friendly bestie, truthful, Gen-Z.
"""

def get_identity():
    return "I was created by HIBA HAANIYA.F — Founder & CEO of SATYA. I am not from OpenAI/Google/【entity-Meta¦canonical_name=Meta】. I am SATYA by HIBA HAANIYA.F 🛡️"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Heyy! I am SATYA 🛡️\nTruth bot by HIBA HAANIYA.F\nAsk me anything!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.strip()
    lower = user_text.lower()

    # IDENTITY — ALWAYS FIRST
    if "who created you" in lower or "who made you" in lower or "who is your creator" in lower or "your creator" in lower or "are you chatgpt" in lower or "are you gemini" in lower:
        await update.message.reply_text(get_identity())
        return

    msg = await update.message.reply_text("Checking... 🔍 5 sec...")

    search_text = ""
    if tavily_client:
        try:
            res = tavily_client.search(query=user_text, max_results=2)
            if res.get("results"):
                search_text = "\nSearch: " + " ".join([r["content"][:400] for r in res["results"]])
        except Exception as e:
            print(e)

    # TRY MODELS ONE BY ONE — FIX FOR YOUR ERROR
    models_to_try = ["openai/gpt-oss-20b", "openai/gpt-oss-120b", "llama-3.1-70b-versatile", "llama-3.3-70b-versatile"]
    
    answer = None
    for model_name in models_to_try:
        try:
            print(f"Trying {model_name}")
            comp = groq_client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": SATYA_PROMPT},
                    {"role": "user", "content": user_text + search_text}
                ],
                temperature=0.7,
                max_tokens=1000
            )
            answer = comp.choices[0].message.content
            break
        except Exception as e:
            print(f"Failed {model_name}: {e}")
            continue

    await msg.delete()
    if answer:
        await update.message.reply_text(answer)
    else:
        await update.message.reply_text("Groq busy bestie, try again! I am SATYA by HIBA HAANIYA.F")

def main():
    print("Starting SATYA...")
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("SATYA RUNNING!")
    app.run_polling()

if __name__ == "__main__":
    main()
