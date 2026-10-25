import os
import requests
import re
import json
import tempfile
from datetime import datetime
from zoneinfo import ZoneInfo
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from groq import Groq

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_KEY = os.getenv("GROQ_API_KEY")
TAVILY_KEY = os.getenv("TAVILY_API_KEY")
groq_client = Groq(api_key=GROQ_KEY) if GROQ_KEY else None

user_tones = {}
user_locations = {}
user_lang_mode = {}
user_voice_reply = {}
LOC_FILE = "/tmp/satya_locations.json"

try:
    if os.path.exists(LOC_FILE):
        with open(LOC_FILE, "r") as f:
            data = json.load(f)
            for k, v in data.items():
                user_locations[int(k)] = (v[0], v[1], v[2] if len(v) > 2 else "Saved")
except:
    pass

def save_locs():
    try:
        with open(LOC_FILE, "w") as f:
            json.dump({str(k): [v[0], v[1], v[2]] for k, v in user_locations.items()}, f)
    except:
        pass

TONES = {
    "short": "SHORT — 3-4 lines max sharp",
    "ceo": "CEO — expensive confident",
    "friendly": "FRIENDLY — bestie warm",
    "formal": "FORMAL — respectful",
    "roast": "ROAST — roast stupid Q savage funny"
}

TIMEZONE_DB = {
    "palamaner": "Asia/Kolkata", "palamner": "Asia/Kolkata", "chittoor": "Asia/Kolkata", "tirupati": "Asia/Kolkata",
    "faiza": "Asia/Kolkata", "gangavaram": "Asia/Kolkata", "gantavoor": "Asia/Kolkata", "basavanna katta": "Asia/Kolkata", "golbodi": "Asia/Kolkata",
    "india": "Asia/Kolkata", "delhi": "Asia/Kolkata", "mumbai": "Asia/Kolkata", "kolkata": "Asia/Kolkata", "chennai": "Asia/Kolkata", "bangalore": "Asia/Kolkata", "hyderabad": "Asia/Kolkata",
    "saudi": "Asia/Riyadh", "saudi arabia": "Asia/Riyadh", "riyadh": "Asia/Riyadh", "jeddah": "Asia/Riyadh", "mecca": "Asia/Riyadh",
    "dubai": "Asia/Dubai", "uae": "Asia/Dubai", "abu dhabi": "Asia/Dubai", "qatar": "Asia/Qatar", "doha": "Asia/Qatar", "kuwait": "Asia/Kuwait", "bahrain": "Asia/Bahrain", "oman": "Asia/Muscat",
    "south korea": "Asia/Seoul", "korea": "Asia/Seoul", "seoul": "Asia/Seoul", "대한민국": "Asia/Seoul", "busan": "Asia/Seoul", "incheon": "Asia/Seoul",
    "japan": "Asia/Tokyo", "tokyo": "Asia/Tokyo", "osaka": "Asia/Tokyo", "china": "Asia/Shanghai", "beijing": "Asia/Shanghai", "shanghai": "Asia/Shanghai",
    "hong kong": "Asia/Hong_Kong", "singapore": "Asia/Singapore", "malaysia": "Asia/Kuala_Lumpur", "thailand": "Asia/Bangkok", "philippines": "Asia/Manila", "indonesia": "Asia/Jakarta",
    "uk": "Europe/London", "london": "Europe/London", "england": "Europe/London", "paris": "Europe/Paris", "france": "Europe/Paris", "germany": "Europe/Berlin", "berlin": "Europe/Berlin", "italy": "Europe/Rome", "rome": "Europe/Rome", "spain": "Europe/Madrid", "madrid": "Europe/Madrid", "turkey": "Europe/Istanbul", "istanbul": "Europe/Istanbul",
    "usa": "America/New_York", "us": "America/New_York", "new york": "America/New_York", "america": "America/New_York", "california": "America/Los_Angeles", "los angeles": "America/Los_Angeles", "texas": "America/Chicago", "chicago": "America/Chicago", "canada": "America/Toronto", "brazil": "America/Sao_Paulo", "australia": "Australia/Sydney", "sydney": "Australia/Sydney", "egypt": "Africa/Cairo"
}

