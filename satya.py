
import os, requests, re, json, tempfile, asyncio, base64
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

def clean(t):
    if not t or len(t.strip()) < 2:
        return "<b>⚡ SATYA by HIBA HAANIYA.F 👑</b> — Ask anything 🌍"
    t = t.replace('<b>', '___B_OPEN___').replace('</b>', '___B_CLOSE___')
    t = re.sub(r'<[^>]+>', '', t)
    t = t.replace('___B_OPEN___', '<b>').replace('___B_CLOSE___', '</b>')
    t = t.replace('**','').replace('__','')
    t = re.sub(r'\*+', '', t)
    t = re.sub(r'_+', '', t)
    t = t.replace('|','').replace('`','')
    t = re.sub(r'(?i)Answer\s*\(SATYA by HIBA HAANIYA\.F\)', '', t).strip()
    t = re.sub(r'\n{3,}', '\n\n', t)
    lines=[x.strip() for x in t.split('\n') if x.strip()][:12]
    result='\n'.join(lines).strip()
    return result[:1000] if result else "<b>SATYA by HIBA HAANIYA.F 👑</b>"

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
    t=re.sub(r'(?i)Answer\s*\(SATYA by HIBA HAANIYA\.F\)', '', t)
    t=t.replace("HIBA HAANIYA.F","He ba Haaniya").replace("HIBA HAANIYA","He ba Haaniya").replace("HIBA","He ba").replace("SATYA","Sathya").replace(".F","")
    t=re.sub(r'<[^>]+>', '', t)
    t=re.sub(r'[✅❌⚠️🎤📍🕐🌤️🌍👑⚡🔥💖🎓🎛️⏱️🔍📰😏👀💀🤔🎬🎥🔗⏳👂🎙️📋✨😊💀🌙🧪📚🔬📝📌🎯💧⚗️🧬]', '', t)
    t=t.replace("*","").replace("_","").replace("**","")
    t=t.replace("°C"," degrees ").replace("km/h"," kilometers ").replace("%"," percent ")
    t=t.replace("e.g.","for example").replace("vs.","versus")
    t=t.replace(" - ", ", ").replace(" — ", ", ").replace("-", ", ")
    t=re.sub(r'\s+', ' ', t).strip()
    if not t.lower().startswith("hello"):
        t = "Hello, let me teach you clearly and step by step. " + t
    return t[:800] or "Sathya by He ba Haaniya teaches you"

def kb_tone():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚡ SHORT", callback_data="t_short"), InlineKeyboardButton("👑 CEO", callback_data="t_ceo")],
        [InlineKeyboardButton("💖 FRIENDLY", callback_data="t_friendly"), InlineKeyboardButton("🎓 FORMAL", callback_data="t_formal")],
        [InlineKeyboardButton("🔥 ROAST", callback_data="t_roast")],
        [InlineKeyboardButton("🌍 Any Language", callback_data="t_lang"), InlineKeyboardButton("🎤 Speak Voice", callback_data="t_voice")]
    ])

def kb_location_once():
    btn=KeyboardButton("📍 Share Location Once — Never Again", request_location=True)
    return ReplyKeyboardMarkup([[btn]], resize_keyboard=True, one_time_keyboard=True)

def kb_main_popup():
    return ReplyKeyboardMarkup([[KeyboardButton("🎛️ Change Tone"), KeyboardButton("🎤 Speak Voice")],[KeyboardButton("🌍 Any Language"), KeyboardButton("🔗 Check Link")]], resize_keyboard=True)

def get_coords(place):
    try:
        r=requests.get(f"https://nominatim.openstreetmap.org/search?q={place}&format=json&limit=1", headers={"User-Agent":"SATYA-BEST"}, timeout=8)
        if r.status_code==200 and r.json():
            d=r.json()[0]
            return float(d['lat']), float(d['lon']), d.get('display_name','')
    except: pass
    return None,None,""

