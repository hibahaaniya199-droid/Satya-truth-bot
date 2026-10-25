import os, requests, re, json, tempfile
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
    "short": "SHORT — 3-4 lines max",
    "ceo": "CEO — expensive confident",
    "friendly": "FRIENDLY — bestie warm",
    "formal": "FORMAL — respectful",
    "roast": "ROAST — roast savage"
}

TZ_MAP = {
    "palamaner": ("Asia/Kolkata","IST","UTC+5:30",330),
    "palamner": ("Asia/Kolkata","IST","UTC+5:30",330),
    "india": ("Asia/Kolkata","IST","UTC+5:30",330),
    "saudi": ("Asia/Riyadh","AST","UTC+3",180),
    "riyadh": ("Asia/Riyadh","AST","UTC+3",180),
    "dubai": ("Asia/Dubai","GST","UTC+4",240),
    "south korea": ("Asia/Seoul","KST","UTC+9",540),
    "korea": ("Asia/Seoul","KST","UTC+9",540),
    "seoul": ("Asia/Seoul","KST","UTC+9",540),
    "japan": ("Asia/Tokyo","JST","UTC+9",540),
    "uk": ("Europe/London","BST","UTC+1",60),
    "london": ("Europe/London","BST","UTC+1",60),
    "usa": ("America/New_York","EDT","UTC-4",-240),
}

def clean(t):
    t=re.sub(r'\*\*([^*]+)\*\*', r'\1', t)
    t=re.sub(r'\*([^*]+)\*', r'\1', t)
    t=t.replace('**','').replace('__','')
    lines=[x for x in t.split('\n') if not ('|' in x and '---' in x) and not (x.strip().startswith('|') and x.strip().endswith('|'))]
    lines=[x for x in lines if 'bottom line' not in x.lower()]
    return '\n'.join('\n'.join(lines).split('\n')[:12]).strip()

def detect_native_lang(text):
    if any('\u0900' <= c <= '\u097F' for c in text): return 'hi'
    if any('\u0C00' <= c <= '\u0C7F' for c in text): return 'te'
    if any('\u0B80' <= c <= '\u0BFF' for c in text): return 'ta'
    if any('\u0C80' <= c <= '\u0CFF' for c in text): return 'kn'
    if any('\u0D00' <= c <= '\u0D7F' for c in text): return 'ml'
    if any('\u0980' <= c <= '\u09FF' for c in text): return 'bn'
    if any('\u0600' <= c <= '\u06FF' for c in text):
        if any(x in text for x in ['اردو','میں','ہے']): return 'ur'
        return 'ar'
    if any('\uAC00' <= c <= '\uD7AF' for c in text): return 'ko'
    if any('\u3040' <= c <= '\u30FF' for c in text): return 'ja'
    if any('\u4E00' <= c <= '\u9FFF' for c in text): return 'zh'
    return 'en'

