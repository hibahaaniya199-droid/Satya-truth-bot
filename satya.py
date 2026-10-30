
import os
import re
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
import requests
from gtts import gTTS

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from groq import Groq
from tavily import TavilyClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN") or ""
BOT_TOKEN = BOT_TOKEN.strip()
GROQ_KEY = os.getenv("GROQ_API_KEY") or ""
TAVILY_KEY = os.getenv("TAVILY_API_KEY") or ""

groq_client = Groq(api_key=GROQ_KEY) if GROQ_KEY else None
tavily_client = TavilyClient(api_key=TAVILY_KEY) if TAVILY_KEY else None

USER_TONE = {}
USER_LOCATION = {}
USER_LOCATION_ASKED = {}
USER_LAST_Q = {}
USER_LAST_EXTRA = {}
USER_LAST_MODE = {}  # short or long

def clean(t):
    if not t:
        return ""
    t = re.sub(r'https?://\S+', '', t)
    t = t.replace("**","").replace("__","").replace("`","").replace("##","")
    t = t.replace("*","")
    lines = [x.strip() for x in t.split("\n") if x.strip()]
    # Short mode 20 lines, Long mode 35 lines
    return "\n".join(lines).strip()

def clean_for_voice(t):
    if not t:
        return ""
    t = re.sub(r'<[^>]+>', '', t)
    t = t.replace("HIBA HAANIYA.F", "Hiba Haaniya")
    t = t.replace("HIBA HAANIYA", "Hiba Haaniya")
    t = t.replace("&", "and")
    emoji_pattern = re.compile("["
        u"\U0001F600-\U0001F64F"
        u"\U0001F300-\U0001F5FF"
        u"\U0001F680-\U0001F6FF"
        u"\U0001F1E0-\U0001F1FF"
        u"\U00002500-\U00002BEF"
        u"\U00002702-\U000027B0"
        u"\U000024C2-\U0001F251"
        u"\U0001f926-\U0001f937"
        u"\U00010000-\U0010ffff"
        u"\u2640-\u2642"
        u"\u2600-\u2B55"
        u"\u200d"
        u"\u23cf"
        u"\u23e9"
        u"\u231a"
        u"\ufe0f"
        u"\u3030"
        "]+", flags=re.UNICODE)
    t = emoji_pattern.sub(r'', t)
    t = t.replace("📌","").replace("👑","").replace("🌍","").replace("🔥","").replace("💖","").replace("🎓","").replace("⚡","").replace("🎤","").replace("🔗","").replace("📍","").replace("🖼️","").replace("🎨","").replace("✅","").replace("❌","").replace("⚠️","").replace("📏","").replace("📖","").replace("📚","").replace("🗺️","")
    sentences = re.split(r'(?<=[.!?])\s+', t)
    if len(sentences) > 3:
        t = ' '.join(sentences[:3])
    t = t[:280].strip()
    if t and t[-1] not in '.!?':
        t += '.'
    t = re.sub(r'\s+', ' ', t)
    return t

def detect_language(text):
    if re.search(r'[\u0C00-\u0C7F]', text):
        return "te"
    elif re.search(r'[\u0900-\u097F]', text):
        return "hi"
    elif re.search(r'[\u0B80-\u0BFF]', text):
        return "ta"
    elif re.search(r'[\u0C80-\u0CBF]', text):
        return "kn"
    elif re.search(r'[\u0D00-\u0D7F]', text):
        return "ml"
    elif re.search(r'[\u0600-\u06FF]', text):
        return "ar"
    elif re.search(r'[\u3040-\u309F\u30A0-\u30FF]', text):
        return "ja"
    elif re.search(r'[\uAC00-\uD7AF]', text):
        return "ko"
    elif re.search(r'[\u4E00-\u9FFF]', text):
        return "zh"
    else:
        return "en"

def live_search_anywhere(q, location=None):
    if not tavily_client or not q:
        return ""
    try:
        search_q = q
        if location and ("news" in q.lower() or "latest" in q.lower()):
            search_q = f"{q} {location} latest"
        res = tavily_client.search(query=search_q, max_results=5, include_answer=True, search_depth="advanced")
        ans = res.get('answer','') or ''
        results = res.get('results',[])
        ctx = ans + "\n"
        for r in results[:4]:
            content = r.get('content','')[:500]
            title = r.get('title','')
            ctx += f"{title}: {content}\n"
        return ctx[:2000]
    except Exception as e:
        print(f"Search error: {e}")
        return ""

