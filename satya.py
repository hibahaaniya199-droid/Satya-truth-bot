import os
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from groq import Groq
from tavily import TavilyClient

load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN")
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

# 🌍 WORLD TIME MAP — FIXED — EACH ON NEW LINE — NO SYNTAX ERROR
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

def get_precise_time(place_query):
    q = place_query.lower().strip()
    abbr = "IST"
    tz = "Asia/Kolkata"
    for key in TIMEZONES:
        if key in q:
            abbr, tz = TIMEZONES[key]
            break
    try:
        dt = datetime.now(ZoneInfo(tz))
        formatted = dt.strftime(f"%d %B %Y, %I:%M:%S %p {abbr}")
        return formatted, abbr, tz
    except:
        dt = datetime.now(ZoneInfo("Asia/Kolkata"))
        return dt.strftime("%d %B %Y, %I:%M:%S %p IST"), "IST", "Asia/Kolkata"

def get_weather_live(place="India"):
    try:
        r = requests.get(f"https://wttr.in/{place}?format=%C+%t+%w+%h", timeout=5)
        if r.status_code == 200:
            return r.text.strip()
        return "Live weather"
    except:
        return "Live weather"

def google_search_live(q):
    combined = ""
    try:
        r = tavily_client.search(query=q, max_results=5, include_answer=True, search_depth="advanced")
        combined += f" LIVE: {r.get('answer','')} "
        for d in r.get('results',[])[:2]:
            combined += f" {d.get('content','')[:600]} "
    except:
        pass
    return combined

def ask_perfect(q):
    q_low = q.lower().strip()

    if "time in" in q_low or "what is the time" in q_low or "current time" in q_low or "what time" in q_low or q_low == "ist":
        place = q_low
        for p in ["what is the time in", "what is the time", "time in", "current time in", "what time", "time", "?", "ist"]:
            place = place.replace(p, "")
        place = place.strip() or "India"
        t_str, abbr, tz = get_precise_time(place)
        weather = get_weather_live(place)
        return f"✅ TRUE\n🕐 Time in {place.title()}: {t_str}\n📍 Zone: {tz}\n🌤️ Weather: {weather}\n— SATYA by HIBA HAANIYA.F 🛡️💖 | 🌐 Live World Clock"

    if "weather" in q_low:
        place = q_low.replace("weather in", "").replace("weather", "").strip() or "India"
        weather = get_weather_live(place)
        t_str, _, _ = get_precise_time(place)
        return f"✅ TRUE\n🌤️ Weather in {place.title()}: {weather}\n🕐 Time: {t_str}\n— SATYA by HIBA HAANIYA.F 🛡️💖"

    knowledge = google_search_live(q)
    if len(knowledge) < 20:
        knowledge = "No live search, use accurate general knowledge."

    prompt = f"""
You are SATYA by HIBA HAANIYA.F, Founder & CEO. Date: {get_precise_time('India')[0]}
You know everything like Google. Plain text only.

RULES:
1. Believe LIVE knowledge.
2. Never invent.
3. If no proof, say PARTIAL, never FALSE without proof.
4. Use emojis ✅ ❌ ⚠️ 🔍 🕐 🌤️ 🛡️ 💖

LIVE: {knowledge[:4000]}
Q: {q}
"""
    for model in ["llama-3.3-70b-versatile", "openai/gpt-oss-20b"]:
        try:
            c = groq_client.chat.completions.create(model=model, messages=[{"role":"user","content":prompt}], temperature=0.0, max_tokens=750)
            return c.choices[0].message.content.strip()
        except:
            continue
    return "⚠️ PARTIAL — Busy, try again — SATYA 🛡️💖"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    t_str, _, _ = get_precise_time("India")
    await update.message.reply_text(
        f"⚡ SATYA — GOOGLE LEVEL — LIVE 🛡️\n"
        f"👑 HIBA HAANIYA.F — Founder & CEO 💖\n"
        f"🕐 {t_str}\n\n"
        f"🌐 Knows Everything 🔍\n"
        f"🕐 World Clock + 🌤️ Weather + ✅ No Lie\n"
        f"💬 Ask anything — music 🎤 football ⚽ politics 🏛️ time 🕐 weather 🌤️"
    )

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.message.text.strip()
    if "who created" in q.lower():
        await update.message.reply_text("👑 Created by HIBA HAANIYA.F — Founder & CEO — SATYA 🛡️💖")
        return
    wait = await update.message.reply_text("🔍 SATYA searching live... 🌐 2 sec... 🛡️")
    ans = ask_perfect(q)
    try:
        await wait.delete()
    except:
        pass
    await update.message.reply_text(ans)

def main():
    t_str, _, _ = get_precise_time("India")
    print(f"🚀 STARTING FIXED SATYA — {t_str} — NO SYNTAX ERROR — KST FIXED")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