def clean(t):
    t = re.sub(r'\*\*([^*]+)\*\*', r'\1', t)
    t = re.sub(r'\*([^*]+)\*', r'\1', t)
    t = t.replace('**', '').replace('__', '')
    lines = [x for x in t.split('\n') if not ('|' in x and '---' in x) and not (x.strip().startswith('|') and x.strip().endswith('|'))]
    lines = [x for x in lines if 'bottom line' not in x.lower() and 'believe live' not in x.lower()]
    return '\n'.join('\n'.join(lines).split('\n')[:7]).strip()

def get_speak_text(text):
    t = text
    t = re.sub(r'[✅❌⚠️🎤📍🕐🌤️🌍👑⚡🔥💖🎓]', '', t)
    t = t.replace("HIBA HAANIYA.F", "Heeba Haaniya")
    t = t.replace("HIBA HAANIYA", "Heeba Haaniya")
    t = t.replace("HIBA", "Heeba")
    t = t.replace("SATYA", "Sathya")
    t = t.replace(".F", "")
    t = t.replace("Founder & CEO", "Founder and CEO")
    t = re.sub(r'\s+', ' ', t).strip()
    return t[:400]

def kb_tone():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚡ SHORT", callback_data="t_short"), InlineKeyboardButton("👑 CEO", callback_data="t_ceo")],
        [InlineKeyboardButton("💖 FRIENDLY", callback_data="t_friendly"), InlineKeyboardButton("🎓 FORMAL", callback_data="t_formal")],
        [InlineKeyboardButton("🔥 ROAST", callback_data="t_roast")],
        [InlineKeyboardButton("🌍 Any Language", callback_data="t_lang"), InlineKeyboardButton("🎤 Speak Voice", callback_data="t_voice")]
    ])

def kb_location_once():
    btn = KeyboardButton("📍 Share Location Once — Never Again", request_location=True)
    return ReplyKeyboardMarkup([[btn]], resize_keyboard=True, one_time_keyboard=True)

def get_coords(place):
    try:
        r = requests.get(f"https://nominatim.openstreetmap.org/search?q={place}&format=json&limit=1", headers={"User-Agent": "SATYA-HIBA-CEO"}, timeout=8)
        if r.status_code == 200 and r.json():
            d = r.json()[0]
            return float(d['lat']), float(d['lon']), d.get('display_name', '')
    except:
        pass
    return None, None, ""

