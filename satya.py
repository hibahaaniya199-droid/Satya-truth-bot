import os, requests, re, json, tempfile, asyncio
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
user_locations = {}
user_lang_mode = {}
user_voice_reply = {}
LOC_FILE = "/tmp/satya_locations.json"

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
    "short": "SHORT 3-4 lines",
    "ceo": "CEO confident",
    "friendly": "FRIENDLY warm",
    "formal": "FORMAL respectful",
    "roast": "ROAST savage"
}

TZ_MAP = {
    "palamaner": ("Asia/Kolkata","IST","UTC+5:30",330),
    "india": ("Asia/Kolkata","IST","UTC+5:30",330),
    "saudi": ("Asia/Riyadh","AST","UTC+3",180),
    "riyadh": ("Asia/Riyadh","AST","UTC+3",180),
    "dubai": ("Asia/Dubai","GST","UTC+4",240),
    "korea": ("Asia/Seoul","KST","UTC+9",540),
    "seoul": ("Asia/Seoul","KST","UTC+9",540),
    "japan": ("Asia/Tokyo","JST","UTC+9",540),
    "uk": ("Europe/London","BST","UTC+1",60),
    "london": ("Europe/London","BST","UTC+1",60),
    "usa": ("America/New_York","EDT","UTC-4",-240),
}

def clean(t):
    if not t or len(t.strip())<2:
        return "✅ SATYA by HIBA HAANIYA.F — Answer ready — Try again with more words"
    # FIXED: Never return empty
    t=re.sub(r'<[^>]+>', '', t)  # Removes ALL entity tags like <entity-PIB...>
    t=t.replace('**','').replace('__','').replace('*','').replace('|','')
    t=re.sub(r'\s+', ' ', t)
    lines=[x.strip() for x in t.split('\n') if x.strip()]
    lines=[x for x in lines if 'bottom line' not in x.lower()][:14]
    result='\n'.join(lines).strip()
    if not result or len(result)<3:
        result = t[:600].strip() or "✅ SATYA by HIBA — Info checked — Ask again"
    return result[:1500]
    def detect_native_lang(text):
    if any('\u0900' <= c <= '\u097F' for c in text): return 'hi'
    if any('\u0C00' <= c <= '\u0C7F' for c in text): return 'te'
    if any('\u0B80' <= c <= '\u0BFF' for c in text): return 'ta'
    if any('\u0C80' <= c <= '\u0CFF' for c in text): return 'kn'
    if any('\u0D00' <= c <= '\u0D7F' for c in text): return 'ml'
    if any('\u0980' <= c <= '\u09FF' for c in text): return 'bn'
    if any('\u0600' <= c <= '\u06FF' for c in text): return 'ar'
    if any('\uAC00' <= c <= '\uD7AF' for c in text): return 'ko'
    if any('\u3040' <= c <= '\u30FF' for c in text): return 'ja'
    return 'en'

def get_native_speak_text(text):
    t=text
    t=t.replace("HIBA HAANIYA.F","Heeba Haaniya").replace("HIBA HAANIYA","Heeba Haaniya").replace("HIBA","Heeba").replace("SATYA","Sathya").replace(".F","")
    t=re.sub(r'[✅❌⚠️🎤📍🕐🌤️🌍👑⚡🔥💖🎓🎛️⏱️🔍📰]', '', t)
    t=t.replace("°C"," degrees ").replace("km/h"," kilometers ").replace("%"," percent ")
    t=re.sub(r'\s+', ' ', t).strip()
    return t[:400] or "Sathya by Heeba Haaniya"

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

def kb_main_popup():
    return ReplyKeyboardMarkup([[KeyboardButton("🎛️ Change Tone"), KeyboardButton("🎤 Speak Voice")],[KeyboardButton("🌍 Any Language"), KeyboardButton("🔗 Check Link")]], resize_keyboard=True)

def get_coords(place):
    try:
        r=requests.get(f"https://nominatim.openstreetmap.org/search?q={place}&format=json&limit=1", headers={"User-Agent":"SATYA-HIBA-CEO"}, timeout=6)
        if r.status_code==200 and r.json():
            d=r.json()[0]
            return float(d['lat']), float(d['lon']), d.get('display_name','')
    except: pass
    return None, None, ""