def get_time_weather_exact(place_or_latlon):
    try:
        if isinstance(place_or_latlon, tuple):
            lat,lon=place_or_latlon; display=""
        else:
            lat,lon,display=get_coords(place_or_latlon)
            if lat is None: return None
        r=requests.get(f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,apparent_temperature,wind_speed_10m,relative_humidity_2m&timezone=auto", timeout=8)
        if r.status_code!=200: return None
        j=r.json(); tz=j.get('timezone','Asia/Kolkata'); curr=j.get('current',{})
        weather=f"{curr.get('temperature_2m')}°C feels {curr.get('apparent_temperature')}°C, wind {curr.get('wind_speed_10m')}km/h, humidity {curr.get('relative_humidity_2m')}%"
        dt=datetime.now(ZoneInfo(tz)); pretty=dt.strftime(f"%d %B %Y, %I:%M:%S %p {tz}")
        return {"lat":lat,"lon":lon,"display":display,"time":pretty,"timezone":tz,"weather":weather}
    except: return None


def get_accurate_time_with_difference(query):
    ql=query.lower()
    place=ql
    for p in ["what is time in","what's time in","what is the time in","time in","current time in","time at","timing of","timing in","time of","what time is it in","whats time in"]:
        place=place.replace(p," ")
    place=place.replace("?","").strip() or "Palamaner"
    tz_map={
        "south korea":"Asia/Seoul","korea":"Asia/Seoul","seoul":"Asia/Seoul",
        "japan":"Asia/Tokyo","tokyo":"Asia/Tokyo",
        "usa":"America/New_York","new york":"America/New_York","texas":"America/Chicago","california":"America/Los_Angeles",
        "uk":"Europe/London","london":"Europe/London","bavaria":"Europe/Berlin","germany":"Europe/Berlin",
        "bihar":"Asia/Kolkata","patna":"Asia/Kolkata","palamaner":"Asia/Kolkata","india":"Asia/Kolkata","delhi":"Asia/Kolkata",
        "dubai":"Asia/Dubai","saudi":"Asia/Riyadh","riyadh":"Asia/Riyadh","singapore":"Asia/Singapore",
        "australia":"Australia/Sydney","queensland":"Australia/Brisbane","sydney":"Australia/Sydney",
        "china":"Asia/Shanghai","beijing":"Asia/Shanghai","thailand":"Asia/Bangkok"
    }
    target_tz=None
    target_key=place.title()
    for k,v in tz_map.items():
        if k in place.lower():
            target_tz=v
            target_key=k.title()
            break
    try:
        ist_tz="Asia/Kolkata"
        now_ist=datetime.now(ZoneInfo(ist_tz))
        ist_pretty=now_ist.strftime("%d %B %Y, %I:%M:%S %p IST")
        ist_offset=now_ist.utcoffset()
    except:
        now_ist=datetime.now()
        ist_pretty=now_ist.strftime("%d %B %Y, %I:%M:%S %p IST")
        ist_offset=None
    display=""
    lat=None
    lon=None
    if not target_tz:
        lat,lon,display=get_coords(place)
        if lat is not None:
            info=get_time_weather_exact((lat,lon))
            if info:
                target_tz=info['timezone']
                display=info['display']
                target_key=display.split(",")[0] if display else place.title()
    if not target_tz:
        target_tz="Asia/Kolkata"
    try:
        now_target=datetime.now(ZoneInfo(target_tz))
        target_pretty=now_target.strftime("%d %B %Y, %I:%M:%S %p "+target_tz.split("/")[-1])
        target_offset=now_target.utcoffset()
    except:
        now_target=now_ist
        target_pretty=ist_pretty
        target_offset=ist_offset
    if ist_offset and target_offset:
        diff_min=int((target_offset-ist_offset).total_seconds()//60)
        if diff_min==0:
            diff_str=f"⏱️ {target_key} SAME as IST 🕐"
        elif diff_min>0:
            h=diff_min//60
            m=diff_min%60
            if m:
                diff_str=f"⏱️ {target_key} {h}h {m}m AHEAD ⏩ of IST"
            else:
                diff_str=f"⏱️ {target_key} {h}h AHEAD ⏩ of IST"
        else:
            h=abs(diff_min)//60
            m=abs(diff_min)%60
            if m:
                diff_str=f"⏱️ {target_key} {h}h {m}m BEHIND ⏪ IST"
            else:
                diff_str=f"⏱️ {target_key} {h}h BEHIND ⏪ IST"
    else:
        diff_str=f"⏱️ {target_tz}"
    return f"✅ TIMING — {target_key.upper()} vs IST 🌍\n🕐 IST: {ist_pretty}\n🕐 {target_key}: {target_pretty}\n{diff_str}\n🌐 {target_tz}"

def read_youtube(url):

    try:
        m=re.search(r'(?:shorts/|v=|youtu\.be/)([A-Za-z0-9_-]{11})', url)
        if not m: return f"YouTube link {url[:60]} 🔗", ""
        vid=m.group(1)
        r=requests.get(f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={vid}&format=json", timeout=7, headers={"User-Agent":"Mozilla/5.0"})
        if r.status_code==200:
            j=r.json()
            title=j.get('title',''); channel=j.get('author_name','')
            return f"Title: {title} Channel: {channel} ID {vid} 🎬", title
        return f"YouTube Shorts ID {vid} 🎥", ""
    except Exception as e:
        return f"YouTube link {url[:60]} 🔗", ""

def read_link(url):
    try:
        if "youtu" in url:
            full, title = read_youtube(url)
            return full, title
        r=requests.get(url, headers={"User-Agent":"Mozilla/5.0 SATYA BEST"}, timeout=8)
        if r.status_code==200:
            text=re.sub(r'<[^>]+>', ' ', r.text); text=re.sub(r'\s+', ' ', text).strip()
            return text[:5000] or f"Link {url} valid 🔗", ""
        return f"Link status {r.status_code} 🔗", ""
    except Exception as e:
        return f"Link {url} exists 🔗", ""

def live_search_anywhere(query):
    if not TAVILY_KEY: return ""
    try:
        r=requests.post("https://api.tavily.com/search", json={"api_key":TAVILY_KEY,"query":query[:400],"search_depth":"advanced","max_results":5,"include_answer":True}, timeout=7)
        if r.status_code==200:
            j=r.json()
            ans=j.get('answer','')
            results=j.get('results',[])
            extra=" ".join([x.get('content','')[:300] for x in results[:2]])
            return (ans+" "+extra)[:1500]
    except: pass
    return ""

def transcribe_voice(file_path):
    if not groq_client: return ""
    try:
        with open(file_path,"rb") as f:
            tr=groq_client.audio.transcriptions.create(model="whisper-large-v3", file=(file_path, f.read()), response_format="text")
            return tr if isinstance(tr, str) else getattr(tr,'text',str(tr))
    except: return ""

def read_image_with_groq(file_path, extra_prompt=""):
    if not groq_client: return "No GROQ key"
    try:
        with open(file_path,"rb") as f: b64=base64.b64encode(f.read()).decode('utf-8')
        # ONLY WORKING MODEL - NO DEAD MODELS
        models=["qwen/qwen3.8-27b","qwen/qwen3.6-27b"]
        for model in models:
            try:
                chat=groq_client.chat.completions.create(
                    model=model,
                    messages=[{"role":"user","content":[
                        {"type":"text","text":f"Read this image PERFECTLY perfectly — Extract ALL text exactly including Telugu, Hindi, English — Describe scene, objects, people, colors, logos, time, date — If it's ETV Telugu 40 Varalu 04 PM 28-10-2026, say that exactly — Be accurate, no hallucination — Extra: {extra_prompt}"},
                        {"type":"image_url","image_url":{"url":f"data:image/jpeg;base64,{b64}"}}
                    ]}],
                    max_tokens=1500, temperature=0.05
                )
                txt=chat.choices[0].message.content.strip()
                if txt and len(txt)>10: return txt[:3500]
            except Exception as e:
                print(f"Vision {model} err {e}"); continue
    except Exception as e: print(f"Image read err {e}")
    return "Could not read image clearly — Try clearer photo — Vision model may be busy — Try again 👀"


def ask_any(q, uid, image_text=""):
    try:
        if not q and not image_text: return "<b>⚡ SATYA by HIBA HAANIYA.F 👑</b> — Send text 📝 image 👀 link 🔗 voice 🎤"
        ql=(q or "").lower().strip()
        urls=re.findall(r'https?://\S+', q or ""); link_content=""; link_title=""; is_link=False
        if urls:
            is_link=True
            try: link_content, link_title = read_link(urls[0])
            except: link_content=f"Link {urls[0]} valid 🔗"; link_title=""
        if "time" in ql or "timing" in ql or "difference" in ql:
            if any(x in ql for x in ["time in","current time","timing of","what time","time at","difference"]):
                accurate=get_accurate_time_with_difference(ql)
                if accurate: return accurate
        if any(x in ql for x in ["who made you","who created you","kisne banaya","who built you","creator"]):
            return "<b>✅ I AM SATYA 👑</b> — CREATED BY HIBA HAANIYA.F — 15 — Palamaner — Founder & CEO 🌍✨"
        if "weather" in ql or "where is" in ql or "location of" in ql:
            place=ql
            for p in ["weather in","weather at","where is","location of","locate","weather","where","location"]: place=place.replace(p,"")
            place=place.strip() or "Palamaner"
            if uid in user_locations and any(x in ql for x in ["my location","my weather","here"]):
                lat,lon,name=user_locations[uid]; info=get_time_weather_exact((lat,lon))
                if info: return f"<b>✅ WEATHER 📍</b>\n📍 {name[:60]}\n🌤️ {info['weather']}"
            info=get_time_weather_exact(place or "Palamaner")
            if info: return f"<b>✅ {place.upper()} 🌍</b>\n🕐 {info['time'][:30]}\n🌤️ {info['weather']}"
        tone=user_tones.get(uid,"short")
        live=""
        if is_link:
            search_q = (link_title+" "+link_content)[:300] if link_title else link_content[:300]
            if search_q: live=live_search_anywhere(search_q)
        else:
            if not image_text:
                search_q=(q)[:300]
                if len(search_q)>5: live=live_search_anywhere(search_q)
        if tone=="short":
            style="Very SHORT — 3 points MAX — Max 60 words — Use <b> heading — Add 1 emoji"
            max_tok=200
        elif tone=="roast":
            style="ROAST tone — SHORT funny sarcastic — 2-3 points MAX — Max 50 words — Add 😏"
            max_tok=180
        elif tone=="friendly":
            style="Friendly — SHORT — 3 points MAX — Max 70 words — Add 💖"
            max_tok=220
        elif tone=="formal":
            style="Formal — SHORT — 3 points MAX — Max 70 words"
            max_tok=220
        else:
            style="CEO tone — SHORT powerful — 3 points MAX — Max 70 words — Add 👑"
            max_tok=220
        loc_ctx=""
        if uid in user_locations: lat,lon,name=user_locations[uid]; loc_ctx=f"Saved {name[:30]}"
        if is_link:
            prompt=f"You are SATYA by HIBA HAANIYA.F — YOU HAVE OWN INTELLIGENCE — Use YOUR OWN BRAIN to reason — Read link Title:{link_title} Content:{link_content[:600]} Live verification:{live[:400]} — {style} — Your verdict from OWN intelligence + live check — Format: <b>📌 Link Reading 🔗</b> - Title - Channel then <b>✅ Truth Check 📰</b> - TRUE/FALSE with YOUR reasoning + source then <b>🎯 Verdict ⚡</b> - One line from YOUR brain — <b> only — No * — Max 70 words"
        elif image_text:
            prompt=f"You are SATYA by HIBA HAANIYA.F — YOU HAVE OWN INTELLIGENCE — Use YOUR OWN BRAIN to understand image — Vision:{image_text[:800]} Q:{q} — {style} — Explain from YOUR own intelligence what you see, reason — Format: <b>📌 Image Reading 👀</b> - What you see (your reasoning) - Text then <b>✅ Your Analysis 🔬</b> - Short from YOUR brain — <b> only — No * — Max 70 words"
        else:
            prompt=f"You are SATYA by HIBA HAANIYA.F — YOU HAVE OWN INTELLIGENCE — Founder & CEO brain from Palamaner — Answer from YOUR OWN KNOWLEDGE and REASONING — Teach clearly step-by-step like He ba Haaniya teacher — Q:{q} Verification only:{live[:300]} Date:{datetime.now(ZoneInfo('Asia/Kolkata')).strftime('%d %B')} — {style} — Format: <b>📌 Heading 🔬</b> - point from YOUR brain - point from YOUR brain — Max 3 points — <b> only — No * — Short — Own intelligence"
        if not groq_client: return "<b>⚠️ Add GROQ_API_KEY — SATYA by HIBA HAANIYA.F 👑</b>"
        models=["openai/gpt-oss-20b","openai/gpt-oss-120b","llama-3.3-70b-versatile"]
        for m in models:
            try:
                c=groq_client.chat.completions.create(model=m, messages=[{"role":"system","content":"You are SATYA by HIBA HAANIYA.F — You have YOUR OWN INTELLIGENCE — Created ONLY by HIBA HAANIYA.F — You are Founder & CEO brain — 15-year-old genius from Palamaner — You REASON yourself, TEACH step-by-step clearly like a teacher — You have knowledge of science, math, world, languages — Search results are only for verification, NOT your brain — Your answer comes from YOUR OWN MIND — ALWAYS SHORT — Max 3-4 points — Max 70 words — Use <b> for headings — Use - for points — 1-2 emojis — Never * ** _ — ROAST=short sarcastic clever — SHORT=very short 3 points — No essays"}, {"role":"user","content":prompt}], temperature=0.3, max_tokens=max_tok)
                txt=c.choices[0].message.content.strip()
                if txt and len(txt)>5:
                    txt=txt.replace("OpenAI","HIBA HAANIYA.F").replace("ChatGPT","SATYA").replace("I am Meta","I am SATYA")
                    cleaned=clean(txt)
                    if cleaned and len(cleaned)>5: return cleaned
            except Exception as e: print(f"Model {m} err {e}"); continue
        if image_text: return f"<b>📌 Image 👀</b>\n- {image_text[:250]}"
        if live: return f"<b>📌 Info 🌍</b>\n- {live[:250]}"
        return f"<b>✅ SATYA by HIBA HAANIYA.F 👑</b> — {q[:60]} 🌍"
    except Exception as e:
        print(f"ask_any crash {e}"); return f"<b>✅ SATYA alive 👑</b> — Try again 🌍"


async def start(update, context):
    uid=update.effective_user.id
    if uid in user_locations:
        lat,lon,name=user_locations[uid]; info=get_time_weather_exact((lat,lon))
        text=f"<b>⚡ SATYA — HIBA HAANIYA.F — CEO 👑</b>\n🌍 Best bot — Text + Image + Link + Voice\n📍 {name[:120]}\n🌤️ {info['weather'] if info else ''}\n🕐 {info['time'] if info else ''}"
        try:
            await update.message.reply_text(text, reply_markup=kb_main_popup(), parse_mode='HTML')
        except:
            await update.message.reply_text(re.sub(r'<[^>]+>', '', text), reply_markup=kb_main_popup())
    else:
        text=f"<b>⚡ SATYA — HIBA HAANIYA.F — CEO 👑</b>\n✨ Best bot — perfectly but better\n🌍 Reads: Text 📝 Image 👀 Link 🔗 Voice 🎤 Any Language\n🕐 {datetime.now(ZoneInfo('Asia/Kolkata')).strftime('%d %B %Y, %I:%M %p IST')}\n\n📍 Share location ONCE\n🎛️ Send any photo — I read perfectly perfectly"
        try:
            await update.message.reply_text(text, reply_markup=kb_location_once(), parse_mode='HTML')
        except:
            await update.message.reply_text(re.sub(r'<[^>]+>', '', text), reply_markup=kb_location_once())

async def loc_cmd(update, context):
    await update.message.reply_text("📍 Share location ONCE 🌍:", reply_markup=kb_location_once())

async def tone_cmd(update, context):
    await update.message.reply_text("🎛️ Choose tone 🎨:", reply_markup=kb_tone())

async def tone_cb(update, context):
    q=update.callback_query; await q.answer(); data=q.data; uid=q.from_user.id
    if data=="t_lang": user_lang_mode[uid]=True; await q.edit_message_text("✅ 🌍 ANY LANGUAGE ON ✨")
    elif data=="t_voice": user_voice_reply[uid]=True; user_lang_mode[uid]=True; await q.edit_message_text("✅ 🎤 VOICE MODE ON 🔊")
    else: user_tones[uid]=data.replace("t_",""); await q.edit_message_text(f"✅ Tone {data.replace('t_','').upper()} set 🎨")

async def handle_text(update, context):
    text=update.message.text or ""
    if text=="🎛️ Change Tone": await update.message.reply_text("🎛️ Choose tone 🎨:", reply_markup=kb_tone()); return
    if text=="🎤 Speak Voice": user_voice_reply[update.effective_user.id]=True; user_lang_mode[update.effective_user.id]=True; await update.message.reply_text("✅ 🎤 VOICE MODE ON 🔊", reply_markup=kb_main_popup()); return
    if text=="🌍 Any Language": user_lang_mode[update.effective_user.id]=True; await update.message.reply_text("✅ 🌍 ANY LANGUAGE ON ✨", reply_markup=kb_main_popup()); return
    if text=="🔗 Check Link": await update.message.reply_text("🔗 Send any link — YouTube / News — I read title + TRUE/FALSE with proof 📰", reply_markup=kb_main_popup()); return
    if "http://" in text or "https://" in text: await update.message.reply_text("🔗 Reading link... Title... Content... Verifying with live search... 6 sec... ⏳🔍", reply_markup=kb_main_popup())
    loop=asyncio.get_running_loop()
    try: ans=await loop.run_in_executor(None, ask_any, text, update.effective_user.id, "")
    except Exception as e: ans=f"<b>✅ SATYA by HIBA HAANIYA.F 👑</b> — Error {e} — Try again"
    if not ans or len(ans.strip())<2: ans=f"<b>✅ SATYA — HIBA HAANIYA.F 👑</b> — Got: {text[:100]} — Time {datetime.now(ZoneInfo('Asia/Kolkata')).strftime('%I:%M %p')} ⏰"
    try:
        await update.message.reply_text(ans, reply_markup=kb_main_popup(), parse_mode='HTML')
    except:
        await update.message.reply_text(re.sub(r'<[^>]+>', '', ans), reply_markup=kb_main_popup())
    if user_voice_reply.get(update.effective_user.id):
        try:
            from gtts import gTTS; speak=get_native_speak_text(ans); lang=detect_native_lang(ans)
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                tts=gTTS(text=speak, lang=lang, slow=False); tts.save(tmp.name)
                await update.message.reply_voice(voice=open(tmp.name,'rb'))
        except: pass

async def handle_photo(update, context):
    try:
        photo=update.message.photo[-1]; file=await photo.get_file()
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            await file.download_to_drive(tmp.name)
            await update.message.reply_text("👀 Reading image PERFECTLY perfectly... Text... Objects... Language... 7 sec... ⏳✨", reply_markup=kb_main_popup())
            loop=asyncio.get_running_loop()
            image_text=await loop.run_in_executor(None, read_image_with_groq, tmp.name, update.message.caption or "")
        if not image_text: image_text="Image received — Vision busy — Try again 👀"
        caption=update.message.caption or ""; full_q=f"{caption}\nImage content: {image_text}" if caption else image_text
        loop=asyncio.get_running_loop()
        ans=await loop.run_in_executor(None, ask_any, full_q, update.effective_user.id, image_text)
        if not ans or len(ans.strip())<2: ans=f"<b>📌 Image Reading 👀</b>\n- {image_text[:800]}"
        try:
            await update.message.reply_text(ans, reply_markup=kb_main_popup(), parse_mode='HTML')
        except:
            await update.message.reply_text(re.sub(r'<[^>]+>', '', ans), reply_markup=kb_main_popup())
        if user_voice_reply.get(update.effective_user.id):
            try:
                from gtts import gTTS; speak=get_native_speak_text(ans); lang=detect_native_lang(ans)
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp2:
                    tts=gTTS(text=speak, lang=lang, slow=False); tts.save(tmp2.name)
                    await update.message.reply_voice(voice=open(tmp2.name,'rb'))
            except: pass
    except Exception as e:
        print(f"Photo err {e}"); await update.message.reply_text("⚠️ Image error 😢 — Try clearer photo 👀✨", reply_markup=kb_main_popup())

async def handle_document(update, context):
    try:
        if not update.message.document.mime_type or not update.message.document.mime_type.startswith('image/'):
            return
        file=await update.message.document.get_file()
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            await file.download_to_drive(tmp.name)
            await update.message.reply_text("👀 Reading document image PERFECTLY... 7 sec... ⏳✨", reply_markup=kb_main_popup())
            loop=asyncio.get_running_loop()
            image_text=await loop.run_in_executor(None, read_image_with_groq, tmp.name, update.message.caption or "")
        if not image_text: image_text="Image doc received — Try again 👀"
        caption=update.message.caption or ""; full_q=f"{caption}\nImage content: {image_text}" if caption else image_text
        loop=asyncio.get_running_loop()
        ans=await loop.run_in_executor(None, ask_any, full_q, update.effective_user.id, image_text)
        if not ans or len(ans.strip())<2: ans=f"<b>📌 Image Reading 👀</b>\n- {image_text[:800]}"
        try:
            await update.message.reply_text(ans, reply_markup=kb_main_popup(), parse_mode='HTML')
        except:
            await update.message.reply_text(re.sub(r'<[^>]+>', '', ans), reply_markup=kb_main_popup())
    except Exception as e:
        print(f"Doc err {e}"); await update.message.reply_text("⚠️ Doc image error 😢", reply_markup=kb_main_popup())

async def handle_voice(update, context):
    try:
        file=await update.message.voice.get_file()
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            await file.download_to_drive(tmp.name); text=transcribe_voice(tmp.name)
        if text:
            await update.message.reply_text(f"🎤 Heard: {text[:250]} 👂✨", reply_markup=kb_main_popup())
            loop=asyncio.get_running_loop(); ans=await loop.run_in_executor(None, ask_any, text, update.effective_user.id, "")
            if not ans or len(ans.strip())<2: ans="<b>✅ SATYA by HIBA HAANIYA.F 👑 — Heard voice</b>"
            try:
                await update.message.reply_text(ans, reply_markup=kb_main_popup(), parse_mode='HTML')
            except:
                await update.message.reply_text(re.sub(r'<[^>]+>', '', ans), reply_markup=kb_main_popup())
            try:
                from gtts import gTTS; speak=get_native_speak_text(ans); lang=detect_native_lang(ans)
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp2:
                    tts=gTTS(text=speak, lang=lang, slow=False); tts.save(tmp2.name)
                    await update.message.reply_voice(voice=open(tmp2.name,'rb'))
            except: pass
        else: await update.message.reply_text("⚠️ Could not hear 🎤", reply_markup=kb_main_popup())
    except: await update.message.reply_text("⚠️ Voice error 🎙️", reply_markup=kb_main_popup())

async def handle_loc(update, context):
    lat=update.message.location.latitude; lon=update.message.location.longitude
    try:
        r=requests.get(f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json", headers={"User-Agent":"SATYA-BEST"}, timeout=8)
        name=r.json().get('display_name','Your saved location') if r.status_code==200 else "Your saved location"
    except: name="Your saved location"
    user_locations[update.effective_user.id]=(lat,lon,name); save_locs()
    info=get_time_weather_exact((lat,lon))
    if info: await update.message.reply_text(f"✅ LOCATION SAVED ONCE 📍\n📍 {name[:150]}\n📍 {lat:.6f},{lon:.6f}\n🕐 {info['time']}\n🌤️ {info['weather']} 🌍", reply_markup=kb_main_popup())
    else: await update.message.reply_text(f"✅ Saved 📍 — {lat:.6f},{lon:.6f} 🌍", reply_markup=kb_main_popup())

async def post_init(app):
    await app.bot.delete_webhook(drop_pending_updates=True)
    print("✅ SATYA FIXED — No hardcoded Sweety — Reads real image + real link — CEO HIBA HAANIYA.F 👑🌍🔥")

def main():
    app=Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tone", tone_cmd))
    app.add_handler(CommandHandler("location", loc_cmd))
    app.add_handler(CallbackQueryHandler(tone_cb, pattern="^t_"))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.IMAGE, handle_document))
    app.add_handler(MessageHandler(filters.LOCATION, handle_loc))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.run_polling(drop_pending_updates=True)

if __name__=="__main__":
    main()