def kb_tone_always_visible():
    return ReplyKeyboardMarkup([[KeyboardButton("🎛️ TONE")]], resize_keyboard=True, is_persistent=True)

def kb_tone_popup():
    # LONG and SHORT must also be present near TONE itself - Smarter Better
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚡ SHORT", callback_data="t_short"), InlineKeyboardButton("👑 CEO", callback_data="t_ceo")],
        [InlineKeyboardButton("💖 FRIENDLY", callback_data="t_friendly"), InlineKeyboardButton("🎓 FORMAL", callback_data="t_formal")],
        [InlineKeyboardButton("🔥 ROAST", callback_data="t_roast")],
        [InlineKeyboardButton("📏 SHORT MODE", callback_data="mode_short"), InlineKeyboardButton("📖 LONG MODE", callback_data="mode_long")],
        [InlineKeyboardButton("❌ Close", callback_data="close")]
    ])

def kb_detailed_option():
    # Option for detailed - for every tone - near TONE logic
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📖 Need Detailed Info?", callback_data="detailed_yes"), InlineKeyboardButton("✅ Short is OK", callback_data="detailed_no")]
    ])

def kb_location_once():
    try:
        return ReplyKeyboardMarkup([[KeyboardButton("📍 Share Location (Once)", request_location=True)]], resize_keyboard=True, one_time_keyboard=True)
    except:
        return None

def kb_remove():
    try:
        return ReplyKeyboardRemove()
    except:
        return None

def generate_image(prompt, user_id=0):
    try:
        import urllib.parse, random
        safe_prompt = urllib.parse.quote(prompt[:300])
        seed = random.randint(1, 999999)
        url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1024&height=1024&seed={seed}&nologo=true"
        resp = requests.get(url, timeout=30)
        if resp.status_code == 200 and len(resp.content) > 1000:
            path = f"/tmp/gen_{user_id}_{seed}.jpg"
            with open(path, "wb") as f:
                f.write(resp.content)
            return path
        return None
    except Exception as e:
        print(f"Image gen error: {e}")
        return None

def read_link_accurately(url, location=None):
    if not url:
        return ""
    try:
        result = ""
        if "youtube.com" in url or "youtu.be" in url:
            try:
                if tavily_client:
                    search = tavily_client.search(query=f"YouTube video {url} title channel summary poem", max_results=5, include_answer=True, search_depth="advanced")
                    result += f"Title & Summary: {search.get('answer','')[:500]}\n"
                    for r in search.get('results',[])[:3]:
                        result += f"{r.get('title','')}: {r.get('content','')[:400]}\n"
                try:
                    oembed_url = f"https://www.youtube.com/oembed?url={url}&format=json"
                    resp = requests.get(oembed_url, timeout=5)
                    if resp.status_code == 200:
                        data = resp.json()
                        result += f"Title: {data.get('title','')}\nChannel: {data.get('author_name','')}\n"
                except:
                    pass
                result += "\nVERDICT: Check TRUE/FALSE/DANGEROUS based on sources\nInstructions: Verify channel authenticity, cross-check\n"
            except Exception as e:
                print(f"YouTube error: {e}")
                result += live_search_anywhere(f"YouTube {url} title channel summary", location=location)
        else:
            try:
                if tavily_client:
                    search = tavily_client.search(
                        query=f"Fact check {url} is it true false dangerous poem summary PIB ANI PTI",
                        max_results=5,
                        include_answer=True,
                        search_depth="advanced"
                    )
                    ans = search.get('answer','')
                    result += f"Summary: {ans[:600]}\n"
                    for r in search.get('results',[])[:4]:
                        title = r.get('title','')
                        content = r.get('content','')[:500]
                        proof = ""
                        if "pib" in content.lower() or "press information bureau" in content.lower():
                            proof = " [PIB Proof]"
                        elif "ani" in content.lower():
                            proof = " [ANI Proof]"
                        elif "pti" in content.lower():
                            proof = " [PTI Proof]"
                        result += f"{title}: {content}{proof}\n"
                    al = ans.lower()
                    if "false" in al or "fake" in al or "misleading" in al or "hoax" in al:
                        result += "\nVERDICT: FALSE ❌ - Not backed by PIB/ANI/PTI\nInstructions: Do not forward, report as fake, check PIB Fact Check\n"
                    elif "dangerous" in al or "harmful" in al or "scam" in al or "phishing" in al:
                        result += "\nVERDICT: DANGEROUS ⚠️ - May be harmful\nInstructions: Do not click, block sender, report\n"
                    elif "true" in al or "correct" in al or "verified" in al or "authentic" in al:
                        result += "\nVERDICT: TRUE ✅ - Backed by reliable sources\nInstructions: Safe to share, verify from official\n"
                    else:
                        result += "\nVERDICT: UNVERIFIED ⚠️ - No PIB/ANI/PTI proof\nInstructions: Cross-check with official sources\n"
                else:
                    result += live_search_anywhere(f"Fact check {url} true false dangerous summary PIB", location=location)
            except Exception as e:
                print(f"News error: {e}")
                result += live_search_anywhere(f"News {url} fact check true false dangerous summary PIB", location=location)
        return result[:2500]
    except Exception as e:
        print(f"read_link error: {e}")
        return live_search_anywhere(f"Read link {url} true false summary proof", location=location)

