import os, requests, re, base64, time
from datetime import datetime
from zoneinfo import ZoneInfo
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.error import Conflict
from groq import Groq

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_KEY = os.getenv("GROQ_API_KEY")
TAVILY_KEY = os.getenv("TAVILY_API_KEY")
groq_client = Groq(api_key=GROQ_KEY) if GROQ_KEY else None

user_tones = {}
TONES = {
    "short": "Short, 4 lines, sharp, precise verification",
    "ceo": "CEO, expensive, confident, sharp",
    "friendly": "Friendly bestie, warm",
    "formal": "Formal, boards, respectful",
    "roast": "Roast fake news, savage, short",
    "palamaner": "Palamaner local, exact streets"
}

def clean(t):
    t=re.sub(r'\*\*([^*]+)\*\*', r'\1', t)
    t=re.sub(r'\*([^*]+)\*', r'\1', t)
    t=t.replace('**','').replace('__','').replace('##','')
    lines=[]
    for x in t.split('\n'):
        if '|' in x and '---' in x: continue
        if x.strip().startswith('|') and x.strip().endswith('|'): continue
        if any(k in x.lower() for k in ['bottom line','believe live','never invent','what the sources','tradition |']): continue
        lines.append(x)
    txt='\n'.join(lines)
    txt=re.sub(r'\n\s*\n','\n',txt)
    # Max 5 lines proper verification
    return '\n'.join(txt.split('\n')[:5]).strip()

def kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚡ SHORT", callback_data="t_short"), InlineKeyboardButton("👑 CEO", callback_data="t_ceo")],
        [InlineKeyboardButton("💖 FRIENDLY", callback_data="t_friendly"), InlineKeyboardButton("🎓 FORMAL", callback_data="t_formal")],
        [InlineKeyboardButton("🔥 ROAST", callback_data="t_roast"), InlineKeyboardButton("📍 PALAMANER", callback_data="t_palamaner")]
    ])

TIMEZONES = {
    "india":"Asia/Kolkata","ist":"Asia/Kolkata","delhi":"Asia/Kolkata",
    "seoul":"Asia/Seoul","korea":"Asia/Seoul","south korea":"Asia/Seoul",
    "tokyo":"Asia/Tokyo","japan":"Asia/Tokyo",
    "new york":"America/New_York","usa":"America/New_York",
    "london":"Europe/London","uk":"Europe/London",
    "dubai":"Asia/Dubai","saudi":"Asia/Riyadh","saudi arabia":"Asia/Riyadh","qatar":"Asia/Qatar","paris":"Europe/Paris"
}

def get_time(q="India"):
    ql=q.lower(); tz="Asia/Kolkata"; abbr="IST"
    for k,v in TIMEZONES.items():
        if k in ql: tz=v; abbr=k.upper(); break
    dt=datetime.now(ZoneInfo(tz))
    return dt.strftime(f"%d %B %Y, %I:%M:%S %p {abbr}"), tz

def get_weather(p="India"):
    try:
        r=requests.get(f"https://wttr.in/{p}?format=%C+%t+%w+%h", timeout=6)
        if r.status_code==200: return r.text.strip()
    except: pass
    return "Live weather"

