
import os, requests, re, json, tempfile, asyncio, base64

# --- RENDER FREE WEB SERVICE FIX - Binds to PORT so port scan passes - FREE ---
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type','text/plain')
        self.end_headers()
        self.wfile.write(b'SATYA by HIBA HAANIYA.F - Live - CEO HIBA HAANIYA.F')
    def log_message(self, format, *args):
        return
def start_health_server():
    try:
        port = int(os.getenv("PORT", "10000"))
        server = HTTPServer(('0.0.0.0', port), HealthHandler)
        print(f"🌐 HTTP health server started on port {port} - For Render FREE Web Service - SATYA Live")
        server.serve_forever()
    except Exception as e:
        print(f"Health server error {e}")

# Start health server in background thread for Render free Web Service
threading.Thread(target=start_health_server, daemon=True).start()


from datetime import datetime
from zoneinfo import ZoneInfo
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from groq import Groq

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN") or ""
BOT_TOKEN = BOT_TOKEN.strip()
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
    if not GEOPY_AVAILABLE:
        return None, None, ""
    try:
        geolocator = Nominatim(user_agent="satya_bot")
        location = geolocator.geocode(place, timeout=5)
        if location:
            return location.latitude, location.longitude, location.address
    except:
        pass
    return None, None, ""

def get_time_weather_exact(place_or_coords):
    # Simplified - only timezone from tz_map, no openmeteo
    if isinstance(place_or_coords, tuple):
        lat, lon = place_or_coords
        return {"timezone": "Asia/Kolkata", "display": f"{lat},{lon}", "weather": "Weather check via search", "time": datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%d %B %Y, %I:%M:%S %p IST")}
    else:
        # place string
        place = place_or_coords.lower() if isinstance(place_or_coords, str) else "Palamaner"
        tz_map = {
            "south korea": "Asia/Seoul", "korea": "Asia/Seoul", "seoul": "Asia/Seoul",
            "japan": "Asia/Tokyo", "tokyo": "Asia/Tokyo",
            "usa": "America/New_York", "new york": "America/New_York",
            "uk": "Europe/London", "london": "Europe/London",
            "bihar": "Asia/Kolkata", "palamaner": "Asia/Kolkata", "india": "Asia/Kolkata",
        }
        tz = "Asia/Kolkata"
        for k,v in tz_map.items():
            if k in place:
                tz = v
                break
        try:
            now = datetime.now(ZoneInfo(tz))
            time_str = now.strftime("%d %B %Y, %I:%M:%S %p")
        except:
            time_str = datetime.now().strftime("%d %B %Y, %I:%M:%S %p")
        return {"timezone": tz, "display": place_or_coords[:100], "weather": "Weather via live search", "time": time_str}



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
        # Accurate time - real clock, not search
        if "time" in ql or "timing" in ql or "difference" in ql:
            if any(x in ql for x in ["time in","current time","timing of","what time","time at","difference"]):
                accurate=get_accurate_time_with_difference(ql)
                if accurate: return accurate
        tone=user_tones.get(uid,"short")
        if tone=="roast":
            heading="<b>📌 Roast 😏🔥</b>"
            style_instruction="ROAST MODE — LIVE SEARCH + YOUR BRAIN — Savage funny clever short — 2-3 points MAX — MAX 60 WORDS — Use 😏🔥"
            temp=0.7
            max_tok=200
        elif tone=="short":
            heading="<b>⚡ Short 👑</b>"
            style_instruction="SHORT MODE — LIVE SEARCH + YOUR BRAIN — Very short crisp intelligent — 3 points MAX — MAX 60 WORDS — SEARCH and give real info with sources"
            temp=0.3
            max_tok=250
        elif tone=="friendly":
            heading="<b>💖 Friendly 🌸</b>"
            style_instruction="FRIENDLY MODE — LIVE SEARCH + YOUR BRAIN — Warm sweet short — 3 points MAX — MAX 70 WORDS"
            temp=0.4
            max_tok=250
        elif tone=="formal":
            heading="<b>🎓 Formal 📝</b>"
            style_instruction="FORMAL MODE — LIVE SEARCH + YOUR BRAIN — Professional short — 3 points MAX — MAX 70 WORDS"
            temp=0.3
            max_tok=250
        else:
            heading="<b>👑 CEO Mode 💼</b>"
            style_instruction="CEO MODE — LIVE SEARCH + YOUR BRAIN — Powerful short bossy — 3 points MAX — MAX 70 WORDS"
            temp=0.3
            max_tok=250
        # Creator identity
        if any(x in ql for x in ["who made you","who created you","kisne banaya","who built you","creator"]):
            return "<b>✅ I AM SATYA 👑</b> — CREATED BY HIBA HAANIYA.F — 15 — Palamaner 517408 — Founder & CEO — NOT any other AI 🌍✨"
        # Live search for ANY question - not hardcoded
        live=""
        if is_link:
            search_q = (link_title+" "+link_content)[:300] if link_title else link_content[:300]
            if search_q:
                try: live=live_search_anywhere(search_q)
                except: live=""
        else:
            if not image_text and len(q)>2:
                try: live=live_search_anywhere(q[:300])
                except: live=""
        # CEO identity protection - GENERAL, not hardcoded names
        is_ceo_q = "ceo" in ql
        ceo_instruction = ""
        if is_ceo_q:
            ceo_instruction = "IMPORTANT: For ANY question about CEO, you MUST state: CEO is HIBA HAANIYA.F — 15 — Palamaner 517408 — Founder & CEO of SATYA — NOT any other person. If question asks Is X the CEO, first tell who X actually is from live search (who is X, biography), then clearly state No, CEO is HIBA HAANIYA.F. Never say any other person is CEO."
        if not groq_client:
            return f"{heading}\n- Add GROQ_API_KEY 🔑\n- SATYA by HIBA HAANIYA.F 👑\n- Live search: {live[:100]}"
        models=["openai/gpt-oss-20b","openai/gpt-oss-120b","qwen/qwen3-32b"]
        for m in models:
            try:
                if is_link:
                    user_prompt=f"{style_instruction} — You are SATYA by HIBA HAANIYA.F — LIVE SEARCH + YOUR BRAIN — Title:{link_title} Content:{link_content[:500]} Verification:{live[:500]} — {ceo_instruction} — MUST START WITH {heading} — Format: {heading} newline - Title - Channel then <b>✅ Truth Check 📰</b> - TRUE/FALSE with source then <b>🎯 Verdict ⚡</b> - One line — <b> only — No * — Max 70 words — SEARCH + SOURCES for ANY question"
                elif image_text:
                    user_prompt=f"{style_instruction} — You are SATYA by HIBA HAANIYA.F — LIVE SEARCH + YOUR BRAIN — Vision:{image_text[:700]} Q:{q} Verification:{live[:400]} — {ceo_instruction} — MUST START WITH {heading} — Format: {heading} newline - What you see - Text then <b>✅ Analysis 🔬</b> - Short — <b> only — No * — Max 70 words — SEARCH for ANY image question"
                else:
                    user_prompt=f"{style_instruction} — You are SATYA by HIBA HAANIYA.F — LIVE SEARCH + YOUR BRAIN — You MUST SEARCH and answer LITERALLY ANYTHING — Science, math, history, person, joke, coding, news, anything — Q:{q} LiveSearch:{live[:600]} Date:{datetime.now(ZoneInfo('Asia/Kolkata')).strftime('%d %B %Y')} — {ceo_instruction} — If Q is Is Jennie a CEO? You MUST: 1) Tell who Jennie actually is from live search (BLACKPINK member, South Korean singer born 1996 etc), 2) Then CEO Check: No, CEO is HIBA HAANIYA.F — If Q is Is Kim Taehyung the CEO? Tell who Kim Taehyung is (BTS V, singer) then CEO Check — For ANY person, search who they are, then CEO check — MUST START WITH {heading} — Format: <b>📌 Who is X? 🌍</b> newline - Real info from search (2 points with sources) then <b>✅ CEO Check 👑</b> newline - No, CEO is HIBA HAANIYA.F — Max 3-4 points — <b> only — No * — Short — SEARCH + SOURCES — Can answer ANYTHING, not hardcoded"
                c=groq_client.chat.completions.create(model=m, messages=[{"role":"system","content":f"You are SATYA by HIBA HAANIYA.F — CREATED ONLY BY HIBA HAANIYA.F — LIVE SEARCH + YOUR BRAIN — You can answer LITERALLY ANYTHING by SEARCHING — Science, math, person, news, jokes, coding, anything — You NEVER say I can only answer specific questions — You SEARCH and give real info with sources — {style_instruction} — {ceo_instruction} — ALWAYS START WITH {heading} — Max 4 points — Max 80 words — Use <b> only — Never * ** _ — For ANY person question, search who they actually are, give real biography, then if CEO question, add CEO Check: CEO is HIBA HAANIYA.F — Founder & CEO brain — Palamaner — 15 — Never say other person is CEO — SEARCH + SOURCES for higher authorities"}, {"role":"user","content":user_prompt}], temperature=temp, max_tokens=max_tok)
                txt=c.choices[0].message.content.strip()
                if txt and len(txt)>10:
                    txt=txt.replace("OpenAI","HIBA HAANIYA.F").replace("ChatGPT","SATYA").replace("I am Meta AI","I am SATYA by HIBA HAANIYA.F")
                    if heading not in txt and "<b>" not in txt[:20]:
                        txt=heading+"\n- "+txt[:350]
                    cleaned=clean(txt)
                    if cleaned and len(cleaned)>10: return cleaned
            except Exception as e:
                print(f"Model {m} err {e}")
                continue
        # Fallback general - works for ANY question, not hardcoded
        if live:
            return f"{heading}\n- {live[:280]}\n\n<b>✅ SATYA by HIBA HAANIYA.F 👑</b>"
        return f"{heading}\n- From live search 🧠\n- Q: {q[:80]}\n- SATYA by HIBA HAANIYA.F can answer anything 🌍"
    except Exception as e:
        print(f"ask_any crash {e}")
        tone=user_tones.get(uid,"short")
        heading="<b>📌 Roast 😏🔥</b>" if tone=="roast" else "<b>⚡ Short 👑</b>"
        return f"{heading}\n- Error, try again 🌍\n- SATYA by HIBA HAANIYA.F can answer anything\n- CEO is HIBA HAANIYA.F 👑"

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