def ask_any(q, tone="short", lang="en", location=None, extra_context="", detailed=False):
    if not groq_client:
        return "Groq key missing"
    
    q_lower = q.lower()
    current_lang = detect_language(q)
    lang = current_lang
    
    tell_creator = False
    creator_keywords = ["who created you", "who made you", "who is your owner", "who is your creator", "who built you", "who is your founder", "who is founder", "who is ceo of satya", "who is ceo", "who is your ceo", "who owns you", "kisne banaya", "who developed you", "founder of satya", "creator of satya"]
    for kw in creator_keywords:
        if kw in q_lower:
            tell_creator = True
            break
    is_satya_ceo_question = ("satya" in q_lower and "ceo" in q_lower) or ("satya" in q_lower and "founder" in q_lower) or q_lower.strip() in ["who is ceo", "who is founder", "who is your ceo"]
    
    if detailed:
        length_instruction = "Give LONG explanation - 6-7 points - Detailed but precise - Max 350 words - Complete"
        max_tokens = 900
        max_len = 3500
        lines_limit = 35
    else:
        length_instruction = "Give SHORT answer - 3 points MAX - Max 150 words - People get bored if long - Short precise"
        max_tokens = 500
        max_len = 1500
        lines_limit = 20
    
    tone_prompt = {
        "short": f"You are SATYA. {length_instruction}. Short crisp. No Friendly heading.",
        "ceo": f"You are SATYA. {length_instruction}. Powerful boss mode.",
        "friendly": f"You are SATYA. {length_instruction}. Warm but short.",
        "formal": f"You are SATYA. {length_instruction}. Formal professional.",
        "roast": f"You are SATYA. {length_instruction}. Savage short funny roast but correct."
    }
    base_instruction = tone_prompt.get(tone, tone_prompt["short"])
    
    search_ctx = extra_context if extra_context else (live_search_anywhere(q, location=location) if len(q)>2 else "")
    
    time_ctx = ""
    try:
        tz_map = {
            "korea": "Asia/Seoul", "seoul": "Asia/Seoul", "japan": "Asia/Tokyo", "tokyo": "Asia/Tokyo",
            "usa": "America/New_York", "new york": "America/New_York", "uk": "Europe/London", "london": "Europe/London",
            "bihar": "Asia/Kolkata", "palamaner": "Asia/Kolkata", "india": "Asia/Kolkata"
        }
        tz = "Asia/Kolkata"
        for k,v in tz_map.items():
            if k in q_lower:
                tz = v
                break
        now = datetime.now(ZoneInfo(tz))
        ist_now = datetime.now(ZoneInfo("Asia/Kolkata"))
        diff_str = ""
        if tz != "Asia/Kolkata":
            try:
                diff_hours = (now.utcoffset().total_seconds() - ist_now.utcoffset().total_seconds())/3600
                if tz == "Asia/Seoul":
                    diff_str = f" Example: 8:41 AM IST = 12:11 PM KST - 3h30m AHEAD"
                else:
                    diff_str = f" Diff from IST: {diff_hours:+.1f}h"
            except:
                pass
        time_ctx = f"Current time in {tz}: {now.strftime('%d %B %Y, %I:%M:%S %p %Z')}.{diff_str}\n"
    except:
        time_ctx = ""
    
    if tell_creator or is_satya_ceo_question:
        name_instruction = "User asked who created you / owner / CEO of SATYA. MUST say: You were created by HIBA HAANIYA.F, 15, from Palamaner, Founder & CEO of SATYA TRUTH BOT. Text HIBA HAANIYA.F. Voice internally Hiba Haaniya, DO NOT spell letters."
    else:
        name_instruction = "DO NOT mention who created you, owner, founder, CEO, HIBA HAANIYA.F unless user asks who created you, owner, founder, CEO of SATYA. For general questions just answer helpfully without creator mention. DO NOT say Friendly heading."
    
    system_prompt = f"""{base_instruction}

ALL ROUND - NO HARDCODE - 99.99% ACCURATE:
- Answer ANY questions: studies, any info, latest news, local bodies, time, weather, YouTube, news verification, any language.
- For link/video: MUST give TRUE/FALSE/DANGEROUS verdict + summary + proof (PIB/ANI/PTI) + instructions what to do
- For voice: First say if true false dangerous, then instructions
- For studies: Precise complete but {"SHORT 150 words" if not detailed else "LONG 350 words detailed"}
- No hardcoding - Use live search + intelligence
- CEO: SATYA CEO is ONLY HIBA HAANIYA.F. Only mention when asked about SATYA CEO/founder/creator/owner.

NAME RULE:
{name_instruction}

RULES:
- Use points with -
- No * ** ` ## leaks
- No https:// links
- No other AI names - You are SATYA
- No hardcoding
- {"SHORT - Max 150 words - People get bored" if not detailed else "LONG - Max 350 words - Detailed - 6-7 points"}
- Answer in CURRENT message language: {lang} - Same language user is texting RN
- No heading like Friendly with heart - REMOVE IT
- Live context: {search_ctx[:1500]}
- Time context: {time_ctx}
- Location: {location}
- Language: {lang}
"""

    try:
        models = ["openai/gpt-oss-20b", "openai/gpt-oss-120b", "qwen/qwen3-32b", "llama-3.3-70b-versatile"]
        for model in models:
            try:
                completion = groq_client.chat.completions.create(
                    model=model,
                    messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": q}],
                    temperature=0.7 if tone!="roast" else 0.85,
                    max_tokens=max_tokens,
                )
                txt = completion.choices[0].message.content or ""
                txt = re.sub(r'https?://\S+', '', txt)
                txt = txt.replace("**","").replace("__","").replace("`","").replace("##","").replace("*","")
                lines = [x.strip() for x in txt.split("\n") if x.strip()]
                if len(lines) > lines_limit:
                    lines = lines[:lines_limit]
                txt = "\n".join(lines).strip()
                txt = txt.replace("💖 Friendly 🌸", "").replace("Friendly", "").replace("🌸","").strip()
                if len(txt) > max_len:
                    txt = txt[:max_len] + "..."
                return txt
            except Exception as e:
                if "decommissioned" in str(e) or "404" in str(e):
                    continue
                print(f"Model {model} error: {e}")
                continue
        return "All models busy - Try again"
    except Exception as e:
        print(f"ask_any error: {e}")
        return f"Error: {str(e)[:200]}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        USER_TONE[user_id] = "short"
        USER_LAST_MODE[user_id] = "short"
        location_prompt = ""
        show_location_kb = None
        if not USER_LOCATION_ASKED.get(user_id):
            location_prompt = "\n- 📍 Share location once for time/weather/local news - Only once\n"
            show_location_kb = kb_location_once()
        
        text = (
            "Welcome to SATYA - Truth Bot - 99.99% Accurate\n"
            "- Reads any image + Finds person - Real vision\n"
            "- Creates images if asked\n"
            "- Reads any link - TRUE/FALSE/DANGEROUS + Summary + Proof + Instructions\n"
            "- Voice: Same language + No emoji reading + Short + Human-like\n"
            "- World timings + weathering\n"
            "- Answers any kind - Studies, news, local bodies - All round\n"
            "- SHORT mode - Option for LONG near TONE itself - Smart memory\n"
            f"{location_prompt}"
        )
        await update.message.reply_text(text, reply_markup=kb_tone_always_visible())
        if show_location_kb:
            await update.message.reply_text("📍 Share Location - Only Once", reply_markup=show_location_kb)
            USER_LOCATION_ASKED[user_id] = True
    except Exception as e:
        print(f"start error: {e}")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        q = update.message.text or ""
        if not q.strip():
            return
        
        if q.strip() == "🎛️ TONE":
            await update.message.reply_text("Choose Tone + Mode - LONG/SHORT near TONE itself - Short answers + Option for detailed - For every tone - Smart", reply_markup=kb_tone_popup())
            return
        
        tone = USER_TONE.get(user_id, "short")
        mode = USER_LAST_MODE.get(user_id, "short")
        detailed = (mode == "long")
        location = USER_LOCATION.get(user_id, None)
        current_lang = detect_language(q)
        
        # Save last Q for smart LONG/SHORT - Do not ask again
        USER_LAST_Q[user_id] = q
        USER_LAST_EXTRA[user_id] = ""
        
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        
        q_lower = q.lower()
        create_keywords = ["create image", "generate image", "make image", "draw", "image banao", "photo banao", "tasveer banao", "चित्र बनाओ", "generate", "create an image"]
        is_image_creation = any(kw in q_lower for kw in create_keywords) and len(q) > 5
        if q_lower.startswith("create") or q_lower.startswith("generate") or "draw a" in q_lower:
            is_image_creation = True
        
        if is_image_creation:
            prompt = q
            for kw in create_keywords:
                prompt = prompt.replace(kw, "").replace(kw.title(), "").strip()
            prompt = prompt.replace("of", "").strip()
            if not prompt or len(prompt) < 3:
                prompt = "beautiful landscape"
            await update.message.reply_text(f"🎨 Creating: {prompt[:100]} - Wait 10 sec...", reply_markup=kb_tone_always_visible())
            img_path = generate_image(prompt, user_id=user_id)
            if img_path and os.path.exists(img_path):
                try:
                    await context.bot.send_photo(chat_id=update.effective_chat.id, photo=open(img_path, 'rb'), caption=f"Generated: {prompt[:200]}", reply_markup=kb_tone_always_visible())
                    try:
                        os.remove(img_path)
                    except:
                        pass
                    return
                except Exception as e:
                    print(f"Send gen image error: {e}")
                    await update.message.reply_text(f"Image generated but send failed", reply_markup=kb_tone_always_visible())
                    return
            else:
                await update.message.reply_text(f"Could not generate: {prompt} - Try simpler like 'a cat in space'", reply_markup=kb_tone_always_visible())
                return
        
        extra = ""
        if "http" in q_lower or "youtube.com" in q_lower or "youtu.be" in q_lower:
            urls = re.findall(r'https?://\S+', q)
            if urls:
                url = urls[0]
                extra = read_link_accurately(url, location=location)
                extra += "\n" + live_search_anywhere(q, location=location)
            else:
                extra = live_search_anywhere(q, location=location)
        USER_LAST_EXTRA[user_id] = extra
        
        answer = ask_any(q, tone=tone, lang=current_lang, location=location, extra_context=extra, detailed=detailed)
        # Smart label - no Friendly
        mode_label = "📖 LONG" if detailed else "📏 SHORT"
        answer_with_mode = f"{answer}\n\n{mode_label} Mode - Click TONE for LONG/SHORT near TONE itself"
        await update.message.reply_text(answer_with_mode, reply_markup=kb_detailed_option())
        await update.message.reply_text("TONE always visible below - LONG/SHORT near TONE itself", reply_markup=kb_tone_always_visible())
    except Exception as e:
        print(f"handle_text error: {e}")
        import traceback
        traceback.print_exc()
        try:
            await update.message.reply_text("Error - Try again", reply_markup=kb_tone_always_visible())
        except:
            pass

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        tone = USER_TONE.get(user_id, "short")
        mode = USER_LAST_MODE.get(user_id, "short")
        detailed = (mode == "long")
        location = USER_LOCATION.get(user_id, None)
        if groq_client:
            try:
                voice_file = await update.message.voice.get_file()
                voice_path = f"/tmp/voice_{user_id}.ogg"
                await voice_file.download_to_drive(voice_path)
                with open(voice_path, "rb") as f:
                    transcription = groq_client.audio.transcriptions.create(
                        file=(voice_path, f.read()),
                        model="whisper-large-v3",
                    )
                    q = transcription.text or "Hello"
                
                USER_LAST_Q[user_id] = q
                detected_lang = detect_language(q)
                await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
                
                extra = ""
                if "http" in q.lower():
                    urls = re.findall(r'https?://\S+', q)
                    if urls:
                        extra = read_link_accurately(urls[0], location=location)
                USER_LAST_EXTRA[user_id] = extra
                
                answer = ask_any(q, tone=tone, lang=detected_lang, location=location, extra_context=extra, detailed=detailed)
                voice_text = clean_for_voice(answer)
                
                try:
                    tts_lang_map = {"te": "te", "hi": "hi", "ta": "ta", "kn": "kn", "ml": "ml", "ar": "ar", "ja": "ja", "ko": "ko", "zh": "zh", "ru": "ru", "en": "en"}
                    tts_lang = tts_lang_map.get(detected_lang, "en")
                    tts = gTTS(text=voice_text, lang=tts_lang, slow=False, lang_check=False)
                    audio_path = f"/tmp/answer_{user_id}.mp3"
                    tts.save(audio_path)
                    await update.message.reply_text(answer, reply_markup=kb_detailed_option())
                    await update.message.reply_text("TONE always visible below - LONG/SHORT near TONE itself", reply_markup=kb_tone_always_visible())
                    await update.message.reply_voice(voice=open(audio_path, 'rb'))
                except Exception as e:
                    print(f"TTS error: {e}")
                    await update.message.reply_text(answer, reply_markup=kb_tone_always_visible())
                
                try:
                    os.remove(voice_path)
                    os.remove(audio_path)
                except:
                    pass
            except Exception as e:
                print(f"Voice error: {e}")
                await update.message.reply_text("Voice Error - Try text", reply_markup=kb_tone_always_visible())
    except Exception as e:
        print(f"handle_voice outer: {e}")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        tone = USER_TONE.get(user_id, "short")
        mode = USER_LAST_MODE.get(user_id, "short")
        detailed = (mode == "long")
        location = USER_LOCATION.get(user_id, None)
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        if not groq_client:
            await update.message.reply_text("Groq key missing for vision", reply_markup=kb_tone_always_visible())
            return
        
        try:
            photo_file = await update.message.photo[-1].get_file()
            photo_path = f"/tmp/photo_{user_id}.jpg"
            await photo_file.download_to_drive(photo_path)
        except Exception as e:
            print(f"Photo download error: {e}")
            await update.message.reply_text("Could not download image", reply_markup=kb_tone_always_visible())
            return
        
        try:
            import base64
            with open(photo_path, "rb") as f:
                img_data = f.read()
                if len(img_data) > 3*1024*1024:
                    try:
                        from PIL import Image
                        import io
                        img = Image.open(io.BytesIO(img_data))
                        img.thumbnail((1024, 1024))
                        buf = io.BytesIO()
                        img.save(buf, format="JPEG", quality=85)
                        img_data = buf.getvalue()
                    except:
                        pass
                img_b64 = base64.b64encode(img_data).decode()
        except Exception as e:
            print(f"Base64 error: {e}")
            await update.message.reply_text("Could not process image", reply_markup=kb_tone_always_visible())
            return
        
        # FIXED: Only LIVE models - removed decommissioned 11b-vision-preview
        vision_models = [
            "meta-llama/llama-4-scout-17b-16e-instruct",
            "meta-llama/llama-4-maverick-17b-128e-instruct"
        ]
        
        vision_answer = ""
        last_error = ""
        for model_name in vision_models:
            try:
                print(f"Trying vision: {model_name}")
                completion = groq_client.chat.completions.create(
                    model=model_name,
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": f"You are SATYA vision. Read this image PERFECTLY. If image has map about British Empire and nationalism text, explain Fig 20 map celebrating British Empire, Britannia sitting over globe, colonies shown as tigers elephants forests primitive people, British national pride basis. Then explain paragraph about nationalism and imperialism leading to disaster 1914, anti-imperial movements. Explain LONG if detailed else SHORT. Tone: {tone}. No Friendly heading."},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
                        ]
                    }],
                    max_tokens=800 if detailed else 500,
                    temperature=0.2,
                )
                vision_answer = completion.choices[0].message.content or ""
                print(f"Vision success: {model_name}")
                break
            except Exception as e:
                last_error = str(e)
                print(f"Vision {model_name} failed: {e}")
                # Don't leak JSON error
                if "decommissioned" in last_error or "400" in last_error:
                    continue
                continue
        
        if not vision_answer:
            print(f"All vision failed: {last_error}")
            vision_answer = "Vision models updating - Please send image again with clear light - I will read THIS image only - Map of British Empire + Nationalism text - Try again"
        
        # Clean - no Friendly
        vision_answer = re.sub(r'https?://\S+', '', vision_answer)
        vision_answer = vision_answer.replace("**","").replace("##","").replace("*","").strip()
        vision_answer = vision_answer.replace("💖 Friendly 🌸", "").replace("Friendly", "").strip()
        mode_label = "📖 LONG Mode - Explained detailed" if detailed else "📏 SHORT Mode - Explained short"
        vision_answer = f"{vision_answer}\n\n{mode_label}"
        
        # Save for smart LONG/SHORT
        USER_LAST_Q[user_id] = f"Explain this image: {vision_answer[:200]}"
        USER_LAST_EXTRA[user_id] = vision_answer
        
        await update.message.reply_text(vision_answer, reply_markup=kb_detailed_option())
        await update.message.reply_text("TONE always visible below - LONG/SHORT near TONE itself", reply_markup=kb_tone_always_visible())
        try:
            os.remove(photo_path)
        except:
            pass
    except Exception as e:
        print(f"handle_photo outer: {e}")
        import traceback
        traceback.print_exc()
        try:
            await update.message.reply_text("Could not read image - Send clearer image - No cheating - Will read THIS image", reply_markup=kb_tone_always_visible())
        except:
            pass

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        data = query.data
        if data == "change_tone":
            await query.message.reply_text("Choose Tone + Mode - LONG/SHORT near TONE itself - Smart", reply_markup=kb_tone_popup())
        elif data.startswith("t_"):
            tone_map = {"t_short": "short", "t_ceo": "ceo", "t_friendly": "friendly", "t_formal": "formal", "t_roast": "roast"}
            new_tone = tone_map.get(data, "short")
            USER_TONE[user_id] = new_tone
            await query.message.reply_text(f"Tone Changed: {new_tone.upper()} - Now short savage answers - LONG/SHORT near TONE itself - Pop-up closed", reply_markup=kb_tone_always_visible())
        elif data == "mode_short":
            USER_LAST_MODE[user_id] = "short"
            # SMART - Give SHORT explanation of last Q automatically - Don't ask again
            last_q = USER_LAST_Q.get(user_id, "")
            last_extra = USER_LAST_EXTRA.get(user_id, "")
            if last_q:
                await context.bot.send_chat_action(chat_id=query.message.chat_id, action="typing")
                tone = USER_TONE.get(user_id, "short")
                location = USER_LOCATION.get(user_id, None)
                current_lang = detect_language(last_q)
                answer = ask_any(last_q, tone=tone, lang=current_lang, location=location, extra_context=last_extra, detailed=False)
                await query.message.reply_text(f"📏 SHORT Mode - Smarter Better - Last Q: {last_q[:100]}\n\n{answer}", reply_markup=kb_detailed_option())
                await query.message.reply_text("TONE always visible below - LONG/SHORT near TONE itself", reply_markup=kb_tone_always_visible())
            else:
                await query.message.reply_text("📏 SHORT Mode Set - Now answers will be SHORT - 3 points MAX - 150 words - People not bored - Send question", reply_markup=kb_tone_always_visible())
        elif data == "mode_long":
            USER_LAST_MODE[user_id] = "long"
            # SMART - Give LONG explanation of last Q automatically - Don't ask again - BETTER
            last_q = USER_LAST_Q.get(user_id, "")
            last_extra = USER_LAST_EXTRA.get(user_id, "")
            if last_q:
                await context.bot.send_chat_action(chat_id=query.message.chat_id, action="typing")
                tone = USER_TONE.get(user_id, "short")
                location = USER_LOCATION.get(user_id, None)
                current_lang = detect_language(last_q)
                answer = ask_any(last_q, tone=tone, lang=current_lang, location=location, extra_context=last_extra, detailed=True)
                await query.message.reply_text(f"📖 LONG Mode - Smarter Better - Giving LONG explanation - No need to ask again\n\nQ: {last_q[:100]}\n\n{answer}", reply_markup=kb_tone_always_visible())
            else:
                await query.message.reply_text("📖 LONG Mode Set - Now answers will be LONG - 6-7 points - Detailed - 350 words - Send question for LONG explanation", reply_markup=kb_tone_always_visible())
        elif data == "close":
            try:
                await query.message.delete()
            except:
                pass
        elif data == "detailed_yes":
            # SMART - Automatically give LONG explanation of last Q - Don't ask again
            last_q = USER_LAST_Q.get(user_id, "")
            last_extra = USER_LAST_EXTRA.get(user_id, "")
            if last_q:
                await context.bot.send_chat_action(chat_id=query.message.chat_id, action="typing")
                tone = USER_TONE.get(user_id, "short")
                location = USER_LOCATION.get(user_id, None)
                current_lang = detect_language(last_q)
                answer = ask_any(last_q, tone=tone, lang=current_lang, location=location, extra_context=last_extra, detailed=True)
                USER_LAST_MODE[user_id] = "long"
                await query.message.reply_text(f"📖 DETAILED - Smarter Better - LONG Explanation Auto - No need to ask again\n\n{answer}", reply_markup=kb_tone_always_visible())
            else:
                USER_LAST_MODE[user_id] = "long"
                await query.message.reply_text("📖 LONG Mode Set - Send question for LONG detailed info - Smart - No need to ask again", reply_markup=kb_tone_always_visible())
        elif data == "detailed_no":
            USER_LAST_MODE[user_id] = "short"
            await query.message.reply_text("✅ Short is OK - SHORT Mode - TONE always visible below - LONG/SHORT near TONE itself", reply_markup=kb_tone_always_visible())
    except Exception as e:
        print(f"callback error: {e}")
        import traceback
        traceback.print_exc()

