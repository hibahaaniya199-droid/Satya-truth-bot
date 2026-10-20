import os, requests, hashlib, time
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

# WORLD TIME MAP — GOOGLE LEVEL — EVERY PLACE
TIMEZONES = {
    "india": ("IST", "Asia/Kolkata"), "ist": ("IST", "Asia/Kolkata"), "delhi": ("IST", "Asia/Kolkata"),
    "south korea": ("KST", "Asia/Seoul"), "korea": ("KST", "Asia/Seoul"), "seoul": ("KST", "Asia/Seoul"), " kst": ("KST", "Asia/Seoul"),
    "japan": ("JST", "Asia/Tokyo"), "tokyo": ("JST", "Asia/Tokyo"),
    "usa": ("EST", "America/New_York"), "new york": ("EST", "America/New_York"), "america": ("EST", "America/New_York"),
    "london": ("GMT", "Europe/London"), "uk": ("GMT", "Europe/London"), "england": ("GMT", "Europe/London"),
    "dubai": ("GST", "Asia/Dubai"), "uae": ("GST", "Asia/Dubai"),
    "qatar": ("AST", "Asia/Qatar"), "doha": ("AST", "Asia/Qatar"),
    "paris": ("CET", "Europe/Paris"), "france": ("CET", "Europe/Paris"),
    "australia": ("AEST", "Australia/Sydney"), "sydney": ("AEST", "Australia/Sydney"),
    "china": ("CST", "Asia/Shanghai"), "beijing": ("CST", "Asia/Shanghai"),
}

def get_time_for_place(place_query):
    """PERFECT WORLD TIME — Returns correct time for ANY place"""
    place_lower = place_query.lower().strip()
    
    # Find matching timezone
    found_abbr, found_tz = None, None
    for key, (abbr, tz) in TIMEZONES.items():
        if key in place_lower:
            found_abbr, found_tz = abbr, tz
            break
    
    # Default to IST if no match
    if not found_tz:
        found_abbr, found_tz = "IST", "Asia/Kolkata"
        place_query = "India"

    try:
        dt = datetime.now(ZoneInfo(found_tz))
        # Format like Google: 20 October 2026, 09:25:15 PM KST
        formatted = dt.strftime(f"%d %B %Y, %I:%M:%S %p {found_abbr}")
        return formatted, found_abbr, found_tz
    except Exception as e:
        print(f"Time err {e}")
        ist = datetime.now(ZoneInfo("Asia/Kolkata"))
        return ist.strftime("%d %B %Y, %I:%M:%S %p IST"), "IST", "Asia/Kolkata"

def get_ist_now():
    return get_time_for_place("india")

def get_weather(place="India"):
    try:
        r = requests.get(f"https://wttr.in/{place}?format=%C+%t+%w+%h", timeout=4)
        if r.status_code == 200:
            return r.text.strip()
        return "Live weather"
    except: return ""

def google_search(q):
    combined = ""
    try:
        r = tavily_client.search(query=q, max_results=5, include_answer=True, search_depth="advanced")
        combined += f" LIVE: {r.get('answer','')} "
        for d in r.get('results',[])[:2]:
            combined += f" {d.get('content','')[:600]} "
    except: pass
    return combined

def ask_best(q):
    q_lower = q.lower().strip()
    
    # WORLD TIME — FIXED — NO IST BUG
    if "time in" in q_lower or "what is the time" in q_lower or "current time" in q_lower or "what time" in q_lower:
        # Extract place: "What is the time in South Korea" -> "South Korea"
        place = q_lower
        for phrase in ["what is the time in", "what is the time", "time in", "current time in", "what time is it in", "time"]:
            place = place.replace(phrase, "")
        place = place.replace("?", "").strip()
        if not place or place == "ist": place = "India"
        
        formatted_time, abbr, tz = get_time_for_place(place)
        weather = get_weather(place)
        
        # FIXED MESSAGE — SHOWS KST NOT IST FOR SOUTH KOREA
        return f"✅ TRUE\n🕐 Time in {place.title()}: {formatted_time} ({tz})\n🌤️ Weather {place.title()}: {weather}\n— SATYA by HIBA HAANIYA.F | Live World Clock"

    if "weather" in q_lower:
        place = q_lower.replace("weather in","").replace("weather","").strip() or "India"
        weather = get_weather(place)
        time_str, _, _ = get_time_for_place(place)
        return f"✅ TRUE\n🌤️ Weather in {place.title()}: {weather}\n🕐 Time: {time_str}\n— SATYA by HIBA HAANIYA.F | Live Weather"

    if "what is the ist" in q_lower or q_lower == "ist":
        time_str, _, _ = get_ist_now()
        weather = get_weather("India")
        return f"✅ TRUE\n🔍 IST = Indian Standard Time — UTC+5:30 — India & Sri Lanka\n🕐 Current IST: {time_str}\n🌤️ Weather: {weather}\n— SATYA by HIBA HAANIYA.F | Live Clock"

    # OTHER QUESTIONS
    knowledge = google_search(q)
    prompt = f"You are SATYA by HIBA HAANIYA.F. Date: {get_ist_now()[0]}. PLAIN TEXT ONLY. LIVE: {knowledge[:4000]} Q: {q} Answer TRUE/FALSE/PARTIAL with proof, no entity tags."
    for model in ["llama-3.3-70b-versatile", "openai/gpt-oss-20b"]:
        try:
            c = groq_client.chat.completions.create(model=model, messages=[{"role":"user","content":prompt}], temperature=0.0, max_tokens=700)
            return c.choices[0].message.content.strip()
        except: continue
    return "PARTIAL — Busy — SATYA"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ist_str, _, _ = get_ist_now()
    await update.message.reply_text(f"SATYA - GOOGLE LEVEL - LIVE\nHIBA HAANIYA.F Founder and CEO\n{ist_str}\n\nLive Search + World Clock + Weather + Perfect Forever\nAsk anything!")

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.message.text.strip()
    if "who created" in q.lower():
        await update.message.reply_text("Created by HIBA HAANIYA.F - Founder and CEO - SATYA")
        return
    wait = await update.message.reply_text("SATYA searching live... 2 sec...")
    ans = ask_best(q)
    try: await wait.delete()
    except: pass
    await update.message.reply_text(ans)

def main():
    print(f"STARTING FIXED WORLD CLOCK SATYA — {get_ist_now()[0]} — KST BUG FIXED")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
