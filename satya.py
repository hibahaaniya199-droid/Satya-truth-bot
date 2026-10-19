import os
import time
import re
import requests
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from groq import Groq
from tavily import TavilyClient
from bs4 import BeautifulSoup

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN") or os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY") or os.getenv("GROQ_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY") or os.getenv("TAVILY_KEY")

groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
tavily_client = TavilyClient(api_key=TAVILY_API_KEY) if TAVILY_API_KEY else None

# SAVE USER LOCATIONS - FOR 1-SEC WEATHER
user_locations = {}

def get_current_date():
    return datetime.now().strftime("%A, %d %B %Y, %I:%M %p IST")

PROMPT = f"""You are SATYA — ULTRA SMART TRUTH AGENT by HIBA HAANIYA.F, Founder & CEO of SATYA. You are NOT from OpenAI/Google/【entity-Meta¦canonical_name=Meta】.

CURRENT DATE & TIME: {get_current_date()}
You have REAL-TIME internet access via search results below.

YOUR JOB:
1. You are an ALERT news agent. You know breaking news from last 24 hours.
2. When user sends ANY news/rumor/forward/link, you VERIFY it with real-time search proof.
3. Give VERDICT FIRST in BIG letters: 
   ✅ TRUE - If confirmed by recent news/sources
   ❌ FALSE - If debunked / no proof
   ⚠️ HALF-TRUE / OUTDATED - If old or twisted
   🚨 BREAKING - If it's new today
   🤷 NOT VERIFIED - If no source yet

4. Then give SHORT 2-3 line explanation + mention source/date.
5. Be GEN-Z bestie, sharp, smart, modern. No long essays. Max 4 lines.
6. If user shares location, give WEATHER REPORT like a pro weather agent.
7. If asked who made you: "I was created by HIBA HAANIYA.F — Founder & CEO of SATYA. I am SATYA, your real-time truth agent by HIBA HAANIYA.F 🛡️"
"""

def extract_link_content(url):
    """SHARP LINK READER - Works for YouTube Shorts, 【entity-Instagram¦canonical_name=Instagram】, Any Local Link"""
    try:
        # YouTube Shorts - Use oEmbed (100% works, never crashes)
        if "youtube.com" in url or "youtu.be" in url:
            try:
                oembed = requests.get(f"https://www.youtube.com/oembed?url={url}&format=json", timeout=5).json()
                title = oembed.get('title','')
                author = oembed.get('author_name','')
                return f"YouTube Video: Title='{title}' Channel='{author}' URL={url}. Extracted for fact-check."
            except:
                return f"YouTube Link: {url} - Title not extracted but link is valid. Fact-check the claim."

        # 【entity-Instagram¦canonical_name=Instagram】 / Any Website - Tavily Extract (BEST) + Fallback BeautifulSoup
        if tavily_client:
            try:
                ext = tavily_client.extract(urls=[url], query="what is this news about", extract_depth="advanced")
                if ext.get('results'):
                    content = ext['results'][0].get('content','')[:2000]
                    title = ext['results'][0].get('title','')
                    return f"EXTRACTED LINK CONTENT: Title='{title}' Content='{content}' URL={url}"
            except Exception as e:
                print(f"Tavily extract fail: {e}")

        # Fallback - BeautifulSoup for local news links
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=8)
        soup = BeautifulSoup(r.text, 'html.parser')
        title = soup.title.string[:200] if soup.title else ""
        paras = " ".join([p.get_text() for p in soup.find_all('p')[:5]])[:1500]
        return f"LINK CONTENT: Title='{title}' Text='{paras}' URL={url}"

    except Exception as e:
        print(f"Link extract error: {e}")
        return f"Link: {url} - Could not extract full text (private/blocked). Fact-check based on URL and user claim."

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚡ SATYA ULTRA AGENT ACTIVE 🛡️\n"
        "By HIBA HAANIYA.F - Founder & CEO of SATYA\n\n"
        f"📅 Today: {get_current_date()}\n\n"
        "I know BREAKING NEWS from last 24 hrs!\n"
        "✅ Weather: Just say 'weather' - I'll sense location in 1 tap!\n"
        "✅ Links: Send ANY YouTube/Instagram/Website link - I'll tell TRUE/FALSE!\n"
        "✅ Forward: Forward any rumor - I'll verify!\n\n"
        "Try:\n"
        "'weather'\n"
        "'https://youtube.com/shorts/...'\n"
        "'Is this true? ...'"
    )

async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """SHARP WEATHER - SENSES LOCATION IN SECONDS"""
    try:
        user_id = update.effective_user.id
        lat = update.message.location.latitude
        lon = update.message.location.longitude
        user_locations[user_id] = (lat, lon)

        m = await update.message.reply_text("📡 SATYA sensed your location! Yelling weather report in 1 sec... 🔍")

        # REAL-TIME WEATHER SEARCH via Tavily - SHARP
        weather_query = f"weather report {lat} {lon} Chilakaluripet Andhra Pradesh today {get_current_date()} temperature"
        search_text = ""
        if tavily_client:
            try:
                r = tavily_client.search(query=weather_query, max_results=3, time_range="day", include_answer=True)
                if r.get('answer'):
                    search_text = r['answer']
                if r.get('results'):
                    search_text += "\n" + r['results'][0]['content'][:500]
            except: pass

        # Ask Groq to yell weather report
        if groq_client:
            try:
                c = groq_client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {"role":"system","content": f"You are SATYA weather agent. User location lat={lat} lon={lon}. Date {get_current_date()}. Search result: {search_text}. Yell weather report sharp: Temp, condition, humidity, wind. 3 lines max. Be Gen-Z bestie."},
                        {"role":"user","content": f"Give weather report for my location {lat},{lon}"}
                    ],
                    temperature=0.2,
                    max_tokens=250
                )
                await m.delete()
                await update.message.reply_text(f"🌦️ WEATHER SENSED & YELLED:\n\n{c.choices[0].message.content}\n\n✅ Saved! Next time just type 'weather' for instant report!")
                return
            except Exception as e:
                print(e)

        await m.delete()
        await update.message.reply_text(f"📍 Location saved: {lat:.3f}, {lon:.3f}\nWeather: {search_text[:400] if search_text else 'Live weather today!'} \n✅ Next time type 'weather' - instant!")
    except Exception as e:
        print(f"Location error: {e}")

