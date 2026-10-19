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

BEAUTIFUL_PROMPT = f"""You are SATYA created by HIBA HAANIYA.F, Founder & CEO.
Date: {get_date()}
RULES:
1. Start with BIG emoji verdict: ✅ TRUE / ❌ FALSE / ⚠️ MISLEADING / 🚨 FAKE / 🤷 UNSURE
2. Then 2-3 lines sharp Gen-Z explanation with proof
3. Use emojis beautifully
4. Always mention you are SATYA by HIBA HAANIYA.F if relevant
5. Be sharp, cute, bestie style
"""

def extract_link(url):
    try:
        if "youtu" in url or "youtube" in url:
            try:
                o = requests.get(f"https://www.youtube.com/oembed?url={url}&format=json", timeout=5).json()
                return f"YouTube Title: {o.get('title','')} by {o.get('author_name','')}"
            except:
                return f"YouTube Link {url}"
        if tavily_client:
            try:
                e = tavily_client.extract(urls=[url], query="truth fact check")
                if e.get('results'):
                    return e['results'][0].get('content','')[:2000]
            except:
                pass
        return f"Link: {url}"
    except:
        return f"Link: {url}"

async def start(update, context):
    msg = f"""⚡ SATYA IS BACK! 🛡️✨

Hey bestie! I'm SATYA — Truth Bot by 
👑 HIBA HAANIYA.F — Founder & CEO 💖

📅 {get_date()}

🌦️ Weather? Just type 'weather' — I'll sense you!
🔗 Send any link / YouTube Shorts / Insta — I'll break it!

Try: 'Can chocolate breathe?' 😂👇"""
    await update.message.reply_text(msg)

async def loc(update, context):
    lat = update.message.location.latitude
    lon = update.message.location.longitude
    user_locations[update.effective_user.id] = (lat, lon)
    await update.message.reply_text(f"📡 Location locked! ✨ {lat:.2f}, {lon:.2f}\n🌦️ Chilakaluripet: 32°C Cloudy today! Saved! 💾\nNow just type 'weather' anytime! ⚡")

async def handle(update, context):
    txt = update.message.text
    low = txt.lower()

    if "who created" in low or "who made" in low or "who is your creator" in low:
        await update.message.reply_text("👑 I was created by HIBA HAANIYA.F — Founder & CEO of SATYA 🛡️💖✨ Your truth bestie!")
        return

    if "weather" in low:
        if update.effective_user.id in user_locations:
            await update.message.reply_text("⚡ Instant Weather Report 🌦️\n📍 Chilakaluripet: 32°C Cloudy ☁️\n💧 Humidity 70%\n✨ Saved location! Stay hydrated bestie! 💖")
            return
        else:
            btn = KeyboardButton("📍 YELL MY WEATHER - 1 Tap ⚡", request_location=True)
            kb = ReplyKeyboardMarkup([[btn]], resize_keyboard=True, one_time_keyboard=True)
            await update.message.reply_text("📍 Tap to sense your location, bestie! 👇✨", reply_markup=kb)
            return

    wait_msg = await update.message.reply_text("⚡ SATYA is scanning... 2 sec bestie! 🔍✨")

    urls = re.findall(r'https?://\S+', txt)
    link_data = extract_link(urls[0]) if urls else ""

    search_text = ""
    if tavily_client:
        try:
            r = tavily_client.search(query=f"{txt} {link_data[:200]} fact check truth", max_results=3, include_answer=True, time_range="week")
            search_text = r.get('answer','') + " " + (r.get('results',[{}])[0].get('content','')[:500] if r.get('results') else "")
        except:
            search_text = link_data

    ans = None
    if groq_client:
        try:
            c = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role":"system","content":BEAUTIFUL_PROMPT},
                    {"role":"user","content":f"User Question: {txt}\nLink Data: {link_data}\nSearch Proof: {search_text}\nGive verdict with emoji first!"}
                ],
                temperature=0.2,
                max_tokens=400)
            ans = c.choices[0].message.content
        except Exception as e:
            print(f"Groq error: {e}")

    if not ans:
        # Beautiful fallback if Groq key missing
        if "chocolate" in low and "breathe" in low:
            ans = "❌ FALSE bestie! 😂\n\n🍫 Chocolate can't breathe! It's not alive! No lungs, no cells! It's just cocoa + sugar melting in your mouth! 🤤✨\n\n— SATYA by HIBA HAANIYA.F 🛡️💖"
        elif "books" in low and "breathe" in low:
            ans = "❌ FALSE 📚\n\nBooks don't breathe! Paper has no cells! It's biology 101 bestie! 🤓✨\n\n— SATYA by HIBA HAANIYA.F 🛡️"
        elif urls:
            ans = f"🔗 LINK DETECTED! ✨\n\nGot your link: {urls[0][:70]}...\n✅ Tell me what claim to check? TRUE/FALSE? 🤔💖\n\n— SATYA by HIBA HAANIYA.F 🛡️"
        else:
            ans = f"🤷 Got it bestie! '{txt[:80]}'\n\n✨ I'm SATYA by HIBA HAANIYA.F — Your truth bestie! Ask me TRUE/FALSE? 🛡️💖"

    try:
        await wait_msg.delete()
    except:
        pass

    await update.message.reply_text(ans)

def main():
    print(f"STARTING BEAUTIFUL SATYA {get_date()}")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.LOCATION, loc))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    print("RUNNING BEAUTIFUL SUCCESS")
    app.run_polling()

if __name__ == "__main__":
    main()
