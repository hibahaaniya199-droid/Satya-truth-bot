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
WEATHER_KEY = os.getenv("OPENWEATHER_API_KEY")  # Optional

groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
tavily_client = TavilyClient(api_key=TAVILY_API_KEY) if TAVILY_API_KEY else None
user_locations = {}

def get_date(): return datetime.now().strftime("%A, %d %B %Y, %I:%M %p IST")

def get_weather_forecast(lat, lon):
    # FREE weather - No API key needed - Open-Meteo
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,weather_code,wind_speed_10m,relative_humidity_2m&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,weathercode&timezone=auto&forecast_days=3"
        r = requests.get(url, timeout=8).json()
        cur = r.get('current',{})
        daily = r.get('daily',{})
        temp = cur.get('temperature_2m','?')
        hum = cur.get('relative_humidity_2m','?')
        wind = cur.get('wind_speed_10m','?')
        tomorrow_max = daily.get('temperature_2m_max',[None])[0]
        tomorrow_min = daily.get('temperature_2m_min',[None])[0]
        rain_chance = daily.get('precipitation_probability_max',[0])[0]
        return f"Current: {temp}°C, Humidity {hum}%, Wind {wind} km/h. Tomorrow: {tomorrow_min}-{tomorrow_max}°C, Rain chance {rain_chance}%. Forecast 3 days available."
    except Exception as e:
        return f"Weather API error {e}"

def extract_any_link(url):
    # Reads ANY link - website, Insta, YouTube, news - via Tavily + oEmbed
    content = ""
    try:
        if "youtu.be" in url or "youtube.com" in url or "youtu" in url:
            try:
                o = requests.get(f"https://www.youtube.com/oembed?url={url}&format=json", timeout=6).json()
                content += f"YouTube: Title={o.get('title')} Author={o.get('author_name')} "
            except: pass
        if tavily_client:
            try:
                e = tavily_client.extract(urls=[url], query="fact check truth", extract_depth="advanced")
                if e.get('results'):
                    content += e['results'][0].get('content','')[:3000]
                    return content
            except: pass
        # Fallback simple fetch
        try:
            h = {"User-Agent":"Mozilla/5.0"}
            r = requests.get(url, headers=h, timeout=8)
            content += r.text[:3000]
        except: pass
    except: pass
    return content[:3000] if content else f"Link: {url}"

PERFECT_PROMPT = f"""You are SATYA - Perfect Truth Bot by HIBA HAANIYA.F Founder & CEO. Date {get_date()}

YOU MUST:
1. Answer ANYTHING - Not just coded questions. You are AGI-level sharp.
2. Start with verdict emoji: ✅ TRUE / ❌ FALSE / ⚠️ PARTIALLY TRUE / 🚨 FAKE / 🤷 UNSURE / ☀️ WEATHER / 🔗 LINK ANALYSIS
3. Then sharp 3-4 lines: proof, source, why.
4. If link/website provided: read it, summarize, say if trustworthy or not, check claims.
5. If weather asked: use provided forecast data, tell if sunny/rain tomorrow, with numbers.
6. If user asks normal question (Can humans breathe?): answer scientifically correct, not dumb fallback.
7. Always beautiful emojis, Gen-Z bestie, but super sharp and updated.
8. End with — SATYA by HIBA HAANIYA.F 🛡️💖

You have real-time search and weather data provided. Use it.
"""

async def start(update, context):
    await update.message.reply_text(f"""⚡ SATYA — PERFECT TRUTH BOT 🛡️✨

👑 Created by HIBA HAANIYA.F — Founder & CEO 💖

📅 {get_date()}

✨ I can now:
🔗 Read ANY link, website, YouTube, Insta
🌦️ Tell weather NOW + Forecast — Will it rain? Sunny?
🧠 Answer ANYTHING — True/False in seconds!

Send link or question bestie! 👇""")

