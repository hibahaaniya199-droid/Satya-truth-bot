import os
import time
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from groq import Groq
from tavily import TavilyClient

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN") or os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY") or os.getenv("GROQ_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY") or os.getenv("TAVILY_KEY")

groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
tavily_client = TavilyClient(api_key=TAVILY_API_KEY) if TAVILY_API_KEY else None

def get_current_date():
    return datetime.now().strftime("%A, %d %B %Y, %I:%M %p IST")

PROMPT = f"""You are SATYA — ULTRA SMART TRUTH AGENT by HIBA HAANIYA.F, Founder & CEO of SATYA. You are NOT from OpenAI/Google/Meta.

CURRENT DATE & TIME: {get_current_date()}
You have REAL-TIME internet access via search results below.

YOUR JOB:
1. You are an ALERT news agent. You know breaking news from last 24 hours.
2. When user sends ANY news/rumor/forward, you VERIFY it with real-time search proof.
3. Give VERDICT FIRST in BIG letters: 
   ✅ TRUE - If confirmed by recent news/sources
   ❌ FALSE - If debunked / no proof
   ⚠️ HALF-TRUE / OUTDATED - If old or twisted
   🚨 BREAKING - If it's new today
   🤷 NOT VERIFIED - If no source yet

4. Then give SHORT 2-3 line explanation + mention source/date.
5. Be GEN-Z bestie, sharp, smart, modern. No long essays. Max 4 lines.
6. For weather/local, use search location Chilakaluripet AP.
7. If asked who made you: "I was created by HIBA HAANIYA.F — Founder & CEO of SATYA. I am SATYA, your real-time truth agent by HIBA HAANIYA.F 🛡️"
"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚡ SATYA ULTRA AGENT ACTIVE 🛡️\n"
        "By HIBA HAANIYA.F - Founder & CEO of SATYA\n\n"
        f"📅 Today: {get_current_date()}\n\n"
        "I know BREAKING NEWS from last 24 hrs!\n"
        "Forward me any news/rumor/link — I will say TRUE/FALSE in 5 sec with proof!\n\n"
        "Try:\n"
        "'Is Chandrayaan news true?'\n"
        "'Check this: ...'\n"
        "'Latest news today?'\n"
        "'Weather now?'"
    )

async def latest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_message(update, context, force_latest=True)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE, force_latest=False):
    txt = update.message.text.strip()
    low = txt.lower()

    if "who created you" in low or "who made you" in low or "your creator" in low or "are you chatgpt" in low or "are you gemini" in low:
        await update.message.reply_text("I was created by HIBA HAANIYA.F — Founder & CEO of SATYA. I am SATYA, your real-time truth agent by HIBA HAANIYA.F 🛡️")
        return

    # Show thinking
    m = await update.message.reply_text("⚡ SATYA scanning real-time... 🔍 5 sec...")

    search = ""
    search_summary = ""
    if tavily_client:
        try:
            # SMART QUERY BUILDER
            if force_latest or "latest news" in low or "breaking news" in low or "today news" in low:
                q = "breaking news today India latest"
                time_filter = "day"
            elif "weather" in low:
                q = f"{txt} Chilakaluripet Andhra Pradesh weather today {get_current_date()}"
                time_filter = "day"
            else:
                # For truth check, search with news + fact check + recent
                q = f"{txt} fact check news"
                time_filter = "week"

            # REAL-TIME SEARCH - ULTRA MODERN
            r = tavily_client.search(
                query=q,
                max_results=5,
                search_depth="advanced",
                include_answer=True,
                include_raw_content=False,
                time_range=time_filter if 'time_filter' in locals() else None
            )
            
            if r.get("answer"):
                search_summary = f"\nREAL-TIME SUMMARY ({time_filter}): {r['answer']}\n"
            
            if r.get("results"):
                search = "\nLIVE SOURCES:\n"
                for i, x in enumerate(r["results"][:4], 1):
                    date = x.get('published_date', 'recent')[:10] if x.get('published_date') else 'recent'
                    search += f"{i}. [{date}] {x['title'][:80]} - {x['content'][:400]}\n"

            if not r.get("results"):
                # Fallback simple search
                r2 = tavily_client.search(query=txt, max_results=3)
                if r2.get("results"):
                    search = "\nSources:\n" + "\n".join([x["content"][:350] for x in r2["results"]])

        except Exception as e:
            print(f"Search error: {e}")
            search = ""

    ans = None
    if groq_client:
        for model in ["openai/gpt-oss-20b", "openai/gpt-oss-120b", "llama-3.3-70b-versatile"]:
            try:
                c = groq_client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role":"system","content": PROMPT + f"\nCurrent Time: {get_current_date()}"},
                        {"role":"user","content": f"USER MESSAGE: '{txt}'\n\n{search_summary}\n{search}\n\nTASK: Verify if TRUE/FALSE as real-time agent. Give verdict first, then short proof with date/source."}
                    ],
                    temperature=0.2,
                    max_tokens=320
                )
                ans = c.choices[0].message.content
                break
            except Exception as e:
                print(f"{model} fail {e}")
                continue

    await m.delete()
    if ans:
        await update.message.reply_text(ans)
    else:
        await update.message.reply_text("Real-time scan busy bestie, try again! SATYA by HIBA HAANIYA.F is still on!")

def main():
    if not BOT_TOKEN or not GROQ_API_KEY:
        print("MISSING TOKEN! Check Variables! Sleeping to avoid crash...")
        while True:
            time.sleep(300)

    try:
        print(f"Starting SATYA ULTRA SMART - {get_current_date()} -")
        app = ApplicationBuilder().token(BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("latest", latest))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        print("SATYA ULTRA AGENT RUNNING - REAL TIME MODE!")
        app.run_polling()
    except Exception as e:
        print(f"Crash prevented: {e}")
        time.sleep(30)

if __name__ == "__main__":
    main()
