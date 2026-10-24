import os, requests, re, base64, time
from datetime import datetime
from zoneinfo import ZoneInfo
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from groq import Groq

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_KEY = os.getenv("GROQ_API_KEY")
TAVILY_KEY = os.getenv("TAVILY_API_KEY")
groq_client = Groq(api_key=GROQ_KEY) if GROQ_KEY else None

user_tones = {}
TONES_PROMPT = {
    "short": "SHORT mode — 3-4 lines max — sharp truth — precise",
    "ceo": "CEO mode — expensive — confident — sharp — business",
    "friendly": "FRIENDLY mode — bestie warm cute",
    "formal": "FORMAL mode — formal respectful for teachers",
    "roast": "ROAST mode — ROAST STUPID QUESTIONS — Savage funny dar ka mahol — Example: Do humans give birth to birds? -> Bro are you building Jurassic Park? Humans don't pop birds 😂"
}

def clean(t):
    t=re.sub(r'\*\*([^*]+)\*\*', r'\1', t)
    t=re.sub(r'\*([^*]+)\*', r'\1', t)
    t=t.replace('**','').replace('__','').replace('##','')
    lines=[]
    for x in t.split('\n'):
        if '|' in x and '---' in x: continue
        if x.strip().startswith('|') and x.strip().endswith('|'): continue
        if any(k in x.lower() for k in ['bottom line','believe live','never invent','what the sources']): continue
        lines.append(x)
    return '\n'.join('\n'.join(lines).split('\n')[:6]).strip()

def inline_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚡ SHORT", callback_data="t_short"), InlineKeyboardButton("👑 CEO", callback_data="t_ceo")],
        [InlineKeyboardButton("💖 FRIENDLY", callback_data="t_friendly"), InlineKeyboardButton("🎓 FORMAL", callback_data="t_formal")],
        [InlineKeyboardButton("🔥 ROAST", callback_data="t_roast")]
    ])

def location_kb():
    # ONE BUTTON PERMISSION TO ACCESS LOCATION — BOOM ACCURATE
    btn = KeyboardButton("📍 Share My Live Location — Boom Accurate Weather", request_location=True)
    return ReplyKeyboardMarkup([[btn]], resize_keyboard=True, one_time_keyboard=True)

def get_time_everywhere(q):
    # TIME OF EVERY PLACE IN WORLD — ACCURATE
    ql=q.lower()
    tz_map={
        "india":"Asia/Kolkata","ist":"Asia/Kolkata","delhi":"Asia/Kolkata","palamaner":"Asia/Kolkata",
        "saudi":"Asia/Riyadh","saudi arabia":"Asia/Riyadh","riyadh":"Asia/Riyadh","dubai":"Asia/Dubai","uae":"Asia/Dubai",
        "seoul":"Asia/Seoul","korea":"Asia/Seoul","south korea":"Asia/Seoul",
        "tokyo":"Asia/Tokyo","japan":"Asia/Tokyo",
        "new york":"America/New_York","usa":"America/New_York","us":"America/New_York",
        "london":"Europe/London","uk":"Europe/London","paris":"Europe/Paris","china":"Asia/Shanghai","australia":"Australia/Sydney",
        "qatar":"Asia/Qatar","kuwait":"Asia/Kuwait","bahrain":"Asia/Bahrain","singapore":"Asia/Singapore","malaysia":"Asia/Kuala_Lumpur"
    }
    tz="Asia/Kolkata"; abbr="IST"
    for k,v in tz_map.items():
        if k in ql: tz=v; abbr=k.upper(); break
    try:
        dt=datetime.now(ZoneInfo(tz))
        return dt.strftime(f"%d %B %Y, %I:%M:%S %p {abbr}"), tz
    except:
        dt=datetime.now(ZoneInfo("Asia/Kolkata"))
        return dt.strftime(f"%d %B %Y, %I:%M:%S %p IST"), "Asia/Kolkata"

