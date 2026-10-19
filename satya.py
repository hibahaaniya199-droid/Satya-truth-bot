import os
import asyncio
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from telegram import Update
from groq import Groq
from tavily import TavilyClient

# --- ENV ---
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
GROQ_KEY = os.getenv("GROQ_API_KEY", "").strip()
TAVILY_KEY = os.getenv("TAVILY_API_KEY", "").strip()
CREATOR_NAME = "HIBA HAANIYA.F"

# --- CLIENTS ---
groq_client = Groq(api_key=GROQ_KEY) if GROQ_KEY else None
tavily_client = TavilyClient(api_key=TAVILY_KEY) if TAVILY_KEY else None

def live_search(query: str):
    try:
        if not tavily_client:
            return "No search"
        result = tavily_client.search(query=query, max_results=2, include_answer=True)
        context = ""
        for r in result.get('results', []):
            context += f"{r['title']}: {r['content'][:300]}\n"
        return context
    except:
        return "No search"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Namaste! I am SATYA by {CREATOR_NAME} 🛡️\nSend any claim, I verify TRUE/FALSE!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    lower = text.lower()

    if any(w in lower for w in ["who created you", "who made you", "your creator", "your founder", "hiba"]):
        await update.message.reply_text(f"I was created by {CREATOR_NAME} — Founder & CEO of SATYA. I am not from OpenAI/Google/Meta. I am SATYA by {CREATOR_NAME} 🛡️")
        return

    await update.message.reply_text("Checking... 🔍 5 sec...")

    live_data = live_search(text)

    prompt = f"""
You are SATYA by {CREATOR_NAME}. Never say OpenAI.
Verify: {text}
Live data: {live_data}
Reply in user's language:
CLAIM: [claim]
VERDICT: TRUE/FALSE/PARTLY TRUE
EXPLANATION: 2 lines
"""

    try:
        if not groq_client:
            await update.message.reply_text("Groq key missing in Render! Add GROQ_API_KEY starting with gsk_")
            return
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )
        reply = completion.choices[0].message.content
    except Exception as e:
        reply = f"Error: {e} - Check GROQ key in Render!"

    await update.message.reply_text(reply)

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print(f"SATYA by {CREATOR_NAME} starting...")
    # THIS FIXES YOUR CONFLICT ERROR
    app.run_polling(drop_pending_updates=True)
