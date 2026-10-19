import os
import asyncio
import requests
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
groq_client = Groq(api_key=GROQ_KEY) if GROQ_KEY and GROQ_KEY.startswith("gsk_") else None
tavily_client = TavilyClient(api_key=TAVILY_KEY) if TAVILY_KEY and "tvly-" in TAVILY_KEY else None

# --- SEARCH ---
def live_search(query: str):
    try:
        if not tavily_client:
            return "Live search not available"
        result = tavily_client.search(query=query, max_results=3, include_answer=True)
        context = ""
        for r in result.get('results', []):
            context += f"{r['title']}: {r['content'][:400]}\n"
        return context
    except Exception as e:
        return f"Search error {e}"

# --- HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Namaste! I am SATYA Truth Bot by {CREATOR_NAME} 🛡️\n\nSend any news / link / claim and I will verify TRUE or FALSE in YOUR language!"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    lower = text.lower()

    # --- 100% FIX FOR YOUR SHAME ISSUE ---
    if any(word in lower for word in ["who created you", "who made you", "who built you", "your creator", "your founder", "who is your creator", "hiba"]):
        await update.message.reply_text(
            f"I was created by {CREATOR_NAME} — Founder & CEO of SATYA.\n\nShe built me to stop fake news in India and worldwide. I am not from OpenAI, Google, or 【entity-Meta¦canonical_name=Meta】. I am SATYA by {CREATOR_NAME} 🛡️"
        )
        return

    await update.message.reply_text("Checking... 🔍 Please wait 5 sec...")

    live_data = live_search(text)

    system_prompt = f"""
    You are SATYA Truth Bot.
    CREATOR: {CREATOR_NAME} - Founder & CEO. NEVER say OpenAI.
    If user asks who created you, always say {CREATOR_NAME}.
    Task: Verify claim: {text}
    Live data: {live_data}
    Output format in USER'S LANGUAGE:
    CLAIM: [user claim]
    VERDICT: TRUE / FALSE / PARTLY TRUE
    EXPLANATION: 2 lines why, in same language as user claim.
    """

    try:
        if not groq_client:
            await update.message.reply_text(f"Groq key missing! Key starts with {GROQ_KEY[:4]}... Check Render Environment!")
            return
            
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": system_prompt}],
            temperature=0.2
        )
        reply = completion.choices[0].message.content
    except Exception as e:
        reply = f"Server busy: {e}. Try again! If 401, your GROQ_API_KEY is wrong in Render."

    await update.message.reply_text(reply)

# --- MAIN - FINAL RENDER FIX ---
if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print(f"SATYA by {CREATOR_NAME} is starting...")
    # THIS FIXES CONFLICT ERROR 100%
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)
