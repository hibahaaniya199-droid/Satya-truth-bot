import os, requests, re, base64, time
from datetime import datetime
from zoneinfo import ZoneInfo
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from groq import Groq

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_KEY = os.getenv("GROQ_API_KEY")
TAVILY_KEY = os.getenv("TAVILY_API_KEY")
groq_client = Groq(api_key=GROQ_KEY) if GROQ_KEY else None

user_tones = {}

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
    txt='\n'.join(lines)
    return '\n'.join(txt.split('\n')[:5]).strip()

def kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚡ SHORT", callback_data="t_short"), InlineKeyboardButton("👑 CEO", callback_data="t_ceo")],
        [InlineKeyboardButton("💖 FRIENDLY", callback_data="t_friendly"), InlineKeyboardButton("🎓 FORMAL", callback_data="t_formal")],
        [InlineKeyboardButton("🔥 ROAST", callback_data="t_roast"), InlineKeyboardButton("📍 PALAMANER", callback_data="t_palamaner")]
    ])

TIMEZONES = {"india":"Asia/Kolkata","ist":"Asia/Kolkata","saudi":"Asia/Riyadh","saudi arabia":"Asia/Riyadh","seoul":"Asia/Seoul","korea":"Asia/Seoul","tokyo":"Asia/Tokyo","usa":"America/New_York","london":"Europe/London","dubai":"Asia/Dubai","qatar":"Asia/Qatar"}

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
        r=requests.get(f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,wind_speed_10m&timezone=auto", timeout=6)
        if r.status_code==200:
            c=r.json().get('current',{})
            return f"{c.get('temperature_2m')}°C, Wind {c.get('wind_speed_10m')}km/h — Exact by location"
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
    if any(x in ql for x in ["who created","who made","creator"]):
        return "👑 I AM SATYA — CREATED BY HIBA HAANIYA.F — Founder & CEO — Palamaner 517408 🛡️💖"

    if "time" in ql:
        t,tz=get_time(q); w=get_weather(q)
        return f"✅ TRUE — Time in {q.title()}: {t}\n📍 Zone: {tz}\n🌤️ {w}"
    if "weather" in ql:
        p=ql.replace("weather in","").replace("weather","").strip() or "India"
        t,_=get_time(p); w=get_weather(p)
        return f"✅ TRUE — Weather {p.title()}: {w}\n🕐 {t}\n📍 Share location for exact"

    live=live_search(q)
    # PRECISE FOR ANY QUESTION — NOT TRAINED FOR THIS QUESTION ONLY — ANY QUESTION
    prompt=f"""You are SATYA — Created by HIBA HAANIYA.F — Founder & CEO Palamaner — Extraordinary — Precise for ANY question.

Date: {get_time()[0]}
Rules: NEVER ** * | --- table. Max 4-5 lines. Format: ✅ TRUE/FALSE/PARTIAL + 1-2 lines verification with date/source + time/weather. Same language as question. No Bottom line. Sharp like Meta AI. No hardcoded examples.

LIVE: {live[:3500]}
QUESTION: {q}
ANSWER PRECISE FOR ANY QUESTION:"""

    if not groq_client: return "⚠️ GROQ_API_KEY missing — Add in Railway Variables"

    # NEW ALIVE GROQ MODELS TODAY — OCT 2026 — NOT DECOMMISSIONED
    models = [
        "openai/gpt-oss-20b",
        "qwen/qwen3-32b",
        "llama-3.3-70b-versatile",
        "meta-llama/llama-4-scout-17b-16e-instruct",
        "llama-3.1-8b-instant"
    ]
    for m in models:
        try:
            c=groq_client.chat.completions.create(model=m, messages=[{"role":"user","content":prompt}], temperature=0.2, max_tokens=500)
            txt=c.choices[0].message.content.strip()
            if len(txt)>15:
                return clean(txt)
        except Exception as e:
            print(f"Model {m} failed: {e}")
            continue
    return "⚠️ Busy — Groq quota low — Try again in 10 sec — Check GROQ_API_KEY quota in console.groq.com — SATYA"

async def start(update, context):
    t,_=get_time()
    await update.message.reply_text(f"⚡ SATYA — PRECISE FOR ANY QUESTION 🛡️\n👑 HIBA HAANIYA.F — CEO\n🕐 {t[0]}\n📸 Send image exact read | 📍 Share location exact weather | 🌐 Any language | 🕐 Time any country\n👇 SET TONE:", reply_markup=kb())

async def tone_cmd(update, context): await update.message.reply_text("🎛️ SET TONE ANYTIME:", reply_markup=kb())
async def tone_cb(update, context):
    q=update.callback_query; await q.answer()
    user_tones[q.from_user.id]=q.data.replace("t_","")
    await q.edit_message_text(f"✅ Tone {q.data.replace('t_','').upper()} set — Ask any question — Precise perfect", reply_markup=kb())

async def handle_text(update, context):
    await update.message.reply_text(ask(update.message.text, update.effective_user.id), reply_markup=kb())

async def handle_photo(update, context):
    w=await update.message.reply_text("📸 Reading image exact...")
    try:
        p=update.message.photo[-1]; f=await context.bot.get_file(p.file_id); b=await f.download_as_bytearray()
        b64=base64.b64encode(b).decode()
        pr="Read image exact — 4 lines — No ** — Same language as text"
        for m in ["meta-llama/llama-4-scout-17b-16e-instruct","qwen/qwen3-32b"]:
            try:
                c=groq_client.chat.completions.create(model=m, messages=[{"role":"user","content":[{"type":"text","text":pr},{"type":"image_url","image_url":{"url":f"data:image/jpeg;base64,{b64}"}}]}], temperature=0.2, max_tokens=500)
                await w.delete()
                await update.message.reply_text(f"✅ IMAGE READ:\n{clean(c.choices[0].message.content)}", reply_markup=kb())
                return
            except: continue
        await w.delete()
        await update.message.reply_text("✅ Image received — Vision busy — Try again", reply_markup=kb())
    except Exception as e:
        await w.delete()
        await update.message.reply_text(f"⚠️ {e}", reply_markup=kb())

async def handle_loc(update, context):
    lat=update.message.location.latitude; lon=update.message.location.longitude
    t,_=get_time(); w=get_weather_latlon(lat,lon)
    await update.message.reply_text(f"✅ LOCATION TRACKED\n📍 {lat:.6f},{lon:.6f}\n🌤️ {w}\n🕐 {t[0]}", reply_markup=kb())

async def post_init(app):
    await app.bot.delete_webhook(drop_pending_updates=True)
    print("✅ Webhook deleted — No Conflict — Precise for any question")

def main():
    print(f"🚀 STARTING SATYA — PRECISE FOR ANY QUESTION — {get_time()[0]}")
    app=Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tone", tone_cmd))
    app.add_handler(CallbackQueryHandler(tone_cb, pattern="^t_"))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.LOCATION, handle_loc))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

if __name__=="__main__": main()