async def loc(update, context):
    lat = update.message.location.latitude
    lon = update.message.location.longitude
    user_locations[update.effective_user.id] = (lat, lon)
    forecast = get_weather_forecast(lat, lon)
    await update.message.reply_text(f"📡 Location locked! {lat:.2f}, {lon:.2f} ✨\n\n🌦️ {forecast}\n\n💾 Saved! Now ask 'Will it rain tomorrow?' ⚡")

async def handle(update, context):
    txt = update.message.text
    low = txt.lower()
    
    if "who created" in low or "who made" in low:
        await update.message.reply_text("👑 I was created by HIBA HAANIYA.F — Founder & CEO of SATYA 🛡️💖 The perfect truth bot!")
        return

    # Weather intent - uses saved location
    is_weather = any(w in low for w in ["weather","rain","sunny","forecast","temperature","humidity","will it rain","will it be sunny"])
    latlon = user_locations.get(update.effective_user.id)
    
    if is_weather:
        if not latlon:
            btn = KeyboardButton("📍 Share Location for Forecast ⚡", request_location=True)
            kb = ReplyKeyboardMarkup([[btn]], resize_keyboard=True, one_time_keyboard=True)
            await update.message.reply_text("📍 Share location to get PERFECT forecast! 👇", reply_markup=kb)
            return
        # Has location
        forecast = get_weather_forecast(latlon[0], latlon[1])
        # Ask Groq to make it beautiful
        prompt_weather = f"User location {latlon} Forecast data: {forecast} Question: {txt}. Tell if sunny/rain tomorrow, sharp with emojis."
        if groq_client:
            try:
                c = groq_client.chat.completions.create(model="llama-3.3-70b-versatile",
                    messages=[{"role":"system","content":PERFECT_PROMPT},{"role":"user","content":prompt_weather}], temperature=0.2, max_tokens=400)
                await update.message.reply_text(c.choices[0].message.content)
                return
            except: pass
        await update.message.reply_text(f"🌦️ Weather Report:\n{forecast}\n— SATYA by HIBA HAANIYA.F 🛡️")
        return

    wait = await update.message.reply_text("⚡ SATYA perfect scanning... Reading everything! 🔍✨")

    urls = re.findall(r'https?://\S+', txt)
    link_data = ""
    if urls:
        link_data = "\n".join([extract_any_link(u) for u in urls[:2]])  # Read up to 2 links

    search_data = ""
    if tavily_client:
        try:
            r = tavily_client.search(query=txt[:200], max_results=5, include_answer=True, search_depth="advanced", time_range="week")
            search_data = r.get('answer','') + " " + " ".join([x.get('content','')[:600] for x in r.get('results',[])[:2]])
        except: pass

    # PERFECT ANSWER - ANYTHING
    if groq_client:
        try:
            full_prompt = f"User Q: {txt}\nLink Content: {link_data[:3000]}\nLive Search: {search_data[:3000]}\nAnswer ANYTHING sharply with verdict emoji first!"
            c = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role":"system","content":PERFECT_PROMPT},{"role":"user","content":full_prompt}],
                temperature=0.2, max_tokens=600)
            ans = c.choices[0].message.content
            await wait.delete()
            await update.message.reply_text(ans)
            return
        except Exception as e:
            print(f"Groq error: {e}")
            await wait.delete()
            await update.message.reply_text(f"⚠️ Groq key error: {e}\n\nGo to Railway → Variables → Check GROQ_API_KEY is valid! Get new from console.groq.com\n\n— SATYA by HIBA HAANIYA.F 🛡️")
            return

    await wait.delete()
    await update.message.reply_text("❌ Groq API key missing! Add GROQ_API_KEY in Railway Variables! — SATYA by HIBA HAANIYA.F 🛡️")

def main():
    print(f"STARTING PERFECT SATYA {get_date()}")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.LOCATION, loc))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    print("RUNNING PERFECT SUCCESS")
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
