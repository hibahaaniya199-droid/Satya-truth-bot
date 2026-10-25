import os, requests, re, json
from datetime import datetime
from zoneinfo import ZoneInfo
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from groq import Groq

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_KEY = os.getenv("GROQ_API_KEY")
TAVILY_KEY = os.getenv("TAVILY_API_KEY")
groq_client = Groq(api_key=GROQ_KEY) if GROQ_KEY else None

user_tones = {}
user_locations = {}  # USER_ID -> (lat, lon, place_name)
LOC_FILE = "/tmp/satya_locations.json"

# LOAD SAVED LOCATIONS — SO PERMISSION ONLY ONCE FOREVER — NOT EVERY RESTART
try:
    if os.path.exists(LOC_FILE):
        with open(LOC_FILE,"r") as f:
            data=json.load(f)
            for k,v in data.items():
                user_locations[int(k)]=(v[0],v[1],v[2] if len(v)>2 else "Saved")
except: pass

def save_locs():
    try:
        with open(LOC_FILE,"w") as f:
            json.dump({str(k):[v[0],v[1],v[2]] for k,v in user_locations.items()}, f)
    except: pass

TONES = {
    "short": "SHORT — 3-4 lines max sharp",
    "ceo": "CEO — expensive confident",
    "friendly": "FRIENDLY — bestie warm",
    "formal": "FORMAL — respectful formal",
    "roast": "ROAST — roast stupid Q savage funny, but for real news verify seriously"
}

def clean(t):
    t=re.sub(r'\*\*([^*]+)\*\*', r'\1', t)
    t=re.sub(r'\*([^*]+)\*', r'\1', t)
    t=t.replace('**','').replace('__','')
    lines=[x for x in t.split('\n') if not ('|' in x and '---' in x) and not (x.strip().startswith('|') and x.strip().endswith('|'))]
    lines=[x for x in lines if 'bottom line' not in x.lower() and 'believe live' not in x.lower()]
    return '\n'.join('\n'.join(lines).split('\n')[:7]).strip()

def kb_tone():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚡ SHORT", callback_data="t_short"), InlineKeyboardButton("👑 CEO", callback_data="t_ceo")],
        [InlineKeyboardButton("💖 FRIENDLY", callback_data="t_friendly"), InlineKeyboardButton("🎓 FORMAL", callback_data="t_formal")],
        [InlineKeyboardButton("🔥 ROAST", callback_data="t_roast")]
    ])

def kb_location_once():
    btn = KeyboardButton("📍 Share Location Once — Correct Weather", request_location=True)
    return ReplyKeyboardMarkup([[btn]], resize_keyboard=True, one_time_keyboard=True)

# ===== CORRECT WEATHER + TIMING OF ANY PLACE — ANY CORNER — EXACT =====

def get_coords(place):
    # PRECISE LOCATION OF EVERY PLACE — ANY CORNER
    try:
        r=requests.get(f"https://nominatim.openstreetmap.org/search?q={place}&format=json&limit=1&addressdetails=1", headers={"User-Agent":"SATYA-HIBA-CEO"}, timeout=8)
        if r.status_code==200 and r.json():
            d=r.json()[0]
            return float(d['lat']), float(d['lon']), d.get('display_name','')
    except: pass
    return None, None, ""