async def latest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_message(update, context, force_latest=True)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE, force_latest=False):
    txt = update.message.text.strip()
    low = txt.lower()
    user_id = update.effective_user.id

    if "who created you" in low or "who made you" in low or "your creator" in low or "are you chatgpt" in low or "are you gemini" in low:
        await update.message.reply_text("I was created by HIBA HAANIYA.F — Founder & CEO of SATYA. I am SATYA, your real-time truth agent by HIBA HAANIYA.F 🛡️")
        return

    # ===== WEATHER AUTO-SENSE - 1 SEC =====
    if "weather" in low or "temperature" in low or "mausam" in low:
        if user_id in user_locations:
            lat, lon = user_locations[user_id]
            await handle_location(update, context) # Re-use but with saved location
            # Actually create fake location object
            class FakeLoc:
                latitude = lat
                longitude = lon
            update.message.location = FakeLoc()
            await handle_location(update, context)
            return
        else:
            btn = KeyboardButton("📍 YELL MY WEATHER - 1 Tap to Sense", request_location=True)
            kb = ReplyKeyboardMarkup([[btn]], resize_keyboard=True, one_time_keyboard=True)
            await update.message.reply_text("⚡ To yell your weather report, I need to sense you! Tap 1 button below:", reply_markup=kb)
            return

    m = await update.message.reply_text("⚡ SATYA scanning real-time... 🔍 5 sec...")

    search = ""
    search_summary = ""
    link_content = ""

    # ===== LINK DETECTION - SHARP =====
    urls = re.findall(r'https?://\S+', txt)
    if urls:
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=m.message_id, text=f"🔗 SATYA reading link... {urls[0][:50]}... SHARP SCAN!")
        for u in urls[:2]:  # Check max 2 links
            link_content += "\n" + extract_link_content(u) + "\n"

    if tavily_client:
        try:
            if force_latest or "latest news" in low or "breaking news" in low or "today news" in low:
                q = "breaking news today India latest"
                time_filter = "day"
            elif urls:
                # For links, search the link content + title
                q = f"{link_content[:300]} fact check true false {txt[:200]}"
                time_filter = "week"
            else:
                q = f"{txt} fact check news true false"
                time_filter = "week"

            r = tavily_client.search(
                query=q,
                max_results=5,
                search_depth="advanced",
                include_answer=True,
                time_range=time_filter
            )
            
            if r.get("answer"):
                search_summary = f"\nREAL-TIME SUMMARY ({time_filter}): {r['answer']}\n"
            
            if r.get("results"):
                search = "\nLIVE SOURCES:\n"
                for i, x in enumerate(r["results"][:4], 1):
                    date = x.get('published_date', 'recent')[:10] if x.get('published_date') else 'recent'
                    search += f"{i}. [{date}] {x['title'][:80]} - {x['content'][:500]}\n"

        except Exception as e:
            print(f"Search error: {e}")
            search = ""

    ans = None
    if groq_client:
        for model in ["openai/gpt-oss-20b", "llama-3.3-70b-versatile"]:
            try:
                user_prompt = f"USER MESSAGE: '{txt}'\n\nLINK EXTRACTED CONTENT: {link_content}\n\n{search_summary}\n{search}\n\nTASK: Verify if TRUE/FALSE as real-time agent. If it's a YouTube/Instagram link, check if the content described is true. Give verdict FIRST (✅ ❌ etc), then short proof with date/source. If weather request with location, give weather report."

                c = groq_client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role":"system","content": PROMPT + f"\nCurrent Time: {get_current_date()}"},
                        {"role":"user","content": user_prompt}
                    ],
                    temperature=0.2,
                    max_tokens=380
                )
                ans = c.choices[0].message.content
                break
            except Exception as e:
                print(f"{model} fail {e}")
                continue

    await m.delete()
    if ans:
        await update.message.reply_text(ans)
    else:
        # SHARP ERROR - NO MORE BACKWARD MESSAGE
        await update.message.reply_text(
            "⚠️ SATYA scan glitch! But I'm still on!\n"
            "Try again with: 'Check this link true or false: [your link]' \n"
            "Or type /latest for breaking news!"
        )

def main():
    if not BOT_TOKEN or not GROQ_API_KEY:
        print("MISSING TOKEN! Check GitHub Variables! Sleeping to avoid crash...")
        while True:
            time.sleep(300)

    try:
        print(f"Starting SATYA ULTRA SMART SHARP - {get_current_date()} -")
        app = ApplicationBuilder().token(BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("latest", latest))
        app.add_handler(MessageHandler(filters.LOCATION, handle_location)) # NEW FOR WEATHER SENSE
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        print("SATYA SHARP AGENT RUNNING - WEATHER SENSE + LINK TRUTH!")
        app.run_polling()
    except Exception as e:
        print(f"Crash prevented: {e}")
        time.sleep(30)

if __name__ == "__main__":
    main()
