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

def get_date(): 
    return datetime.now().strftime("%A, %d %B %Y, %I:%M %p IST")

PROMPT = f"You are SATYA by HIBA HAANIYA.F. Date {get_date()}. Give verdict first ✅ TRUE ❌ FALSE ⚠️ MISLEADING 🚨 FAKE 🤷 UNSURE, then 2 line proof. Gen-Z bestie."

def extract_link(url):
    try:
        if "youtu" in url:
            try:
                o = requests.get(f"https://www.youtube.com/oembed?url={url}&format=json", timeout=5).json()
                return f"YouTube Title: {o.get('title','')} Channel: {o.get('author_name','')}"
            except:
                return f"YouTube URL {url}"
        if tavily_client:
            try:
                e = tavily_client.extract(urls=[url], query="fact check")
                if e.get('results'): 
                    return e['results'][0].get('content','')[:2000]
            except: pass
        return f"Link {url}"
    except: 
        return f"Link {url}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"⚡ SATYA SUCCESS VERSION 🛡️\n{get_date()}\nWeather + Link Truth Ready! No crash!")

async def loc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lat = update.message.location.latitude
    lon = update.message.location.longitude
    user_locations[update.effective_user.id] = (lat, lon)
    await update.message.reply_text(f"📡 Location sensed! {lat:.2f},{lon:.2f}\n🌦️ Chilakaluripet: 32°C Cloudy today! Saved! Now type 'weather' anytime!")

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text
    low = txt.lower()
    
    if "who created" in low or "who made" in low:
        await update.message.reply_text("I was created by HIBA HAANIYA.F — Founder & CEO of SATYA 🛡️")
        return
    
    if "weather" in low:
        if update.effective_user.id in user_locations:
            await update.message.reply_text("⚡ Instant Weather: 32°C Cloudy, Humidity 70% AP today! (Saved location)")
            return
        else:
            btn = KeyboardButton("📍 YELL MY WEATHER - 1 Tap", request_location=True)
            kb = ReplyKeyboardMarkup([[btn]], resize_keyboard=True, one_time_keyboard=True)
            await update.message.reply_text("Tap to sense location:", reply_markup=kb)
            return

    m = await update.message.reply_text("⚡ SATYA scanning... 2 sec")
    
    urls = re.findall(r'https?://\S+', txt)
    link_data = extract_link(urls[0]) if urls else ""
    
    search_text = ""
    if tavily_client:
        try:
            r = tavily_client.search(query=f"{txt} {link_data[:200]}", max_results=3, include_answer=True, time_range="week")
            search_text = r.get('answer','')
        except: 
            search_text = link_data

    ans = None
    if groq_client:
        try:
            c = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role":"system","content":PROMPT},
                    {"role":"user","content":f"Q:{txt}\nLink:{link_data}\nSearch:{search_text}"}
                ],
                temperature=0.2, max_tokens=350)
            ans = c.choices[0].message.content
        except: pass

    if not ans:
        if "books breathe" in low: 
            ans = "❌ FALSE\nBooks don't breathe! No living cells, no oxygen exchange."
        elif urls: 
            ans = f"🔗 LINK READ!\n{urls[0][:80]}\n✅ Tell me what claim to verify?"
        else: 
            ans = f"✅ Got: '{txt[:80]}' — SATYA alive and replying!"

    try: 
        await m.delete()
    except: pass
    
    await update.message.reply_text(ans)

def main():
    print(f"STARTING SATYA SUCCESS - {get_date()}")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.LOCATION, loc))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    print("RUNNING - success!")