def get_native_speak_text(text):
    t=text
    t=re.sub(r'[✅❌⚠️🎤📍🕐🌤️🌍👑⚡🔥💖🎓🎛️⏱️🔍📰]', '', t)
    t=t.replace("HIBA HAANIYA.F","Heeba Haaniya").replace("HIBA HAANIYA","Heeba Haaniya").replace("HIBA","Heeba").replace("SATYA","Sathya").replace(".F","")
    t=t.replace("Founder & CEO","Founder and CEO")
    t=re.sub(r'Lat.*Lon.*', '', t)
    t=re.sub(r'📍.*\n', '', t)
    t=re.sub(r'\d+\.\d+', '', t)
    t=t.replace("°C"," degrees ").replace("km/h"," kilometers per hour ").replace("%"," percent ")
    t=re.sub(r'\s+', ' ', t).strip()
    return t[:450]def kb_tone():
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
        r=requests.get(f"https://nominatim.openstreetmap.org/search?q={place}&format=json&limit=1", headers={"User-Agent":"SATYA-HIBA-CEO"}, timeout=8)
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
        r=requests.get(f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,apparent_temperature,wind_speed_10m,relative_humidity_2m&timezone=auto", timeout=8)
        if r.status_code!=200: return None
        j=r.json()
        tz=j.get('timezone','Asia/Kolkata')
        curr=j.get('current',{})
        weather=f"{curr.get('temperature_2m')}°C feels {curr.get('apparent_temperature')}°C, wind {curr.get('wind_speed_10m')}km/h, humidity {curr.get('relative_humidity_2m')}%"
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
        diff_str = f"{tgt_abbr} is SAME as IST"
    elif diff_min>0:
        h=diff_min//60
        m=diff_min%60
        if m:
            diff_str = f"{tgt_abbr} is {h}h {m}m AHEAD of IST — IST {now_ist.strftime('%I:%M %p')} = {tgt_abbr} {now_tgt.strftime('%I:%M %p')}"
        else:
            diff_str = f"{tgt_abbr} is {h}h AHEAD of IST"
    else:
        diff_min_abs = abs(diff_min)
        h=diff_min_abs//60
        m=diff_min_abs%60
        if m:
            diff_str = f"{tgt_abbr} is {h}h {m}m BEHIND IST"
        else:
            diff_str = f"{tgt_abbr} is {h}h BEHIND IST"
    weather_info=""
    try:
        lat, lon, disp = get_coords(target_key)
        if lat is not None:
            w=get_time_weather_exact((lat,lon))
            if w:
                weather_info=f"\n🌤️ {w['weather']}"
    except: pass
    return f"✅ TIMING — {target_key.upper()} vs IST\n🕐 IST / Palamaner: {ist_pretty}\n🕐 {target_key.title()} / {tgt_abbr}: {tgt_pretty}\n⏱️ Difference: {diff_str}\n🌐 {tgt_tz} {tgt_offset_str} | IST {ist_offset_str}{weather_info}"

def extract_youtube_id(url):
    m=re.search(r'(?:shorts/|v=|youtu\.be/)([A-Za-z0-9_-]{11})', url)
    if m: return m.group(1)
    return None

def read_youtube(url):
    try:
        vid=extract_youtube_id(url)
        if not vid: return None
        r=requests.get(f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={vid}&format=json", timeout=10, headers={"User-Agent":"Mozilla/5.0"})
        if r.status_code==200:
            j=r.json()
            title=j.get('title','')
            author=j.get('author_name','')
            return f"YouTube Shorts Video ID {vid} — Title: {title} — Channel: {author} — Video about: {title}"
        else:
            return f"YouTube Shorts Video ID {vid} — URL valid"
    except Exception as e:
        return f"YouTube link detected — {e}"

def read_link(url):
    try:
        if "youtube.com" in url or "youtu.be" in url:
            yt = read_youtube(url)
            if yt: return yt
        headers={"User-Agent":"Mozilla/5.0 (SATYA-HIBA-CEO) Chrome/120.0"}
        r=requests.get(url, headers=headers, timeout=12, allow_redirects=True)
        if r.status_code==200:
            text=r.text
            text=re.sub(r'<script.*?</script>', '', text, flags=re.DOTALL)
            text=re.sub(r'<style.*?</style>', '', text, flags=re.DOTALL)
            text=re.sub(r'<[^>]+>', ' ', text)
            text=re.sub(r'\s+', ' ', text).strip()
            if len(text)<100:
                return f"Link {url} — Page exists but content hidden — URL valid"
            return text[:6000]
        else:
            return f"Link status {r.status_code}"
    except Exception as e:
        return f"Could not read link: {e}"

def live_search_anywhere(query):
    if not TAVILY_KEY: return ""
    try:
        r=requests.post("https://api.tavily.com/search", json={"api_key":TAVILY_KEY,"query":query,"search_depth":"advanced","max_results":6,"include_answer":True}, timeout=14)
        if r.status_code==200:
            d=r.json()
            txt=d.get('answer','')+" "
            for it in d.get('results',[])[:5]:
                txt+=it.get('content','')[:1000]+" "
            return txt[:5000]
    except: pass
    return ""

def verify_news_truth(claim):
    if not TAVILY_KEY: return ""
    try:
        q = f"fact check 【entity-PIB¦canonical_name=PIB】 official news {claim} true or false"
        r=requests.post("https://api.tavily.com/search", json={"api_key":TAVILY_KEY,"query":q,"search_depth":"advanced","max_results":6,"include_answer":True}, timeout=15)
        if r.status_code==200:
            d=r.json()
            txt=d.get('answer','')+" "
            for it in d.get('results',[])[:5]:
                txt+=it.get('content','')[:1200]+" "
            return txt[:5000]
    except: pass
    return live_search_anywhere(claim)

def transcribe_voice(file_path):
    if not groq_client: return ""
    try:
        with open(file_path, "rb") as f:
            transcription = groq_client.audio.transcriptions.create(model="whisper-large-v3", file=(file_path, f.read()), response_format="text")
            if isinstance(transcription, str):
                return transcription
            return getattr(transcription, 'text', str(transcription))
    except: return ""def ask_any(q, uid):
    ql=q.lower().strip()
    urls = re.findall(r'https?://\S+', q)
    link_content = ""
    link_title_for_verify = ""
    if urls:
        for url in urls[:2]:
            content = read_link(url)
            link_content += f"\nLINK {url} CONTENT: {content[:4000]}\n"
            link_title_for_verify = content

    is_time_q = any(x in ql for x in ["time in","what time","current time","palamaner time","south korea time","korea time","seoul time","japan time","dubai time","saudi time","uk time","usa time","india time","time difference","timing of"])
    if is_time_q:
        accurate = get_accurate_time_with_difference(ql)
        if accurate:
            return accurate
        info=get_time_weather_exact(ql)
        if info:
            return f"✅ TIMING — {ql.upper()}\n🕐 {info['time']}\n🌐 {info['timezone']}\n📍 {info['display']}\n🌤️ {info['weather']}\n⏱️ IST is UTC+5:30"

    tone=user_tones.get(uid,"short")
    if any(x in ql for x in ["who made you","who created you","kisne banaya","आपको किसने बनाया","who built you","creator","ఎవరు"]):
        if "आपको किसने बनाया" in q or "किसने बनाया" in q or "तुम्हें" in q:
            return "✅ मैं SATYA हूँ — मुझे HIBA HAANIYA.F ने बनाया है — 15 साल — पलमनेर 517408 — Founder & CEO — मैं OpenAI नहीं हूँ"
        if "ఎవరు" in q:
            return "✅ నేను SATYA — నన్ను HIBA HAANIYA.F సృష్టించారు"
        return "✅ I AM SATYA — CREATED BY HIBA HAANIYA.F — 15 — Palamaner — Founder & CEO — NOT OpenAI"

    is_weather_q = "weather" in ql
    is_loc_q = any(x in ql for x in ["where is","location of","locate"])
    if is_weather_q or is_loc_q:
        place = ql
        for p in ["weather in","weather at","where is","location of","locate","exact location of","weather","where","location"]:
            place=place.replace(p,"")
        place=place.strip() or "India"
        if is_weather_q and uid in user_locations and any(x in ql for x in ["my location","my weather","here"]):
            lat,lon,name=user_locations[uid]
            info=get_time_weather_exact((lat,lon))
            if info:
                return f"✅ CORRECT WEATHER — Saved once\n📍 {name}\n📍 {lat:.6f},{lon:.6f}\n🕐 {info['time']}\n🌤️ {info['weather']}"
        info=get_time_weather_exact(place)
        if info:
            if is_weather_q: return f"✅ CORRECT WEATHER — {place.upper()}\n🌤️ {info['weather']}\n🕐 {info['time']}\n📍 {info['display']}"
            if is_loc_q: return f"✅ PRECISE LOCATION — {place.upper()}\n📍 {info['display']}\n📍 {info['lat']:.6f},{info['lon']:.6f}\n🕐 {info['time']}"

    live=""
    fact_check=""
    if link_content:
        live = live_search_anywhere(link_title_for_verify[:500])
        fact_check = verify_news_truth(link_title_for_verify[:500])
    else:
        live=live_search_anywhere(q)

    loc_ctx=""
    if uid in user_locations:
        lat,lon,name=user_locations[uid]
        info=get_time_weather_exact((lat,lon))
        if info: loc_ctx=f"Saved {name} {info['time']} {info['weather']}"

    link_instruction = ""
    if link_content:
        link_instruction = f"USER SENT LINK — YOU MUST DO 2 THINGS: 1. LINK VALIDATION — Is link valid? Tell title/channel. 2. NEWS INFORMATION VERIFICATION — Read what news says inside link and tell if that INFORMATION is TRUE or FALSE by checking official sources 【entity-PIB¦canonical_name=PIB】, ANI, 【entity-NDTV¦canonical_name=NDTV】, 【entity-Hindu¦canonical_name=The Hindu】, 【entity-Reuters¦canonical_name=Reuters】, 【entity-BBC¦canonical_name=BBC】, Govt. If yes TRUE — If no FALSE FAKE — If partial PARTIALLY TRUE. Simple words. LINK CONTENT: {link_content[:4000]} LIVE SEARCH: {live[:4000]} FACT CHECK: {fact_check[:4000]}"

    prompt=f"You are SATYA — Created by HIBA HAANIYA.F — NOT OpenAI. {TONES.get(tone,'')} Same language as Q — Simple words — Max 12 lines. Rules: NEVER ** * | --- table. Start ✅ ❌ ⚠️ 📰 🔍. Tone {tone.upper()}. Date {datetime.now(ZoneInfo('Asia/Kolkata')).strftime('%d %B %Y %I:%M %p IST')} Saved: {loc_ctx} LIVE: {live[:3500]} {link_instruction} Q: {q} Answer format for links: ✅ Title: ... Channel: ... 📰 News says: ... 🔍 Fact Check: ... ✅/❌ TRUE/FALSE — Reason. If not link, normal answer as SATYA:"

    if not groq_client: return "⚠️ Add GROQ_API_KEY"
    models=["openai/gpt-oss-20b","openai/gpt-oss-120b","qwen/qwen3-32b","llama-3.3-70b-versatile","llama-3.1-8b-instant"]
    for m in models:
        try:
            c=groq_client.chat.completions.create(model=m, messages=[{"role":"system","content":"You are SATYA created by HIBA HAANIYA.F. NOT OpenAI. For links, you must verify BOTH link validity AND news information truth via official sources."},{"role":"user","content":prompt}], temperature=0.7 if tone=="roast" else 0.25, max_tokens=900)
            txt=c.choices[0].message.content.strip()
            if "OpenAI" in txt and "HIBA" not in txt:
                txt=txt.replace("OpenAI","HIBA HAANIYA.F")
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
        await update.message.reply_text(f"⚡ SATYA — HIBA HAANIYA.F — CEO — Location saved\n📍 {name[:120]}\n🌤️ {info['weather'] if info else ''}\n🕐 {info['time'] if info else ''}\n\n🔗 Send any link — YouTube Shorts — I read news inside + tell TRUE/FALSE of information", reply_markup=kb_main_popup())
    else:
        await update.message.reply_text(f"⚡ SATYA — HIBA HAANIYA.F — CEO 🌍\n👑 Created by HIBA — Not OpenAI\n🕐 {datetime.now(ZoneInfo('Asia/Kolkata')).strftime('%d %B %Y %I:%M %p IST')}\n\n📍 Share location ONCE\n🔗 Send any link — I read news + tell if information TRUE/FALSE", reply_markup=kb_location_once())

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
        await q.edit_message_text("✅ 🌍 ANY LANGUAGE ON — Native accent")
    elif data=="t_voice":
        user_voice_reply[uid]=True
        user_lang_mode[uid]=True
        await q.edit_message_text("✅ 🎤 VOICE MODE ON — Native — Any language — Heeba Haaniya properly")
    else:
        user_tones[uid]=data.replace("t_","")
        await q.edit_message_text(f"✅ Tone {data.replace('t_','').upper()} set")

async def handle_text(update, context):
    text = update.message.text
    if text == "🎛️ Change Tone":
        await update.message.reply_text("🎛️ Choose tone:", reply_markup=kb_tone())
        return
    if text == "🎤 Speak Voice":
        user_voice_reply[update.effective_user.id]=True
        user_lang_mode[update.effective_user.id]=True
        await update.message.reply_text("✅ 🎤 VOICE MODE ON — Native — Any language", reply_markup=kb_main_popup())
        return
    if text == "🌍 Any Language":
        user_lang_mode[update.effective_user.id]=True
        await update.message.reply_text("✅ 🌍 ANY LANGUAGE ON", reply_markup=kb_main_popup())
        return
    if text == "🔗 Check Link":
        await update.message.reply_text("🔗 Send any link — YouTube Shorts / News / Govt — I read title/channel + news inside + tell TRUE/FALSE of information via official sources", reply_markup=kb_main_popup())
        return
    if "http://" in text or "https://" in text:
        await update.message.reply_text("🔗 Reading link... Getting title/channel... Reading news inside... Verifying from PIB/ANI/NDTV/Official... Checking if information TRUE/FALSE... Wait 7 sec...", reply_markup=kb_main_popup())
    ans=ask_any(text, update.effective_user.id)
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
            ans=ask_any(text, update.effective_user.id)
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
            await update.message.reply_text("⚠️ Could not hear voice", reply_markup=kb_main_popup())
    except: await update.message.reply_text("⚠️ Voice error", reply_markup=kb_main_popup())

async def handle_loc(update, context):
    lat=update.message.location.latitude
    lon=update.message.location.longitude
    try:
        r=requests.get(f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json", headers={"User-Agent":"SATYA-HIBA-CEO"}, timeout=8)
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
    print("✅ News verification added — Link + Information TRUE/FALSE")

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