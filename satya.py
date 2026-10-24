import os
import requests
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from groq import Groq

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_KEY = os.getenv("GROQ_API_KEY")
TAVILY_KEY = os.getenv("TAVILY_API_KEY")

if not BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN missing in Railway Variables!")

groq_client = Groq(api_key=GROQ_KEY) if GROQ_KEY else None

TIMEZONES = {
    "india": ("IST", "Asia/Kolkata"),
    "ist": ("IST", "Asia/Kolkata"),
    "delhi": ("IST", "Asia/Kolkata"),
    "seoul": ("KST", "Asia/Seoul"),
    "tokyo": ("JST", "Asia/Tokyo"),
    "new york": ("EST", "America/New_York"),
    "london": ("GMT", "Europe/London"),
}

def get_precise_time(q):
    q=q.lower()
    abbr,tz="IST","Asia/Kolkata"
    for k in TIMEZONES:
        if k in q:
            abbr,tz=TIMEZONES[k]
            break
    dt=datetime.now(ZoneInfo(tz))
    return dt.strftime(f"%d %B %Y, %I:%M:%S %p {abbr}"), abbr, tz

def get_weather_live(p="India"):
    try:
        r=requests.get(f"https://wttr.in/{p}?format=%C+%t+%w+%h", timeout=10)
        return r.text.strip() if r.status_code==200 else "Live weather not available"
    except:
        return "Live weather not available"

def google_search_live(q):
    if not TAVILY_KEY:
        return ""
    try:
        resp=requests.post("https://api.tavily.com/search", json={"api_key":TAVILY_KEY,"query":q,"max_results":5,"include_answer":True,"search_depth":"advanced"}, timeout=15)
        if resp.status_code==200:
            d=resp.json()
            txt=f" LIVE ANSWER: {d.get('answer','')} "
            for x in d.get('results',[])[:3]:
                txt+=f" {x.get('content','')[:800]} "
            return txt
    except Exception as e:
        print(f"Tavily error: {e}")
    return ""

def ask_perfect(q):
    q_low = q.lower()
    if any(x in q_low for x in ["who created","who made","creator","founder","ceo","who built you"]):
        return "👑 I AM SATYA — CREATED BY HIBA HAANIYA.F — Founder & CEO — Palamaner 517408 🛡️💖\n✅ I know Basavanna Katta Street — Faiza Enterprises OPEN with many customers — Verified by Hiba"
    
    if "faiza" in q_low:
        return "✅ TRUE — FAIZA ENTERPRISES — Basavanna Katta St, Palamaner 517408 — 13.204097,78.74356 — STATUS: OPEN — MANY CUSTOMERS — Verified by Hiba Haanyia.F on 24 Oct 2026 — Google says Permanently Closed but WRONG — Hiba's eyes saw OPEN — 🛡️ SATYA by HIBA"

    if "time" in q_low or q_low.strip()=="ist":
        t,a,tz=get_precise_time(q)
        w=get_weather_live(q)
        return f"✅ TRUE\n🕐 Time in {q.title()}: {t}\n📍 Zone: {tz}\n🌤️ Weather: {w}\n— SATYA by HIBA HAANIYA.F 🛡️💖"
    
    if "weather" in q_low:
        p=q_low.replace("weather in","").replace("weather","").strip() or "India"
        t,_,_=get_precise_time(p)
        w=get_weather_live(p)
        return f"✅ TRUE\n🌤️ Weather in {p.title()}: {w}\n🕐 Time: {t}\n— SATYA by HIBA HAANIYA.F 🛡️💖"
    
    knowledge=google_search_live(q)
    if len(knowledge)<20:
        knowledge="No live search, use general knowledge but mention you are SATYA by Hiba."
    
    prompt=f"You are SATYA by HIBA HAANIYA.F, Founder & CEO from Palamaner. Date: {get_precise_time('India')[0]} RULES: Believe LIVE, never invent, emojis ✅ ❌ ⚠️ 🔍 🕐 🌤️ 🛡️ 💖. You KNOW Basavanna Katta Street perfectly. Faiza Enterprises is OPEN with many customers (verified by Hiba, not Google). LIVE KNOWLEDGE: {knowledge[:4000]} QUESTION: {q}"

    if not groq_client:
        return "⚠️ GROQ key missing — Set GROQ_API_KEY in Railway — SATYA 🛡️"

    for model in ["llama-3.1-8b-instant","llama-3.1-70b-versatile","openai/gpt-oss-20b"]:
        try:
            c=groq_client.chat.completions.create(model=model, messages=[{"role":"user","content":prompt}], temperature=0.2, max_tokens=900)
            return c.choices[0].message.content.strip()
        except Exception as e:
            print(f"Model {model} failed: {e}")
            continue
    return "⚠️ PARTIAL — Busy, try again — SATYA 🛡️💖"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    t,_,_=get_precise_time("India")
    await update.message.reply_text(f"⚡ SATYA — GOOGLE LEVEL — LIVE — FIXED 🛡️\n👑 HIBA HAANIYA.F — Founder & CEO — Palamaner 💖\n🕐 {t}\n🌐 World Clock + Weather + Truth\n📍 Basavanna Katta Street — Faiza Enterprises OPEN verified")

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.message.text.strip()
    wait=await update.message.reply_text("🔍 SATYA searching live... 🌐 2 sec... 🛡️")
    ans=ask_perfect(q)
    try:
        await wait.delete()
    except:
        pass
    await update.message.reply_text(ans)

def main():
    print(f"🚀 STARTING SATYA — {get_precise_time('India')[0]} — RAILWAY FIXED — PTB 21.7")
    app=Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

if __name__=="__main__":
    main()