def get_time_weather_exact(place_or_latlon):
    # CORRECT WEATHER + TIMING OF ANY PLACE — EXACT — BY TIMEZONE AUTO
    try:
        if isinstance(place_or_latlon, tuple):
            lat, lon = place_or_latlon
            display = ""
        else:
            lat, lon, display = get_coords(place_or_latlon)
            if lat is None:
                return None
        # Open-Meteo — timezone auto — gives exact local time + correct weather
        r=requests.get(f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,apparent_temperature,wind_speed_10m,relative_humidity_2m,weather_code&timezone=auto", timeout=8)
        if r.status_code==200:
            j=r.json()
            curr=j.get('current',{})
            tz=j.get('timezone','')
            tz_abbr=j.get('timezone_abbreviation','')
            iso_time=curr.get('time','')
            # Convert iso_time to pretty
            try:
                dt=datetime.fromisoformat(iso_time)
                pretty=dt.strftime(f"%d %B %Y, %I:%M:%S %p {tz_abbr or tz}")
            except:
                pretty=iso_time
            weather=f"{curr.get('temperature_2m')}°C (feels {curr.get('apparent_temperature')}°C), wind {curr.get('wind_speed_10m')}km/h, humidity {curr.get('relative_humidity_2m')}%, code {curr.get('weather_code')}"
            return {
                "lat":lat,"lon":lon,"display":display,
                "time":pretty,"timezone":tz,"abbr":tz_abbr,
                "weather":weather,
                "iso":iso_time
            }
    except Exception as e:
        print(e)
    return None

def live_search_anywhere(query):
    if not TAVILY_KEY: return ""
    try:
        r=requests.post("https://api.tavily.com/search", json={"api_key":TAVILY_KEY,"query":query,"search_depth":"advanced","max_results":5,"include_answer":True}, timeout=14)
        if r.status_code==200:
            d=r.json()
            txt=d.get('answer','')+" "
            for it in d.get('results',[])[:4]:
                txt+=it.get('content','')[:800]+" "
            return txt[:4000]
    except: pass
    return ""

def ask_any(q, uid):
    ql=q.lower().strip()
    tone=user_tones.get(uid,"short")
    tone_ins=TONES.get(tone, TONES["short"])

    if any(x in ql for x in ["who created you","who made you","your creator"]):
        return "👑 I AM SATYA — CREATED BY HIBA HAANIYA.F — 15 — Palamaner — CEO"

    # ===== CORRECT WEATHER + TIMING OF ANY PLACE — DIRECT — NO CHEATING — ANY CORNER =====
    # If user asks timing / time / weather / location
    is_time_q = any(x in ql for x in ["time in","timing","what time","current time","time at"])
    is_weather_q = "weather" in ql
    is_loc_q = any(x in ql for x in ["where is","location of","locate","exact location","address of"])

    if is_time_q or is_weather_q or is_loc_q:
        # Extract place name
        place = ql
        for p in ["time in","timing of","what time in","current time in","weather in","weather at","weather of","where is","location of","locate","exact location of","address of","timing","time","weather","where","location"]:
            place=place.replace(p,"")
        place=place.strip() or "India"
        
        # If weather and user has saved location and says my location / my weather / here
        if is_weather_q and uid in user_locations and any(x in ql for x in ["my location","my weather","here","my place","current location"]):
            lat,lon,name=user_locations[uid]
            info=get_time_weather_exact((lat,lon))
            if info:
                return f"✅ CORRECT WEATHER — Your saved location once — Boom accurate\n📍 {name}\n📍 {lat:.6f}, {lon:.6f}\n🕐 Timing: {info['time']} — {info['timezone']}\n🌤️ Weather: {info['weather']}\n✅ Permission asked only once — Saved forever"

        info=get_time_weather_exact(place)
        if info:
            if is_time_q:
                return f"✅ TIMING OF {place.upper()} — ANY PLACE\n🕐 {info['time']}\n📍 {info['display'] or place}\n🌐 Timezone: {info['timezone']} ({info['abbr']})\n📍 Lat {info['lat']:.6f}, Lon {info['lon']:.6f}\n🌤️ Weather there: {info['weather']}"
            if is_weather_q:
                return f"✅ CORRECT WEATHER — {place.upper()} — Exact\n🌤️ {info['weather']}\n🕐 Timing there: {info['time']}\n📍 {info['display']}\n📍 Lat {info['lat']:.6f}, Lon {info['lon']:.6f}\n🌐 {info['timezone']}"
            if is_loc_q:
                return f"✅ PRECISE LOCATION — {place.upper()}\n📍 {info['display']}\n📍 Lat {info['lat']:.6f}, Lon {info['lon']:.6f}\n🕐 Timing there: {info['time']}\n🌤️ Weather: {info['weather']}"

    # ===== ANY DAMN QUESTION — ANY CORNER — LIVE + BRAIN =====
    live=live_search_anywhere(q)
    loc_ctx=""
    if uid in user_locations:
        lat,lon,name=user_locations[uid]
        info=get_time_weather_exact((lat,lon))
        if info:
            loc_ctx=f"User saved location once: {name} lat {lat} lon {lon} time {info['time']} weather {info['weather']} — Use for local Q."

    prompt=f"""{tone_ins}
You are SATYA by HIBA — Answer ANY damn question any corner world — Precise timing any place, correct weather, precise location.
Rules: NEVER ** * | --- table. Max 6 lines. Start ✅ ❌ ⚠️. Same language as Q. Tone {tone.upper()}. For breaking news, verify TRUE/FALSE using LIVE. Date now Asia/Kolkata {datetime.now(ZoneInfo('Asia/Kolkata')).strftime('%d %B %Y %I:%M %p IST')}
Saved loc: {loc_ctx}
LIVE: {live[:3500]}
Q: {q}
Answer:
"""
    if not groq_client: return "⚠️ Add GROQ_API_KEY"
    models=["openai/gpt-oss-20b","openai/gpt-oss-120b","qwen/qwen3-32b","llama-3.3-70b-versatile","llama-3.1-8b-instant"]
    for m in models:
        try:
            c=groq_client.chat.completions.create(model=m, messages=[{"role":"user","content":prompt}], temperature=0.7 if tone=="roast" else 0.25, max_tokens=600)
            txt=c.choices[0].message.content.strip()
            if len(txt)>15: return clean(txt)
        except Exception as e:
            print(e)
            continue
    if live: return clean(f"Live: {live[:500]}")
    return "⚠️ Busy — Wait 10 sec"

async def start(update, context):
    uid=update.effective_user.id
    if uid in user_locations:
        lat,lon,name=user_locations[uid]
        info=get_time_weather_exact((lat,lon))
        w=info['weather'] if info else "saved"
        await update.message.reply_text(f"⚡ SATYA — Location already saved once — Not asking again 🛡️\n📍 {name}\n🌤️ Correct weather: {w}\n🕐 {info['time'] if info else ''}\n✅ Permission asked only once — Boom accurate\nUse /location to change", reply_markup=kb_tone())
    else:
        await update.message.reply_text(f"⚡ SATYA — CORRECT WEATHER + TIMING ANY PLACE 🌍\n👑 HIBA — CEO\n🕐 {datetime.now(ZoneInfo('Asia/Kolkata')).strftime('%d %B %Y %I:%M %p IST')}\n\n📍 Share location ONCE — I save forever — Correct weather + timing — Never ask again\n👇 Click once:", reply_markup=kb_location_once())
        await update.message.reply_text("🎛️ SET TONE:", reply_markup=kb_tone())

async def loc_cmd(update, context):
    await update.message.reply_text("📍 Share location ONCE — Saved forever — Correct weather — Timing any place:", reply_markup=kb_location_once())

async def tone_cmd(update, context):
    await update.message.reply_text("🎛️ SET TONE:", reply_markup=kb_tone())

async def tone_cb(update, context):
    q=update.callback_query; await q.answer()
    user_tones[q.from_user.id]=q.data.replace("t_","")
    await q.edit_message_text(f"✅ Tone {q.data.replace('t_','').upper()} set — Ask timing of any place — Correct weather", reply_markup=kb_tone())

async def handle_text(update, context):
    ans=ask_any(update.message.text, update.effective_user.id)
    await update.message.reply_text(ans, reply_markup=kb_tone())

async def handle_loc(update, context):
    lat=update.message.location.latitude; lon=update.message.location.longitude
    # Reverse geocode to get name — correct weather
    try:
        r=requests.get(f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json", headers={"User-Agent":"SATYA-HIBA-CEO"}, timeout=8)
        name=r.json().get('display_name','Your saved location') if r.status_code==200 else "Your saved location"
    except:
        name="Your saved location"
    user_locations[update.effective_user.id]=(lat,lon,name)
    save_locs()
    info=get_time_weather_exact((lat,lon))
    if info:
        await update.message.reply_text(f"✅ LOCATION SAVED ONCE — Never asking again — Correct weather — Timing\n📍 {name[:150]}\n📍 {lat:.6f}, {lon:.6f}\n🕐 Timing: {info['time']} — {info['timezone']}\n🌤️ Correct weather: {info['weather']}\n✅ Permission asked only once — Boom accurate perfect", reply_markup=kb_tone())
    else:
        await update.message.reply_text(f"✅ Location saved once — {lat:.6f},{lon:.6f} — {name}", reply_markup=kb_tone())

async def post_init(app):
    await app.bot.delete_webhook(drop_pending_updates=True)
    print("✅ Correct weather — Timing any place — Location once")

def main():
    app=Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tone", tone_cmd))
    app.add_handler(CommandHandler("location", loc_cmd))
    app.add_handler(CallbackQueryHandler(tone_cb, pattern="^t_"))
    app.add_handler(MessageHandler(filters.LOCATION, handle_loc))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.run_polling(drop_pending_updates=True)

if __name__=="__main__": main()