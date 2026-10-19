import os, re, requests
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from groq import Groq
from tavily import TavilyClient

load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
tavily_client = TavilyClient(api_key=TAVILY_API_KEY) if TAVILY_API_KEY else None
user_locations = {}

def get_date(): return datetime.now().strftime("%A, %d %B %Y, %I:%M %p IST")

def get_weather(lat, lon):
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,wind_speed_10m&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max&timezone=auto&forecast_days=3"
        r = requests.get(url, timeout=8).json()
        cur = r.get('current',{})
        daily = r.get('daily',{})
        return f"Now {cur.get('temperature_2m')}C, Hum {cur.get('relative_humidity_2m')}%, Wind {cur.get('wind_speed_10m')}km/h. Tomorrow {daily.get('temperature_2m_min',[0])[0]}-{daily.get('temperature_2m_max',[0])[0]}C Rain {daily.get('precipitation_probability_max',[0])[0]}%"
    except: return "Weather data error"

def extract_link(url):
    try:
        if "youtu" in url:
            o = requests.get(f"https://www.youtube.com/oembed?url={url}&format=json", timeout=6).json()
            return f"YouTube Title {o.get('title')} "
    except: pass
    if tavily_client:
        try:
            e = tavily_client.extract(urls=[url], query="truth", extract_depth="advanced")
            if e.get('results'): return e['results'][0].get('content','')[:3500]
        except: pass
    return f"Link {url}"

PROMPT = "You are SATYA by HIBA HAANIYA.F Founder & CEO. Date " + get_date() + ". Answer ANYTHING. Start with verdict emoji: ✅ TRUE / ❌ FALSE / ⚠️ PARTIAL / 🚨 FAKE / ☀️ WEATHER / 🔗 LINK. Then 3 lines proof with emojis. End with — SATYA by HIBA HAANIYA.F 🛡️💖"

def ask_groq(question):
    if not groq_client:
        return None
    # FIXED MODELS - These 100% exist on Groq in 2026
    models = ["llama-3.1-8b-instant", "llama-3.1-70b-versatile", "mixtral-8x7b-32768", "gemma2-9b-it"]
    for m in models:
        try:
            c = groq_client.chat.completions.create(
                model=m,
                messages=[{"role":"system","content":PROMPT},{"role":"user","content":question}],
                temperature=0.2, max_tokens=700
            )
            print(f"Model {m} success")
            return c.choices[0].message.content
        except Exception as e:
            print(f"Model {m} failed: {e}")
            continue
    return None

async def start(update, context):
    await update.message.reply_text(f"⚡ SATYA PERFECT FIXED! 🛡️\n👑 HIBA HAANIYA.F Founder & CEO 💖\n📅 {get_date()}\n🔗 Any link + 🌦️ Forecast + 🧠 Anything!")

async def loc(update, context):
    lat = update.message.location.latitude
    lon = update.message.location.longitude
    user_locations[update.effective_user.id] = (lat, lon)
    wf = get_weather(lat, lon)
    await update.message.reply_text(f"📡 Saved {lat:.2f},{lon:.2f}\n🌦️ {wf}")

async def handle(update, context):
    txt = update.message.text
    low = txt.lower()
    if "who created" in low:
        await update.message.reply_text("👑 Created by HIBA HAANIYA.F Founder & CEO of SATYA 🛡️💖")
        return
    if any(w in low for w in ["weather","rain","sunny","forecast","will it"]):
        if update.effective_user.id not in user_locations:
            btn = KeyboardButton("📍 Share Location ⚡", request_location=True)
            kb = ReplyKeyboardMarkup([[btn]], resize_keyboard=True, one_time_keyboard=True)
            await update.message.reply_text("Share location for forecast:", reply_markup=kb)
            return
        lat,lon = user_locations[update.effective_user.id]
        wf = get_weather(lat, lon)
        ans = ask_groq(f"Weather data: {wf} Q: {txt}")
        await update.message.reply_text(ans or f"🌦️ {wf}\n— SATYA by HIBA HAANIYA.F 🛡️")
        return

    wait = await update.message.reply_text("⚡ Perfect SATYA scanning... 🔍")
    urls = re.findall(r'https?://\S+', txt)
    link_data = extract_link(urls[0]) if urls else ""
    search_data = ""
    if tavily_client:
        try:
            r = tavily_client.search(query=txt[:200], max_results=3, include_answer=True)
            search_data = r.get('answer','')
        except: pass

    full_q = f"Q: {txt}\nLink: {link_data[:2500]}\nSearch: {search_data[:1500]}"
    ans = ask_groq(full_q)
    try: await wait.delete()
    except: pass
    if ans:
        await update.message.reply_text(ans)
    else:
        await update.message.reply_text("❌ All Groq models failed. Check Railway Deploy Logs. — SATYA by HIBA HAANIYA.F 🛡️")

def main():
    print(f"STARTING PERFECT FIXED {get_date()}")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.LOCATION, loc))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    print("RUNNING PERFECT FIXED SUCCESS")
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