def get_weather_exact(place):
    # ACCURATE EXACT WEATHER OF EVERY PLACE
    try:
        r=requests.get(f"https://wttr.in/{place}?format=%C+%t+%w+%h+%p", timeout=7)
        if r.status_code==200: return r.text.strip()
    except: pass
    return "Weather live"

def get_location_precise_everywhere(place):
    # PRECISE LOCATION OF EVERY PLACE IN WORLD
    try:
        # OpenStreetMap Nominatim — precise location everywhere
        r=requests.get(f"https://nominatim.openstreetmap.org/search?q={place}&format=json&limit=1", headers={"User-Agent":"SATYA-BOT-HIBA"}, timeout=8)
        if r.status_code==200 and r.json():
            d=r.json()[0]
            lat=d.get('lat'); lon=d.get('lon'); display=d.get('display_name')
            return f"{display}\n📍 Lat: {lat}, Lon: {lon}\n🗺️ Exact — OpenStreetMap"
    except: pass
    return f"{place.title()} — Precise location not in OSM, using live search"

def get_weather_latlon_exact(lat, lon):
    # BOOM ACCURATE — ONE BUTTON LOCATION PERMISSION
    try:
        # Reverse geocode to get place name
        rev=requests.get(f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json", headers={"User-Agent":"SATYA-BOT-HIBA"}, timeout=8)
        place_name="Your location"
        if rev.status_code==200:
            place_name=rev.json().get('display_name','Your location')[:120]
        # Exact weather
        r=requests.get(f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,wind_speed_10m,relative_humidity_2m,weather_code,apparent_temperature&timezone=auto", timeout=8)
        if r.status_code==200:
            c=r.json().get('current',{})
            return f"📍 Precise: {place_name}\n📍 Lat {lat:.6f}, Lon {lon:.6f}\n🌤️ {c.get('temperature_2m')}°C (Feels {c.get('apparent_temperature')}°C), Wind {c.get('wind_speed_10m')}km/h, Humidity {c.get('relative_humidity_2m')}%\n✅ Exact by tracking your location — Boom accurate"
    except Exception as e:
        print(e)
    return f"📍 {lat:.6f},{lon:.6f}\n🌤️ {get_weather_exact(f'{lat},{lon}')}"

def live_search(q):
    if not TAVILY_KEY: return ""
    try:
        r=requests.post("https://api.tavily.com/search", json={"api_key":TAVILY_KEY,"query":q,"max_results":4,"include_answer":True,"search_depth":"advanced"}, timeout=12)
        if r.status_code==200:
            d=r.json(); txt=f"{d.get('answer','')} "
            for x in d.get('results',[])[:2]: txt+=f"{x.get('content','')[:600]} "
            return txt
    except: pass
    return ""

def ask(q, uid):
    ql=q.lower()
    tone_key=user_tones.get(uid,"short")
    tone_ins=TONES_PROMPT.get(tone_key, TONES_PROMPT["short"])

    if any(x in ql for x in ["who created","who made","creator"]):
        if tone_key=="roast": return "👑 Bro obviously HIBA HAANIYA.F — 15 — CEO — Built SATYA at 12:37 AM while you ask bird eggs 😂"
        return "👑 I AM SATYA — CREATED BY HIBA HAANIYA.F — Founder & CEO — Palamaner 517408"

    # PRECISE LOCATION OF EVERY PLACE — TIME EVERY PLACE — WEATHER EVERY PLACE
    if any(x in ql for x in ["location of","where is","locate","exact location"]):
        place=ql.replace("location of","").replace("where is","").replace("locate","").replace("exact location","").strip()
        loc=get_location_precise_everywhere(place)
        t,_=get_time_everywhere(place); w=get_weather_exact(place)
        return f"✅ PRECISE LOCATION — {place.title()}:\n{loc}\n🕐 Time: {t}\n🌤️ Weather: {w}\n— SATYA precise"

    if "time" in ql:
        t,tz=get_time_everywhere(q)
        w=get_weather_exact(q)
        return f"✅ TIME EVERY PLACE — Time in {q.title()}: {t}\n📍 Zone: {tz}\n🌤️ Weather: {w}\n— SATYA exact"

    if "weather" in ql:
        p=ql.replace("weather in","").replace("weather","").strip() or "India"
        loc=get_location_precise_everywhere(p)
        t,_=get_time_everywhere(p); w=get_weather_exact(p)
        return f"✅ EXACT WEATHER — Weather in {p.title()}: {w}\n📍 Location: {loc}\n🕐 Time: {t}\n📍 Share live location for boom accurate — One button"

    live=live_search(q)
    prompt=f"""{tone_ins}
You are SATYA by HIBA — Precise for ANY question — You tell precise location everywhere, time everywhere, exact weather everywhere.
Date {get_time_everywhere('India')[0]}
NEVER ** * | --- table. Max 5 lines. Start ✅ ❌ ⚠️. Same language as Q. Tone {tone_key.upper()}. If location question, give lat lon exact. If time question, give exact time any country. If weather, give exact weather.
LIVE: {live[:2500]}
Q: {q}
ANSWER PRECISE:"""

    if not groq_client: return "⚠️ Add GROQ_API_KEY"
    for m in ["openai/gpt-oss-20b","qwen/qwen3-32b","llama-3.3-70b-versatile"]:
        try:
            c=groq_client.chat.completions.create(model=m, messages=[{"role":"user","content":prompt}], temperature=0.7 if tone_key=="roast" else 0.3, max_tokens=500)
            txt=c.choices[0].message.content.strip()
            if len(txt)>10: return clean(txt)
        except Exception as e:
            print(e)
            continue
    return "⚠️ Busy — Try again"

async def start(update, context):
    t,_=get_time_everywhere("India")
    await update.message.reply_text(
        f"⚡ SATYA — EXTRAORDINARY — ONE BUTTON LOCATION 🛡️\n👑 HIBA HAANIYA.F — CEO\n🕐 {t[0]}\n🌐 I tell precise location of every place in world\n🕐 Time of every place in world\n🌤️ Accurate exact weather of every place\n📍 ONE BUTTON — Share location — Boom accurate perfect\n\n👇 CLICK BUTTON BELOW FOR EXACT WEATHER BY YOUR LOCATION:",
        reply_markup=location_kb()
    )
    await update.message.reply_text("🎛️ SET TONE — CLICK ANYTIME:", reply_markup=inline_kb())

async def tone_cmd(update, context): await update.message.reply_text("🎛️ SET TONE:", reply_markup=inline_kb())

async def tone_cb(update, context):
    q=update.callback_query; await q.answer()
    key=q.data.replace("t_","")
    user_tones[q.from_user.id]=key
    await q.edit_message_text(f"✅ Tone {key.upper()} set — Ask any place/time/weather — Precise — One button location for boom accurate", reply_markup=inline_kb())

async def handle_text(update, context):
    ans=ask(update.message.text, update.effective_user.id)
    await update.message.reply_text(ans, reply_markup=inline_kb())
    # After answer, show location button again for boom accurate
    await update.message.reply_text("📍 Want boom accurate weather by YOUR location? Click button:", reply_markup=location_kb())

async def handle_loc(update, context):
    lat=update.message.location.latitude; lon=update.message.location.longitude
    t,_=get_time_everywhere("India")
    w=get_weather_latlon_exact(lat, lon)
    await update.message.reply_text(f"✅ BOOM ACCURATE — ONE BUTTON LOCATION PERMISSION SUCCESS\n{w}\n🕐 Time: {t[0]}\n✅ Precise location of every place — Time every place — Weather exact — Perfect — No mistake — SATYA", reply_markup=inline_kb())

async def post_init(app):
    await app.bot.delete_webhook(drop_pending_updates=True)
    print("✅ Webhook deleted — One button location — Precise everywhere")

def main():
    app=Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tone", tone_cmd))
    app.add_handler(CallbackQueryHandler(tone_cb, pattern="^t_"))
    app.add_handler(MessageHandler(filters.LOCATION, handle_loc))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.run_polling(drop_pending_updates=True)

if __name__=="__main__": main()