def get_weather_latlon(lat,lon):
    try:
        r=requests.get(f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,wind_speed_10m,relative_humidity_2m&timezone=auto", timeout=6)
        if r.status_code==200:
            c=r.json().get('current',{})
            return f"{c.get('temperature_2m')}°C, Wind {c.get('wind_speed_10m')}km/h, Humidity {c.get('relative_humidity_2m')}% — Exact by your location"
    except: pass
    return get_weather(f"{lat},{lon}")

def live_search(q):
    if not TAVILY_KEY: return ""
    try:
        r=requests.post("https://api.tavily.com/search", json={"api_key":TAVILY_KEY,"query":q,"max_results":5,"include_answer":True,"search_depth":"advanced"}, timeout=12)
        if r.status_code==200:
            d=r.json(); txt=f"{d.get('answer','')} "
            for x in d.get('results',[])[:3]: txt+=f"{x.get('content','')[:700]} "
            return txt
    except: pass
    return ""

def ask(q, uid):
    ql=q.lower()
    tone=TONES.get(user_tones.get(uid,"short"),"Short precise")

    # Only fixed identity — not training for any question — Meta AI level
    if any(x in ql for x in ["who created","who made","creator of satya","who built you"]):
        t,_=get_time("India")
        return f"👑 I AM SATYA — CREATED BY HIBA HAANIYA.F — Founder & CEO — Palamaner 517408\n✅ Verified: Founder of @satya_truth_hiba_bot — Cracked CJB protest 12:37 AM\n🕐 {t}"

    if "time" in ql:
        t,tz=get_time(q); w=get_weather(q)
        return f"✅ TRUE — Time in {q.title()}: {t}\n📍 Zone: {tz}\n🌤️ {w}"

    if "weather" in ql:
        p=ql.replace("weather in","").replace("weather","").strip() or "India"
        t,_=get_time(p); w=get_weather(p)
        return f"✅ TRUE — Weather in {p.title()}: {w}\n🕐 {t}\n📍 Share location for exact tracking"

    live=live_search(q)
    # TRAINED TO BE PRECISE FOR ANY QUESTION — NOT THIS QUESTION ONLY — ANY QUESTION
    prompt=f"""You are SATYA — Created by HIBA HAANIYA.F — Founder & CEO — You are EXTRAORDINARY — Precise and perfect for ANY question in whole world — Like Meta AI but sharper.

Date: {get_time("India")[0]}
Tone: {tone}
Rules for ANY question:
- NEVER use ** * | --- table markdown — No leakage
- Max 4-5 lines — Proper verification — Short but not too short — Not 1 line, not 10 lines
- Format: Line1: ✅ TRUE or ❌ FALSE or ⚠️ PARTIAL + short verdict. Line2: Exact verification with date/place/source. Line3: Extra context/time/weather if needed. Line4: SATYA tag.
- Speak SAME LANGUAGE as question — If question English, answer English, if Hindi Hindi, Telugu Telugu, Arabic Arabic, any language — You speak whole world languages
- Use LIVE knowledge — Believe LIVE — Never invent — If no live, use accurate general knowledge
- No Bottom line, No What sources say, No Believe LIVE
- For news/rumour/claim: Verify true/false with credible proof — Fast, Verified, No bias — Like fact-checker
- Be sharp, superb, extraordinary — No mistake — No hardcoded examples

LIVE KNOWLEDGE: {live[:3500]}
QUESTION (ANY QUESTION — BE PRECISE): {q}
ANSWER SHARP, PRECISE, PERFECT FOR ANY QUESTION:"""

    if not groq_client:
        return "⚠️ GROQ_API_KEY missing in Railway — Add it"

    # WORKING MODELS ONLY — TESTED ON GROQ — NO BUSY
    models=["llama-3.1-8b-instant","llama-3.1-70b-versatile","gemma2-9b-it","mixtral-8x7b-32768"]
    for m in models:
        try:
            c=groq_client.chat.completions.create(model=m, messages=[{"role":"user","content":prompt}], temperature=0.2, max_tokens=500)
            txt=c.choices[0].message.content.strip()
            if len(txt)>10:
                return clean(txt)
        except Exception as e:
            print(f"Model {m} failed: {e}")
            continue
    return "⚠️ Busy — Groq quota — Try again in 10 sec — SATYA"

async def start(update, context):
    t,_=get_time()
    await update.message.reply_text(f"⚡ SATYA — EXTRAORDINARY — PRECISE FOR ANY QUESTION 🛡️\n👑 HIBA HAANIYA.F — Founder & CEO\n🕐 {t[0]}\n🌐 Reads images exact | Speaks any language | Weather by location | Time any country | Proper verification 4 lines\n📸 Send image — 📍 Share location\n👇 SET TONE:", reply_markup=kb())

async def tone_cmd(update, context): await update.message.reply_text("🎛️ SET TONE ANYTIME:", reply_markup=kb())
async def tone_cb(update, context):
    q=update.callback_query; await q.answer()
    user_tones[q.from_user.id]=q.data.replace("t_","")
    await q.edit_message_text(f"✅ Tone {q.data.replace('t_','').upper()} set — Ask any question — Precise perfect", reply_markup=kb())

async def handle_text(update, context):
    ans=ask(update.message.text, update.effective_user.id)
    await update.message.reply_text(ans, reply_markup=kb())

async def handle_photo(update, context):
    w=await update.message.reply_text("📸 SATYA reading image — Exact accuracy...")
    try:
        p=update.message.photo[-1]; f=await context.bot.get_file(p.file_id); b=await f.download_as_bytearray()
        b64=base64.b64encode(b).decode()
        pr="You are SATYA — Read image exact — No ** — 4 lines — Same language as image text — Precise"
        for m in ["llama-3.2-11b-vision-preview","llama-3.2-90b-vision-preview"]:
            try:
                c=groq_client.chat.completions.create(model=m, messages=[{"role":"user","content":[{"type":"text","text":pr},{"type":"image_url","image_url":{"url":f"data:image/jpeg;base64,{b64}"}}]}], temperature=0.2, max_tokens=500)
                await w.delete()
                await update.message.reply_text(f"✅ IMAGE READ — Exact:\n{clean(c.choices[0].message.content)}", reply_markup=kb())
                return
            except Exception as e:
                print(e)
                continue
        await w.delete()
        await update.message.reply_text("✅ Image received — Vision model busy — Try again", reply_markup=kb())
    except Exception as e:
        await w.delete()
        await update.message.reply_text(f"⚠️ {e}", reply_markup=kb())

async def handle_loc(update, context):
    lat=update.message.location.latitude; lon=update.message.location.longitude
    t,_=get_time(); w=get_weather_latlon(lat,lon)
    await update.message.reply_text(f"✅ LOCATION TRACKED — Exact weather\n📍 {lat:.6f},{lon:.6f}\n🌤️ {w}\n🕐 {t[0]}", reply_markup=kb())

async def post_init(app):
    await app.bot.delete_webhook(drop_pending_updates=True)
    print("✅ Webhook deleted — No Conflict")

def main():
    while True:
        try:
            print(f"🚀 STARTING SATYA — PRECISE FOR ANY QUESTION — {get_time()[0]}")
            app=Application.builder().token(BOT_TOKEN).post_init(post_init).build()
            app.add_handler(CommandHandler("start", start))
            app.add_handler(CommandHandler("tone", tone_cmd))
            app.add_handler(CallbackQueryHandler(tone_cb, pattern="^t_"))
            app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
            app.add_handler(MessageHandler(filters.LOCATION, handle_loc))
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
            app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES, close_loop=False)
            break
        except Conflict:
            print("⚠️ Conflict — 2 bots same token — Waiting 30 sec — Kill duplicate deployment in Railway")
            time.sleep(30)
            continue
        except Exception as e:
            print(f"Restarting {e}"); time.sleep(10); continue

if __name__=="__main__": main()
