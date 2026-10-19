import os
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from telegram import Update
from groq import Groq
from tavily import TavilyClient

BOT_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
GROQ_KEY = os.getenv("GROQ_API_KEY", "").strip()
TAVILY_KEY = os.getenv("TAVILY_API_KEY", "").strip()
CREATOR_NAME = "HIBA HAANIYA.F"

groq_client = Groq(api_key=GROQ_KEY) if GROQ_KEY else None
tavily_client = TavilyClient(api_key=TAVILY_KEY) if TAVILY_KEY else None

def live_search(query: str):
    try:
        if not tavily_client: return ""
        result = tavily_client.search(query=query, max_results=2, include_answer=True)
        return "\n".join([r['content'][:300] for r in result.get('results', [])])
    except: return ""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Namaste! I am SATYA by {CREATOR_NAME} 🛡️")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    lower = text.lower()

    if any(w in lower for w in ["who created you", "who made you", "your creator", "hiba"]):
        await update.message.reply_text(f"I was created by {CREATOR_NAME} — Founder & CEO of SATYA. I am not from OpenAI/Google/【entity-Meta¦canonical_name=Meta】. I am SATYA by {CREATOR_NAME} 🛡️")
        return

    await update.message.reply_text("Checking... 🔍 5 sec...")

    live_data = live_search(text)
    prompt = f"You are SATYA by {CREATOR_NAME}. Never say OpenAI. Verify: {text}. Live: {live_data}. Reply in user's language as CLAIM, VERDICT TRUE/FALSE, EXPLANATION 2 lines."

    try:
        completion = groq_client.chat.completions.create(
            # Groq models that ACTUALLY work in 2026
GROQ_MODELS = [
    "openai/gpt-oss-20b",          # FREE, fastest, always works
    "openai/gpt-oss-120b",         # FREE, smarter
    "llama-3.1-70b-versatile",     # backup
    "meta-llama/llama-4-scout-17b-16e-instruct", # new Llama 4
    "llama-3.3-70b-versatile"      # try last
]

# Then in your groq call, use:
# Change line from: model="llama-..."
# To:
model="openai/gpt-oss-20b"
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )
        reply = completion.choices[0].message.content
    except Exception as e:
        reply = f"Groq Error: {e}"

    await update.message.reply_text(reply)

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print(f"SATYA by {CREATOR_NAME} starting...")
    app.run_polling(drop_pending_updates=True)
