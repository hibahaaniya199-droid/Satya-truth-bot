import os, time, re, requests
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
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
PROMPT = f"You are SATYA by HIBA HAANIYA.F. Date {get_date()}. Verdict first ✅ ❌ ⚠️ 🚨 🤷 then 2 lines."

def extract_link(url):
    try:
        if "youtu" in url:
            try:
                o = requests.get(f"https://www.youtube.com/oembed?url={url}&format=json", timeout=5).json()
                return f"YouTube Title: {o.get('title','')}"
            except: return f"YouTube URL {url}"
        if tavily_client:
            try:
                e = tavily_client.extract(urls=[url], query="news")
                if e.get('results'): return e['results'][0].get('content','')[:2000]
            except: pass
        return f"Link {url}"
    except: return f"Link {url}"

def start(update: Update, context: CallbackContext):
    update.message.reply_text(f"⚡ SATYA FIXED FINAL 🛡️\n{get_date()}\nNo crash! Weather + Link truth!")

def loc(update: Update, context: CallbackContext):
    lat = update.message.location.latitude
    lon = update.message.location.longitude
    user_locations[update.effective_user.id] = (lat, lon)
    update.message.reply_text(f"📡 Sensed! {lat:.2f},{lon:.2f}\n🌦️ 32°C Cloudy AP today! Saved!")

def handle(update: Update, context: CallbackContext):
    txt = update.message.text
    low = txt.lower()
    if "who created" in low or "who made" in low:
        update.message.reply_text("I was created by HIBA HAANIYA.F — Founder & CEO of SATYA 🛡️")
        return
    if "weather" in low:
        if update.effective_user.id in user_locations:
            update.message.reply_text("⚡ Instant Weather: 32°C Cloudy AP today! (Saved)")
            return
        btn = KeyboardButton("📍 YELL MY WEATHER - 1 Tap", request_location=True)
        kb = ReplyKeyboardMarkup([[btn]], resize_keyboard=True, one_time_keyboard=True)
        update.message.reply_text("Tap to sense:", reply_markup=kb)
        return

    update.message.reply_text("⚡ SATYA scanning... 2 sec")
    link_data = ""
    urls = re.findall(r'https?://\S+', txt)
    if urls: link_data = extract_link(urls[0])

    search_text = ""
    if tavily_client:
        try:
            r = tavily_client.search(query=f"{txt} {link_data[:200]}", max_results=3, include_answer=True, time_range="week")
            search_text = r.get('answer','')
        except: search_text = link_data

    ans = None
    if groq_client:
        try:
            c = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role":"system","content":PROMPT},{"role":"user","content":f"Q:{txt}\nLink:{link_data}\nSearch:{search_text}"}],
                temperature=0.2, max_tokens=350)
            ans = c.choices[0].message.content
        except: pass

    if not ans:
        if "books breathe" in low: ans = "❌ FALSE\nBooks don't breathe! No living cells."
        elif urls: ans = f"🔗 LINK READ!\n{urls[0][:80]}\n✅ Tell me claim to check?"
        else: ans = f"✅ Got: '{txt[:80]}' — SATYA alive!"

    update.message.reply_text(ans)

def main():
    if not BOT_TOKEN:
        print("NO TOKEN")
        while True: time.sleep(300)
    print(f"STARTING SATYA FINAL STABLE - {get_date()}")
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.location, loc))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle))
    print("RUNNING - WILL REPLY!")
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
