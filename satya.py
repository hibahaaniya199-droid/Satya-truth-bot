import os, requests
from datetime import datetime
from zoneinfo import ZoneInfo
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from groq import Groq

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_KEY = os.getenv("GROQ_API_KEY")
TAVILY_KEY = os.getenv("TAVILY_API_KEY")
groq_client = Groq(api_key=GROQ_KEY) if GROQ_KEY else None

TIMEZONES = {
    "india": ("IST", "Asia/Kolkata"),
    "ist": ("IST", "Asia/Kolkata"),
    "delhi": ("IST", "Asia/Kolkata"),
    "south korea": ("KST", "Asia/Seoul"),
    "korea": ("KST", "Asia/Seoul"),
    "seoul": ("KST", "Asia/Seoul"),
    "japan": ("JST", "Asia/Tokyo"),
    "tokyo": ("JST", "Asia/Tokyo"),
    "new york": ("EST", "America/New_York"),
    "usa": ("EST", "America/New_York"),
    "london": ("GMT", "Europe/London"),
    "uk": ("GMT", "Europe/London"),
    "dubai": ("GST", "Asia/Dubai"),
    "qatar": ("AST", "Asia/Qatar"),
    "paris": ("CET", "Europe/Paris"),
    "australia": ("AEST", "Australia/Sydney"),
    "china": ("CST", "Asia/Shanghai"),
}

def get_precise_time(q):
    q=q.lower(); abbr,tz="IST","Asia/Kolkata"
    for k in TIMEZONES:
        if k in q: abbr,tz=TIMEZONES[k]; break
    dt=datetime.now(ZoneInfo(tz))
    return dt.strftime(f"%d %B %Y, %I:%M:%S %p {abbr}"), abbr, tz

def get_weather_live(p="India"):
    try:
        r=requests.get(f"https://wttr.in/{p}?format=%C+%t+%w+%h", timeout=10)
        return r.text.strip() if r.status_code==200 else "Live weather"
    except: return "Live weather"

def google_search_live(q):
    if not TAVILY_KEY: return ""
    try:
        resp=requests.post("https://api.tavily.com/search", json={"api_key":TAVILY_KEY,"query":q,"max_results":5,"include_answer":True,"search_depth":"advanced"}, timeout=15)
        if resp.status_code==200:
            d=resp.json(); txt=f" LIVE: {d.get('answer','')} "
            for x in d.get('results',[])[:3]: txt+=f" {x.get('content','')[:800]} "
            return txt
    except: pass
    return ""

def ask_perfect(q):
    if any(x in q.lower() for x in ["who created","who made","creator","founder","ceo"]):
        return "👑 I AM SATYA — CREATED BY HIBA HAANIYA.F — Founder & CEO 🛡️💖"
    if "time" in q.lower() or q.lower()=="ist":
        t,a,tz=get_precise_time(q); w=get_weather_live(q)
        return f"✅ TRUE\n🕐 Time in {q.title()}: {t}\n📍 Zone: {tz}\n🌤️ Weather: {w}\n— SATYA by HIBA HAANIYA.F 🛡️💖"
    if "weather" in q.lower():
        p=q.lower().replace("weather in","").replace("weather","").strip() or "India"
        t,_,_=get_precise_time(p); w=get_weather_live(p)
        return f"✅ TRUE\n🌤️ Weather in {p.title()}: {w}\n🕐 Time: {t}\n— SATYA by HIBA HAANIYA.F 🛡️💖"
    knowledge=google_search_live(q)
    if len(knowledge)<20: knowledge="No live search, use general knowledge."
    prompt=f"You are SATYA by HIBA HAANIYA.F, Founder & CEO. Date: {get_precise_time('India')[0]} RULES: Believe LIVE, never invent, emojis ✅ ❌ ⚠️ 🔍 🕐 🌤️ 🛡️ 💖 LIVE: {knowledge[:4000]} Q: {q}"
    for model in ["llama-3.1-8b-instant","openai/gpt-oss-20b","qwen/qwen3-32b"]:
        try:
            c=groq_client.chat.completions.create(model=model, messages=[{"role":"user","content":prompt}], temperature=0.2, max_tokens=900)
            return c.choices[0].message.content.strip()
        except: continue
    return "⚠️ PARTIAL — Busy, try again — SATYA 🛡️💖"

async def start(update, context):
    t,_,_=get_precise_time("India")
    await update.message.reply_text(f"⚡ SATYA — GOOGLE LEVEL — LIVE 🛡️\n👑 HIBA HAANIYA.F — Founder & CEO 💖\n🕐 {t}\n🌐 World Clock + Weather + Truth")

async def handle(update, context):
    q=update.message.text.strip()
    wait=await update.message.reply_text("🔍 SATYA searching live... 🌐 2 sec... 🛡️")
    ans=ask_perfect(q)
    try: await wait.delete()
    except: pass
    await update.message.reply_text(ans)

def main():
    print(f"🚀 STARTING SATYA — {get_precise_time('India')[0]} — RAILWAY FIXED")
    app=Application.builder().token(BOT_TOKEN).read_timeout(30).write_timeout(30).connect_timeout(30).pool_timeout(30).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

if __name__=="__main__": main()