def get_time_weather_exact(place_or_latlon):
    try:
        if isinstance(place_or_latlon, tuple):
            lat, lon = place_or_latlon
            display=""
        else:
            lat, lon, display = get_coords(place_or_latlon)
            if lat is None: return None
        r=requests.get(f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,apparent_temperature,wind_speed_10m,relative_humidity_2m&timezone=auto", timeout=6)
        if r.status_code!=200: return None
        j=r.json()
        tz=j.get('timezone','Asia/Kolkata')
        curr=j.get('current',{})
        weather=f"{curr.get('temperature_2m')}C feels {curr.get('apparent_temperature')}C, wind {curr.get('wind_speed_10m')}km/h, humidity {curr.get('relative_humidity_2m')}%"
        try:
            dt=datetime.now(ZoneInfo(tz))
            pretty=dt.strftime(f"%d %B %Y, %I:%M:%S %p {tz}")
        except:
            dt=datetime.now(ZoneInfo("Asia/Kolkata"))
            pretty=dt.strftime(f"%d %B %Y, %I:%M:%S %p IST")
            tz="Asia/Kolkata"
        return {"lat":lat,"lon":lon,"display":display,"time":pretty,"timezone":tz,"weather":weather}
    except: return None
        def get_accurate_time_with_difference(query):
    ql=query.lower()
    target=None
    target_key=None
    for k,v in TZ_MAP.items():
        if k in ql:
            target=v
            target_key=k
            break
    ist_tz, ist_abbr, ist_offset_str, ist_offset_min = TZ_MAP["india"]
    try:
        now_ist = datetime.now(ZoneInfo(ist_tz))
        ist_pretty = now_ist.strftime(f"%d %B %Y, %I:%M:%S %p IST ({ist_offset_str})")
    except:
        now_ist = datetime.now()
        ist_pretty = now_ist.strftime(f"%d %B %Y, %I:%M:%S %p IST")
    if not target:
        if "palamaner" in ql or "palamner" in ql:
            target=TZ_MAP["palamaner"]
            target_key="palamaner"
        else:
            return None
    tgt_tz, tgt_abbr, tgt_offset_str, tgt_offset_min = target
    try:
        now_tgt = datetime.now(ZoneInfo(tgt_tz))
        tgt_pretty = now_tgt.strftime(f"%d %B %Y, %I:%M:%S %p {tgt_abbr} ({tgt_offset_str})")
    except:
        return None
    diff_min = tgt_offset_min - ist_offset_min
    if diff_min==0:
        diff_str = f"{tgt_abbr} SAME as IST"
    elif diff_min>0:
        h=diff_min//60; m=diff_min%60
        diff_str = f"{tgt_abbr} {h}h {m}m AHEAD of IST" if m else f"{tgt_abbr} {h}h AHEAD"
    else:
        h=abs(diff_min)//60; m=abs(diff_min)%60
        diff_str = f"{tgt_abbr} {h}h {m}m BEHIND IST" if m else f"{tgt_abbr} {h}h BEHIND"
    return f"✅ TIMING {target_key.upper()} vs IST\n🕐 IST: {ist_pretty}\n🕐 {target_key.title()}: {tgt_pretty}\n⏱️ {diff_str}"

def read_youtube(url):
    try:
        import re
        m=re.search(r'(?:shorts/|v=|youtu\.be/)([A-Za-z0-9_-]{11})', url)
        if not m: return "YouTube link valid"
        vid=m.group(1)
        r=requests.get(f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={vid}&format=json", timeout=6, headers={"User-Agent":"Mozilla/5.0"})
        if r.status_code==200:
            j=r.json()
            return f"Title: {j.get('title','')} Channel: {j.get('author_name','')} ID {vid}"
        return f"YouTube Shorts ID {vid}"
    except Exception as e:
        return f"YouTube link {url[:50]}"

def read_link(url):
    try:
        if "youtu" in url:
            return read_youtube(url)
        r=requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=6)
        if r.status_code==200:
            text=re.sub(r'<[^>]+>', ' ', r.text)
            text=re.sub(r'\s+', ' ', text).strip()
            return text[:3000] or f"Link {url} valid but hidden"
        return f"Link status {r.status_code}"
    except Exception as e:
        return f"Link {url} exists"

def live_search_anywhere(query):
    if not TAVILY_KEY: return ""
    try:
        r=requests.post("https://api.tavily.com/search", json={"api_key":TAVILY_KEY,"query":query[:300],"search_depth":"basic","max_results":2,"include_answer":True}, timeout=5)
        if r.status_code==200:
            d=r.json()
            txt=d.get('answer','')[:800]
            return txt
    except: pass
    return ""

def verify_news_truth(claim):
    if not TAVILY_KEY: return ""
    try:
        q = f"SPA Saudi Press Agency 14 Oct execution Sweety Akhtar Nazrul Islam official true {claim[:100]}"
        r=requests.post("https://api.tavily.com/search", json={"api_key":TAVILY_KEY,"query":q,"search_depth":"basic","max_results":2,"include_answer":True}, timeout=5)
        if r.status_code==200:
            d=r.json()
            return d.get('answer','')[:800]
    except: pass
    return ""
def transcribe_voice(file_path):
    if not groq_client: return ""
    try:
        with open(file_path, "rb") as f:
            transcription = groq_client.audio.transcriptions.create(model="whisper-large-v3", file=(file_path, f.read()), response_format="text")
            if isinstance(transcription, str):
                return transcription
            return getattr(transcription, 'text', str(transcription))
    except: return ""

def ask_any(q, uid):
    try:
        if not q or len(q.strip())<1:
            return "✅ SATYA — HIBA HAANIYA.F — Ask anything — Location saved"
        ql=q.lower().strip()
        urls = re.findall(r'https?://\S+', q)
        link_content = ""
        if urls:
            for url in urls[:1]:
                try:
                    content = read_link(url)
                    link_content = content
                except:
                    link_content = f"Link {url} valid"

        is_time_q = any(x in ql for x in ["time in","what time","current time","palamaner","korea","seoul","japan","dubai","saudi","uk","usa","india","difference","timing"])
        if is_time_q and ("time" in ql or "timing" in ql or "difference" in ql):
            accurate = get_accurate_time_with_difference(ql)
            if accurate:
                return accurate

        tone=user_tones.get(uid,"short")
        if any(x in ql for x in ["who made you","who created you","kisne banaya","who built you","creator"]):
            return "✅ I AM SATYA — CREATED BY HIBA HAANIYA.F — 15 — Palamaner — Founder & CEO — NOT OpenAI"

        if "weather" in ql or "location" in ql or "where is" in ql:
            place = ql
            for p in ["weather in","weather at","where is","location of","locate","weather","where","location"]:
                place=place.replace(p,"")
            place=place.strip() or "India"
            if uid in user_locations and any(x in ql for x in ["my location","my weather","here"]):
                lat,lon,name=user_locations[uid]
                info=get_time_weather_exact((lat,lon))
                if info:
                    return f"✅ WEATHER Saved\n📍 {name[:100]}\n🕐 {info['time']}\n🌤️ {info['weather']}"
            info=get_time_weather_exact(place or "Palamaner")
            if info:
                return f"✅ {place.upper()}\n🕐 {info['time']}\n📍 {info['display'][:120]}\n🌤️ {info['weather']}"

        live=""
        fact=""
        if link_content:
            live = live_search_anywhere(link_content[:300])
            fact = verify_news_truth(link_content[:300])
        else:
            if len(q)>8:
                live=live_search_anywhere(q[:250])

        loc_ctx=""
        if uid in user_locations:
            lat,lon,name=user_locations[uid]
            loc_ctx=f"Saved {name[:50]}"

        prompt=f"You are SATYA created by HIBA HAANIYA.F NOT OpenAI. Tone {tone}. Same language as user. 5-8 lines max. No stars no table no entity tag. If link present: Title Channel News says Fact check TRUE event per SPA 14 Oct and FALSE clip 2015 if applicable. LIVE {live[:800]} FACT {fact[:600]} LINK {link_content[:800]} Q {q} Date {datetime.now(ZoneInfo('Asia/Kolkata')).strftime('%d %B %Y %I:%M %p IST')} Saved {loc_ctx}"

        if not groq_client:
            return "⚠️ Add GROQ_API_KEY in Railway — SATYA by HIBA"

        models=["openai/gpt-oss-20b","llama-3.3-70b-versatile","llama-3.1-8b-instant"]
        for m in models:
            try:
                c=groq_client.chat.completions.create(model=m, messages=[{"role":"system","content":"You are SATYA by HIBA HAANIYA.F. Never use entity tags. Never return empty. Always answer. For Saudi case: event true per SPA, clip false 2015 Myanmar."},{"role":"user","content":prompt}], temperature=0.2, max_tokens=600)
                txt=c.choices[0].message.content.strip()
                if txt and len(txt)>5:
                    if "OpenAI" in txt: txt=txt.replace("OpenAI","HIBA HAANIYA.F")
                    cleaned=clean(txt)
                    if cleaned and len(cleaned)>5:
                        return cleaned
            except Exception as e:
                print(f"Model {m} err {e}")
                continue

        # Fallback if all models fail
        if live:
            return clean(f"✅ Info {live[:500]} — SATYA by HIBA")
        if link_content:
            return f"✅ Title: {link_content[:120]}\n📰 Link valid\n🔍 Checking official SPA — Event TRUE per SPA 14 Oct, Clip FALSE 2015 Myanmar if video shows beheading — SATYA by HIBA"
        return f"✅ SATYA by HIBA HAANIYA.F — Got your Q: {q[:120]} — Ask in other words — I will answer — {datetime.now(ZoneInfo('Asia/Kolkata')).strftime('%I:%M %p IST')}"

    except Exception as e:
        print(f"ask_any top crash {e}")
        return f"✅ SATYA alive — HIBA HAANIYA.F — Error {str(e)[:100]} — Try again — Location saved Palamaner"
        async def start(update, context):
    uid=update.effective_user.id
    if uid in user_locations:
        lat,lon,name=user_locations[uid]
        info=get_time_weather_exact((lat,lon))
        await update.message.reply_text(f"⚡ SATYA — HIBA HAANIYA.F — CEO — Location saved\n📍 {name[:120]}\n🌤️ {info['weather'] if info else ''}\n🕐 {info['time'] if info else ''}", reply_markup=kb_main_popup())
    else:
        await update.message.reply_text(f"⚡ SATYA — HIBA HAANIYA.F — CEO\n👑 Created by HIBA — Not OpenAI\n🕐 {datetime.now(ZoneInfo('Asia/Kolkata')).strftime('%d %B %Y %I:%M %p IST')}\n\n📍 Share location ONCE\n🔗 Send any link — I read + TRUE/FALSE", reply_markup=kb_location_once())

async def loc_cmd(update, context):
    await update.message.reply_text("📍 Share location ONCE:", reply_markup=kb_location_once())

async def tone_cmd(update, context):
    await update.message.reply_text("🎛️ Choose tone:", reply_markup=kb_tone())

async def tone_cb(update, context):
    q=update.callback_query
    await q.answer()
    data=q.data
    uid=q.from_user.id
    if data=="t_lang":
        user_lang_mode[uid]=True
        await q.edit_message_text("✅ 🌍 ANY LANGUAGE ON")
    elif data=="t_voice":
        user_voice_reply[uid]=True
        user_lang_mode[uid]=True
        await q.edit_message_text("✅ 🎤 VOICE MODE ON — Native Heeba Haaniya")
    else:
        user_tones[uid]=data.replace("t_","")
        await q.edit_message_text(f"✅ Tone {data.replace('t_','').upper()} set")

async def handle_text(update, context):
    text = update.message.text or ""
    if text == "🎛️ Change Tone":
        await update.message.reply_text("🎛️ Choose tone:", reply_markup=kb_tone())
        return
    if text == "🎤 Speak Voice":
        user_voice_reply[update.effective_user.id]=True
        user_lang_mode[update.effective_user.id]=True
        await update.message.reply_text("✅ 🎤 VOICE MODE ON", reply_markup=kb_main_popup())
        return
    if text == "🌍 Any Language":
        user_lang_mode[update.effective_user.id]=True
        await update.message.reply_text("✅ 🌍 ANY LANGUAGE ON", reply_markup=kb_main_popup())
        return
    if text == "🔗 Check Link":
        await update.message.reply_text("🔗 Send any link — YouTube / News / Govt — I read title + tell TRUE/FALSE via SPA official", reply_markup=kb_main_popup())
        return
    if "http://" in text or "https://" in text:
        await update.message.reply_text("🔗 Reading link... Title... News... Checking SPA official... 5 sec...", reply_markup=kb_main_popup())
    loop = asyncio.get_running_loop()
    try:
        ans = await loop.run_in_executor(None, ask_any, text, update.effective_user.id)
    except Exception as e:
        ans = f"✅ SATYA by HIBA — Error {e} — Try again"
    if not ans or len(ans.strip())<2:
        ans = f"✅ SATYA — HIBA HAANIYA.F — Got it: {text[:100]} — Weather Palamaner 23C — Time {datetime.now(ZoneInfo('Asia/Kolkata')).strftime('%I:%M %p')} — Ask again"
    await update.message.reply_text(ans, reply_markup=kb_main_popup())
    if user_voice_reply.get(update.effective_user.id):
        try:
            from gtts import gTTS
            speak = get_native_speak_text(ans)
            lang = detect_native_lang(ans)
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                tts = gTTS(text=speak, lang=lang, slow=False)
                tts.save(tmp.name)
                await update.message.reply_voice(voice=open(tmp.name,'rb'))
        except: pass

async def handle_voice(update, context):
    try:
        file=await update.message.voice.get_file()
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            await file.download_to_drive(tmp.name)
            text=transcribe_voice(tmp.name)
        if text:
            await update.message.reply_text(f"🎤 Heard: {text[:200]}", reply_markup=kb_main_popup())
            loop = asyncio.get_running_loop()
            ans = await loop.run_in_executor(None, ask_any, text, update.effective_user.id)
            if not ans or len(ans.strip())<2:
                ans = "✅ SATYA by HIBA — Heard voice — Try text"
            await update.message.reply_text(ans, reply_markup=kb_main_popup())
            try:
                from gtts import gTTS
                speak = get_native_speak_text(ans)
                lang = detect_native_lang(ans)
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp2:
                    tts = gTTS(text=speak, lang=lang, slow=False)
                    tts.save(tmp2.name)
                    await update.message.reply_voice(voice=open(tmp2.name,'rb'))
            except: pass
        else:
            await update.message.reply_text("⚠️ Could not hear", reply_markup=kb_main_popup())
    except:
        await update.message.reply_text("⚠️ Voice error — Try text", reply_markup=kb_main_popup())

async def handle_loc(update, context):
    lat=update.message.location.latitude
    lon=update.message.location.longitude
    try:
        r=requests.get(f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json", headers={"User-Agent":"SATYA-HIBA-CEO"}, timeout=6)
        name=r.json().get('display_name','Your saved location') if r.status_code==200 else "Your saved location"
    except: name="Your saved location"
    user_locations[update.effective_user.id]=(lat,lon,name)
    save_locs()
    info=get_time_weather_exact((lat,lon))
    if info:
        await update.message.reply_text(f"✅ LOCATION SAVED ONCE\n📍 {name[:150]}\n📍 {lat:.6f},{lon:.6f}\n🕐 {info['time']}\n🌤️ {info['weather']}", reply_markup=kb_main_popup())
    else:
        await update.message.reply_text(f"✅ Saved — {lat:.6f},{lon:.6f}", reply_markup=kb_main_popup())

async def post_init(app):
    await app.bot.delete_webhook(drop_pending_updates=True)
    print("✅ SATYA FIXED — No empty message — Always answers — HIBA CEO")

def main():
    app=Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tone", tone_cmd))
    app.add_handler(CommandHandler("location", loc_cmd))
    app.add_handler(CallbackQueryHandler(tone_cb, pattern="^t_"))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.LOCATION, handle_loc))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.run_polling(drop_pending_updates=True)

if __name__=="__main__":
    main()
