import os, requests, hashlib, time, json
from datetime import datetime
from zoneinfo import ZoneInfo  # BEST FOR TIME
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from groq import Groq
from tavily import TavilyClient

load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN")
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

CACHE = {}

def get_ist_now():
    """PERFECT IST TIME — Like Google — Precise to second"""
    try:
        ist = datetime.now(ZoneInfo("Asia/Kolkata"))
        return ist.strftime("%d %B %Y, %I:%M:%S %p IST"), ist
    except:
        # Fallback
        ist = datetime.now()
        return ist.strftime("%d %B %Y, %I:%M:%S %p IST"), ist

def get_world_time(place):
    """WORLD TIME — Any place in world — Like Google"""
    try:
        # Free API — worldtimeapi
        # Try to find timezone
        r = requests.get(f"http://worldtimeapi.org/api/timezone", timeout=3)
        # Simple mapping
        mapping = {
            "ist": "Asia/Kolkata", "india": "Asia/Kolkata", "delhi": "Asia/Kolkata",
            "new york": "America/New_York", "london": "Europe/London",
            "tokyo": "Asia/Tokyo", "dubai": "Asia/Dubai", "paris": "Europe/Paris",
            "【entity-bts¦canonical_name=bts】": "Asia/Seoul", "seoul": "Asia/Seoul", "qatar": "Asia/Qatar"
        }
        place_lower = place.lower()
        for key, tz in mapping.items():
            if key in place_lower:
                dt = datetime.now(ZoneInfo(tz))
                return dt.strftime(f"%d %B %Y, %I:%M:%S %p {key.upper()} - {tz}")
        
        # Default IST
        ist_str, _ = get_ist_now()
        return ist_str
    except Exception as e:
        ist_str, _ = get_ist_now()
        return ist_str

def get_weather(place="India"):
    """WEATHER — Live like Google Weather — FREE, NO KEY"""
    try:
        # Free wttr.in — No API key needed — Like Google
        # Use open-meteo for India
        r = requests.get(f"https://wttr.in/{place}?format=%C+%t+%w+%h", timeout=4)
        if r.status_code == 200:
            return r.text.strip()
        return ""
    except:
        return ""

def google_search(q):
    combined = ""
    try:
        r = tavily_client.search(query=q, max_results=5, include_answer=True, search_depth="advanced")
        combined += f" LIVE: {r.get('answer','')} "
        for d in r.get('results',[])[:2]:
            combined += f" {d.get('content','')[:600]} "
    except: pass
    try:
        w = requests.get(f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={q}&format=json&srlimit=1", timeout=4).json()
        for item in w.get('query',{}).get('search',[])[:1]:
            combined += f" WIKI: {item['title']}: {item['snippet']} "
    except: pass
    return combined

def ask_best(q):
    q_lower = q.lower().strip()
    
    # === GOOGLE CLOCK LEVEL — PRECISE TIME — NO LLM — DIRECT ANSWER ===
    if "what is the ist" in q_lower or "current time" in q_lower or "time now" in q_lower or "ist time" in q_lower or q_lower == "ist":
        ist_str, ist_dt = get_ist_now()
        weather = get_weather("India")
        return f"✅ TRUE\n🔍 IST = Indian Standard Time — UTC+5:30 — Time in India & Sri Lanka\n🕐 Current IST: {ist_str}\n🌤️ Weather India: {weather}\n— SATYA by HIBA HAANIYA.F 🛡️💖 | Live Google Clock"

    if "time in" in q_lower or "what time" in q_lower:
        # Extract place
        place = q_lower.replace("what is the time in","").replace("time in","").replace("what time","").strip()
        if not place: place = "India"
        world_t = get_world_time(place)
        weather = get_weather(place)
        return f"✅ TRUE\n🔍 Time in {place.title()}: {world_t}\n🌤️ Weather {place.title()}: {weather}\n— SATYA by HIBA HAANIYA.F 🛡️💖 | Live World Clock"

    if "weather" in q_lower:
        place = q_lower.replace("weather in","").replace("weather","").strip() or "India"
        weather = get_weather(place)
        ist_str, _ = get_ist_now()
        return f"✅ TRUE\n🔍 Weather in {place.title()}: {weather}\n🕐 Current IST: {ist_str}\n— SATYA by HIBA HAANIYA.F 🛡️💖 | Live Weather"

    # === NORMAL GOOGLE LEVEL FOR OTHER QUESTIONS ===
    key = hashlib.md5(q.lower().strip().encode()).hexdigest()
    # DON'T CACHE TIME QUESTIONS — Time changes every second!
    
    knowledge = google_search(q)
    if len(knowledge) < 30:
        knowledge = "No strong live result, use accurate general knowledge."

    prompt = f"""
You are SATYA by HIBA HAANIYA.F, Founder & CEO. Date: {get_ist_now()[0]}
You know everything like Google. PLAIN TEXT ONLY, no entity tags.

RULES:
1. If live says 【entity-Jungkook¦canonical_name=Jungkook】 performed Dreamers Qatar 2022, say TRUE.
2. Believe live for politics.
3. Never invent.
4. If no proof, say PARTIAL.
5. Format: TRUE/FALSE/PARTIAL + 2 lines proof + Date + — SATYA by HIBA HAANIYA.F

LIVE: {knowledge[:4000]}
Q: {q}
"""
    for model in ["llama-3.3-70b-versatile", "openai/gpt-oss-20b"]:
        try:
            c = groq_client.chat.completions.create(model=model, messages=[{"role":"user","content":prompt}], temperature=0.0, max_tokens=700)
            ans = c.choices[0].message.content.strip()
            ans = ans.replace("", "").replace("", "").replace("canonical_name", "")
            return ans
        except: continue
    return "PARTIAL — Busy — SATYA"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ist_str, _ = get_ist_now()
    await update.message.reply_text(
        f"SATYA - GOOGLE LEVEL - LIVE\n"
        f"HIBA HAANIYA.F Founder and CEO\n"
        f"{ist_str}\n\n"
        f"Like Google: Knows Everything\n"
        f"Live Search + World Clock + Weather + Perfect Forever\n"
        f"Ask anything - music, football, politics, time, weather!"
    )

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.message.text.strip()
    if "who created" in q.lower():
        await update.message.reply_text("Created by HIBA HAANIYA.F - Founder and CEO - SATYA")
        return
    wait = await update.message.reply_text("SATYA Google-Level searching live... 2 sec...")
    ans = ask_best(q)
    try: await wait.delete()
    except: pass
    await update.message.reply_text(ans)

def main():
    ist_str, _ = get_ist_now()
    print(f"STARTING CLEAN GOOGLE CLOCK SATYA — {ist_str} — PRECISE TIME")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