def get_time_weather_exact(place_or_latlon):
    try:
        if isinstance(place_or_latlon, tuple):
            lat, lon = place_or_latlon
            display = ""
        else:
            lat, lon, display = get_coords(place_or_latlon)
            if lat is None:
                ql = str(place_or_latlon).lower()
                tz_found = None
                for k, v in TIMEZONE_DB.items():
                    if k in ql:
                        tz_found = v
                        break
                if tz_found:
                    dt = datetime.now(ZoneInfo(tz_found))
                    pretty = dt.strftime(f"%d %B %Y, %I:%M:%S %p {tz_found}")
                    return {"lat": 0, "lon": 0, "display": place_or_latlon, "time": pretty, "timezone": tz_found, "weather": "Use saved location for weather"}
                return None
        r = requests.get(f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,apparent_temperature,wind_speed_10m,relative_humidity_2m&timezone=auto", timeout=8)
        if r.status_code != 200:
            return None
        j = r.json()
        tz = j.get('timezone', 'Asia/Kolkata')
        curr = j.get('current', {})
        weather = f"{curr.get('temperature_2m')}°C feels {curr.get('apparent_temperature')}°C, wind {curr.get('wind_speed_10m')}km/h, humidity {curr.get('relative_humidity_2m')}%"
        try:
            dt = datetime.now(ZoneInfo(tz))
            pretty = dt.strftime(f"%d %B %Y, %I:%M:%S %p {tz}")
        except:
            dt = datetime.now(ZoneInfo("Asia/Kolkata"))
            pretty = dt.strftime(f"%d %B %Y, %I:%M:%S %p IST")
            tz = "Asia/Kolkata"
        return {"lat": lat, "lon": lon, "display": display, "time": pretty, "timezone": tz, "weather": weather}
    except Exception as e:
        print(e)
    return None

def live_search_anywhere(query):
    if not TAVILY_KEY:
        return ""
    try:
        r = requests.post("https://api.tavily.com/search", json={"api_key": TAVILY_KEY, "query": query, "search_depth": "advanced", "max_results": 5, "include_answer": True}, timeout=14)
        if r.status_code == 200:
            d = r.json()
            txt = d.get('answer', '') + " "
            for it in d.get('results', [])[:4]:
                txt += it.get('content', '')[:800] + " "
            return txt[:4000]
    except:
        pass
    return ""

def transcribe_voice(file_path):
    if not groq_client:
        return ""
    try:
        with open(file_path, "rb") as f:
            transcription = groq_client.audio.transcriptions.create(model="whisper-large-v3", file=(file_path, f.read()), response_format="text")
            if isinstance(transcription, str):
                return transcription
            return getattr(transcription, 'text', str(transcription))
    except Exception as e:
        print(f"transcribe fail {e}")
        return ""

def ask_any(q, uid):
    ql = q.lower().strip()
    tone = user_tones.get(uid, "short")

    if any(x in ql for x in ["who made you", "who created you", "kisne banaya", "आपको किसने बनाया", "who built you", "your creator", "तुम्हें किसने बनाया", "creator", "ఎవరు", "निम्मनि"]):
        if "आपको किसने बनाया" in q or "किसने बनाया" in q or "तुम्हें" in q or "किसने" in q:
            return "✅ मैं SATYA हूँ — मुझे HIBA HAANIYA.F ने बनाया है — 15 साल — पलमनेर 517408 — Founder & CEO — मैं OpenAI नहीं हूँ — मैं HIBA की हूँ"
        if "ఎవరు" in q or "నన్ను" in q:
            return "✅ నేను SATYA — నన్ను HIBA HAANIYA.F సృష్టించారు — 15 ఏళ్లు — పలమనేరు CEO — నేను OpenAI కాదు"
        if "اردو" in q:
            return "✅ میں SATYA ہوں — مجھے HIBA HAANIYA.F نے بنایا — 15 سال — پلامنیر CEO"
        return "✅ I AM SATYA — CREATED BY HIBA HAANIYA.F — 15 — Palamaner 517408 — Founder & CEO — I am NOT OpenAI — I am HIBA's"

    is_time_q = any(x in ql for x in ["time in", "timing", "what time", "current time"])
    is_weather_q = "weather" in ql
    is_loc_q = any(x in ql for x in ["where is", "location of", "locate"])

    if is_time_q or is_weather_q or is_loc_q:
        place = ql
        for p in ["time in", "timing of", "what time in", "current time in", "weather in", "weather at", "where is", "location of", "locate", "exact location of", "timing", "time", "weather", "where", "location"]:
            place = place.replace(p, "")
        place = place.strip() or "India"
        if is_weather_q and uid in user_locations and any(x in ql for x in ["my location", "my weather", "here"]):
            lat, lon, name = user_locations[uid]
            info = get_time_weather_exact((lat, lon))
            if info:
                return f"✅ CORRECT WEATHER — Saved once\n📍 {name}\n📍 {lat:.6f},{lon:.6f}\n🕐 {info['time']}\n🌤️ {info['weather']}"
        info = get_time_weather_exact(place)
        if info:
            if is_time_q:
                return f"✅ TIMING OF {place.upper()}\n🕐 {info['time']}\n📍 {info['display'] or place}\n🌐 {info['timezone']}\n📍 {info['lat']:.6f},{info['lon']:.6f}\n🌤️ {info['weather']}"
            if is_weather_q:
                return f"✅ CORRECT WEATHER — {place.upper()}\n🌤️ {info['weather']}\n🕐 {info['time']}\n📍 {info['display']}"
            if is_loc_q:
                return f"✅ PRECISE LOCATION — {place.upper()}\n📍 {info['display']}\n📍 {info['lat']:.6f},{info['lon']:.6f}\n🕐 {info['time']}"

    live = live_search_anywhere(q)
    loc_ctx = ""
    if uid in user_locations:
        lat, lon, name = user_locations[uid]
        info = get_time_weather_exact((lat, lon))
        if info:
            loc_ctx = f"Saved {name} {info['time']} {info['weather']}"

    prompt = f"""You are SATYA — Created by HIBA HAANIYA.F — 15 — Palamaner — Founder and CEO — You are NOT OpenAI. If asked who made you in ANY language, MUST say HIBA HAANIYA.F.

{TONES.get(tone, '')}
Same language as question.
Rules: NEVER ** * | --- table. Max 6 lines. Start ✅ ❌ ⚠️. Tone {tone.upper()}. Date {datetime.now(ZoneInfo('Asia/Kolkata')).strftime('%d %B %Y %I:%M %p IST')}
Saved: {loc_ctx}
LIVE: {live[:3500]}
Q: {q}
Answer as SATYA created by HIBA:
"""
    if not groq_client:
        return "⚠️ Add GROQ_API_KEY"
    models = ["openai/gpt-oss-20b", "openai/gpt-oss-120b", "qwen/qwen3-32b", "llama-3.3-70b-versatile", "llama-3.1-8b-instant"]
    for m in models:
        try:
            c = groq_client.chat.completions.create(
                model=m,
                messages=[
                    {"role": "system", "content": "You are SATYA created by HIBA HAANIYA.F, 15, Palamaner, Founder & CEO. You are NOT OpenAI. MUST say HIBA HAANIYA.F is creator."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7 if tone == "roast" else 0.25,
                max_tokens=600
            )
            txt = c.choices[0].message.content.strip()
            if "OpenAI" in txt and "HIBA" not in txt:
                txt = txt.replace("OpenAI", "HIBA HAANIYA.F")
            if len(txt) > 15:
                return clean(txt)
        except Exception as e:
            print(e)
            continue
    if live:
        return clean(f"Live: {live[:500]}")
    return "⚠️ Busy — Wait 10 sec"

async def start(update, context):
    uid = update.effective_user.id
    if uid in user_locations:
        lat, lon, name = user_locations[uid]
        info = get_time_weather_exact((lat, lon))
        await update.message.reply_text(f"⚡ SATYA — HIBA HAANIYA.F — CEO — Location saved once — Not asking again\n📍 {name[:120]}\n🌤️ {info['weather'] if info else ''}\n🕐 {info['time'] if info else ''}\n\n🎛️ Type /tone to change tone — Pop up only\n📍 Type /location to change location\n🎤 Send voice — I say Heeba Haaniya properly")
    else:
        await update.message.reply_text(f"⚡ SATYA — HIBA HAANIYA.F — CEO 🌍\n👑 Created by HIBA — Not OpenAI\n🕐 {datetime.now(ZoneInfo('Asia/Kolkata')).strftime('%d %B %Y %I:%M %p IST')}\n\n📍 Share location ONCE — Saved forever — Never asks again\n👇 Click once below:", reply_markup=kb_location_once())

async def loc_cmd(update, context):
    await update.message.reply_text("📍 Share location ONCE — Saved forever — Won't ask again:", reply_markup=kb_location_once())

async def tone_cmd(update, context):
    await update.message.reply_text("🎛️ Choose tone — Pop up — Only when you type /tone:", reply_markup=kb_tone())

async def tone_cb(update, context):
    q = update.callback_query
    await q.answer()
    data = q.data
    uid = q.from_user.id
    if data == "t_lang":
        user_lang_mode[uid] = True
        await q.edit_message_text("✅ 🌍 ANY LANGUAGE ON — I reply same language — HIBA HAANIYA.F — Pop up closed — Type /tone to open again")
    elif data == "t_voice":
        user_voice_reply[uid] = True
        user_lang_mode[uid] = True
        await q.edit_message_text("✅ 🎤 VOICE MODE ON — Send voice — I detect and say Heeba Haaniya properly — Pop up closed — /tone to change")
    else:
        user_tones[uid] = data.replace("t_", "")
        await q.edit_message_text(f"✅ Tone {data.replace('t_', '').upper()} set — HIBA HAANIYA.F — Pop up closed — Type /tone to change again")

async def handle_text(update, context):
    ans = ask_any(update.message.text, update.effective_user.id)
    await update.message.reply_text(ans)
    if user_voice_reply.get(update.effective_user.id):
        try:
            from gtts import gTTS
            speak = get_speak_text(ans)
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                lang = 'en'
                if any('\u0900' <= c <= '\u097F' for c in update.message.text):
                    lang = 'hi'
                if any('\u0C00' <= c <= '\u0C7F' for c in update.message.text):
                    lang = 'te'
                tts = gTTS(text=speak, lang=lang, slow=False)
                tts.save(tmp.name)
                await update.message.reply_voice(voice=open(tmp.name, 'rb'))
        except Exception as e:
            print(e)

async def handle_voice(update, context):
    try:
        file = await update.message.voice.get_file()
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            await file.download_to_drive(tmp.name)
            text = transcribe_voice(tmp.name)
        if text:
            await update.message.reply_text(f"🎤 Heard: {text[:200]}")
            ans = ask_any(text, update.effective_user.id)
            await update.message.reply_text(ans)
            try:
                from gtts import gTTS
                speak = get_speak_text(ans)
                lang = 'en'
                if any('\u0900' <= c <= '\u097F' for c in text):
                    lang = 'hi'
                if any('\u0C00' <= c <= '\u0C7F' for c in text):
                    lang = 'te'
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp2:
                    tts = gTTS(text=speak, lang=lang, slow=False)
                    tts.save(tmp2.name)
                    await update.message.reply_voice(voice=open(tmp2.name, 'rb'))
            except Exception as e:
                print(e)
        else:
            await update.message.reply_text("⚠️ Could not hear voice — Try again")
    except Exception as e:
        print(e)
        await update.message.reply_text("⚠️ Voice error — Try text")

async def handle_loc(update, context):
    lat = update.message.location.latitude
    lon = update.message.location.longitude
    try:
        r = requests.get(f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json", headers={"User-Agent": "SATYA-HIBA-CEO"}, timeout=8)
        name = r.json().get('display_name', 'Your saved location') if r.status_code == 200 else "Your saved location"
    except:
        name = "Your saved location"
    user_locations[update.effective_user.id] = (lat, lon, name)
    save_locs()
    info = get_time_weather_exact((lat, lon))
    if info:
        await update.message.reply_text(f"✅ LOCATION SAVED ONCE — Never asking again — HIBA HAANIYA.F\n📍 {name[:150]}\n📍 {lat:.6f},{lon:.6f}\n🕐 {info['time']}\n🌤️ {info['weather']}\n\nKeyboard removed — /location to change — /tone for tone", reply_markup=ReplyKeyboardRemove())
    else:
        await update.message.reply_text(f"✅ Saved — {lat:.6f},{lon:.6f}", reply_markup=ReplyKeyboardRemove())

async def post_init(app):
    await app.bot.delete_webhook(drop_pending_updates=True)
    print("✅ HIBA HAANIYA.F — No spam — Location once — Tone pop up — Voice Heeba Haaniya proper")

def main():
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tone", tone_cmd))
    app.add_handler(CommandHandler("location", loc_cmd))
    app.add_handler(CallbackQueryHandler(tone_cb, pattern="^t_"))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.LOCATION, handle_loc))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()