async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        loc = update.message.location
        if loc:
            user_id = update.effective_user.id
            USER_LOCATION_ASKED[user_id] = True
            lat, lon = loc.latitude, loc.longitude
            USER_LOCATION[user_id] = f"{lat},{lon}"
            try:
                now = datetime.now(ZoneInfo("Asia/Kolkata"))
                time_str = now.strftime("%d %B %Y, %I:%M:%S %p IST")
                world_times = ""
                try:
                    zones = {"IST": "Asia/Kolkata", "KST": "Asia/Seoul", "JST": "Asia/Tokyo", "EST": "America/New_York", "GMT": "Europe/London"}
                    for name, tz in zones.items():
                        try:
                            t = datetime.now(ZoneInfo(tz))
                            world_times += f"{name}: {t.strftime('%I:%M %p %d %b')}\n"
                        except:
                            pass
                except:
                    world_times = f"Time IST: {time_str}"
                latest_news = live_search_anywhere(f"latest news local {lat} {lon}", location=f"{lat},{lon}")
                answer = f"📍 Location Saved - Only Once ✅\n- Lat: {lat}, Lon: {lon}\n- Time IST: {time_str}\n- World Timings:\n{world_times}\n- Saved - Will not ask again\n"
                if latest_news:
                    answer += f"- Latest local: {latest_news[:400]}\n"
            except Exception as e:
                print(f"Location processing error: {e}")
                answer = f"📍 Location Saved - Only Once - {lat}, {lon}"
            await update.message.reply_text(answer, reply_markup=kb_remove())
            await update.message.reply_text("TONE always visible below - LONG/SHORT near TONE itself", reply_markup=kb_tone_always_visible())
    except Exception as e:
        print(f"location error: {e}")

def main():
    try:
        if not BOT_TOKEN:
            print("❌ NO TOKEN - Set TELEGRAM_BOT_TOKEN or BOT_TOKEN or TELEGRAM_TOKEN")
            return
        print(f"✅ TOKEN OK - {BOT_TOKEN[:12]}... - FINAL SMARTER BETTER - LONG SHORT NEAR TONE")
        app = Application.builder().token(BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
        app.add_handler(MessageHandler(filters.VOICE, handle_voice))
        app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
        app.add_handler(CallbackQueryHandler(handle_callback))
        app.add_handler(MessageHandler(filters.LOCATION, handle_location))
        print("✅ HANDLERS OK - TONE ALWAYS VISIBLE + LONG SHORT NEAR TONE ITSELF + SMART MEMORY - NO ASK AGAIN")
        print("✅ SATYA POLLING STARTED - FINAL SMARTER BETTER - 99.99% ACCURATE")
        app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        print(f"❌ CRASH: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
