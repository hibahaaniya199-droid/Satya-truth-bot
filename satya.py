
import os
import re
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
import requests
from gtts import gTTS

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from groq import Groq
from tavily import TavilyClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- TOKENS FLEXIBLE ---
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN") or ""
BOT_TOKEN = BOT_TOKEN.strip()
GROQ_KEY = os.getenv("GROQ_API_KEY") or ""
TAVILY_KEY = os.getenv("TAVILY_API_KEY") or ""

groq_client = Groq(api_key=GROQ_KEY) if GROQ_KEY else None
tavily_client = TavilyClient(api_key=TAVILY_KEY) if TAVILY_KEY else None

USER_TONE = {}
USER_LANG = {}
USER_LOCATION = {}  # For latest local news - detect location

# --- CLEAN - NO HTTPS LEAK ---
def clean(t):
    if not t:
        return ""
    t = re.sub(r'https?://\S+', '', t)
    t = t.replace("**","").replace("__","").replace("`","").replace("##","")
    t = t.replace("*","")
    lines = [x.strip() for x in t.split("\n") if x.strip()]
    lines = lines[:35]
    result = "\n".join(lines)
    return result[:4000].strip()

# --- LIVE SEARCH ALL ROUND - ANY TOPIC ---
def live_search_anywhere(q, location=None):
    if not tavily_client or not q:
        return ""
    try:
        # If location detected, search latest local news too
        search_q = q
        if location:
            # For latest news in local bodies - add location
            if "news" in q.lower() or "latest" in q.lower() or "local" in q.lower():
                search_q = f"{q} {location} latest news"
        
        res = tavily_client.search(query=search_q, max_results=5, include_answer=True, search_depth="advanced")
        ans = res.get('answer','') or ''
        results = res.get('results',[])
        ctx = ans + "\n"
        for r in results[:4]:
            content = r.get('content','')[:500]
            title = r.get('title','')
            ctx += f"{title}: {content}\n"
        return clean(ctx)[:2000]
    except Exception as e:
        print(f"Search error: {e}")
        return ""

# --- KEYBOARDS ---
def kb_main():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎛️ Change Tone", callback_data="change_tone"), InlineKeyboardButton("🎤 Speak Voice", callback_data="speak_voice")],
        [InlineKeyboardButton("🌍 Any Language", callback_data="any_language"), InlineKeyboardButton("🔗 Check Link", callback_data="check_link")]
    ])

def kb_tone():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚡ SHORT", callback_data="t_short"), InlineKeyboardButton("👑 CEO", callback_data="t_ceo")],
        [InlineKeyboardButton("💖 FRIENDLY", callback_data="t_friendly"), InlineKeyboardButton("🎓 FORMAL", callback_data="t_formal")],
        [InlineKeyboardButton("🔥 ROAST", callback_data="t_roast")],
    ])

def kb_location_once():
    try:
        return ReplyKeyboardMarkup([[KeyboardButton("📍 Share Location", request_location=True)]], resize_keyboard=True, one_time_keyboard=True)
    except:
        return None

# --- LLM ASK - ALL ROUND - NO HARDCODE - NAME ONLY WHEN ASKED ---
def ask_any(q, tone="friendly", lang="en", location=None, extra_context=""):
    if not groq_client:
        return "<b>📌 Error</b>\n- Groq key missing - Set GROQ_API_KEY in Railway Variables"
    
    q_lower = q.lower()
    
    # --- ONLY TELL NAME WHEN ASKED WHO CREATED YOU / OWNER / FOUNDER / CEO OF SATYA ---
    # Not on every answer - only when asked
    tell_creator = False
    creator_keywords = ["who created you", "who made you", "who is your owner", "who is your creator", "who built you", "who is your founder", "who is founder", "who is ceo of satya", "who is ceo", "who is your ceo", "who owns you", "kisne banaya", "who developed you", "founder of satya", "creator of satya"]
    for kw in creator_keywords:
        if kw in q_lower:
            tell_creator = True
            break
    # If question is "IS X A CEO" - we need to answer about X + also clarify SATYA CEO if relevant, but not always say HIBA
    # Only say CEO is HIBA when asked about SATYA CEO, or when user thinks someone else is SATYA CEO
    is_satya_ceo_question = ("satya" in q_lower and "ceo" in q_lower) or ("satya" in q_lower and "founder" in q_lower) or q_lower.strip() in ["who is ceo", "who is founder", "who is your ceo"]
    
    # Tone headings - different
    tone_prompt = {
        "short": "You are SATYA. Answer SHORT - 3 points MAX - 150 words MAX. Heading: <b>⚡ Short 👑</b>",
        "ceo": "You are SATYA. Answer powerful boss mode. Heading: <b>👑 CEO Mode 💼</b>",
        "friendly": "You are SATYA. Answer warm sweet friendly. Heading: <b>💖 Friendly 🌸</b>",
        "formal": "You are SATYA. Answer formal professional. Heading: <b>🎓 Formal 📝</b>",
        "roast": "You are SATYA. Answer savage funny sarcastic but correct. Heading: <b>📌 Roast 😏🔥</b>"
    }
    base_instruction = tone_prompt.get(tone, tone_prompt["friendly"])
    
    # Live search for ALL topics - studies, any info, latest news, local bodies
    search_ctx = ""
    if extra_context:
        search_ctx = extra_context
    else:
        if len(q) > 2:
            # Detect if latest news needed
            search_ctx = live_search_anywhere(q, location=location)
    
    # Time/weather accurate - detect any place
    time_ctx = ""
    try:
        # Extract possible location from question for time/weather
        tz_map = {
            "korea": "Asia/Seoul", "seoul": "Asia/Seoul", "japan": "Asia/Tokyo", "tokyo": "Asia/Tokyo",
            "usa": "America/New_York", "new york": "America/New_York", "uk": "Europe/London", "london": "Europe/London",
            "bihar": "Asia/Kolkata", "palamaner": "Asia/Kolkata", "india": "Asia/Kolkata", "hyderabad": "Asia/Kolkata",
            "andhra": "Asia/Kolkata", "telangana": "Asia/Kolkata", "delhi": "Asia/Kolkata"
        }
        tz = "Asia/Kolkata"
        found_place = None
        for k,v in tz_map.items():
            if k in q_lower:
                tz = v
                found_place = k
                break
        if "time" in q_lower or "weather" in q_lower or found_place or location:
            use_tz = tz
            if location:
                # Try to map user location to timezone - simplified
                pass
            now = datetime.now(ZoneInfo(use_tz))
            ist_now = datetime.now(ZoneInfo("Asia/Kolkata"))
            diff_str = ""
            if use_tz != "Asia/Kolkata":
                diff_hours = (now.utcoffset().total_seconds() - ist_now.utcoffset().total_seconds())/3600
                if use_tz == "Asia/Seoul":
                    diff_str = f" Example: 8:41 AM IST = 12:11 PM KST - 3h30m AHEAD ⏩"
                else:
                    diff_str = f" Difference from IST: {diff_hours:+.1f}h"
            time_ctx = f"Current time in {use_tz}: {now.strftime('%d %B %Y, %I:%M:%S %p %Z')}.{diff_str} Weather via live search.\n"
    except:
        time_ctx = ""
    
    # System prompt - NO HARDCODE - ALL ROUND - NAME ONLY WHEN ASKED
    creator_info_internal = "Creator is HIBA HAANIYA.F, 15, Palamaner, Founder & CEO, SATYA TRUTH BOT."  # Internal, only use if tell_creator
    if tell_creator or is_satya_ceo_question:
        name_instruction = f"User asked who created you / owner / CEO of SATYA. You MUST say: You were created by HIBA HAANIYA.F, 15, from Palamaner, Founder & CEO of SATYA TRUTH BOT. Text always HIBA HAANIYA.F. Voice internally is He ba Haaniya teaching style, but DO NOT mention spelling H E H A A N I Y in chat - that is internal TTS logic only, not to be shown to users."
    else:
        name_instruction = "DO NOT mention who created you, your owner, founder, CEO, or HIBA HAANIYA.F unless user specifically asks who created you, owner, founder, CEO of SATYA. For general questions (studies, news, facts, any info), just answer the question helpfully without mentioning creator. Your identity as SATYA is internal, not needed in every answer."
    
    system_prompt = f"""{base_instruction}

ALL ROUND INTELLIGENCE - NO HARDCODE:
- You can answer ANY kind of questions: studies (physics, chemistry, biology, maths, alkane alkene alkyne, history, geography), any information, latest news, local bodies news, time, weather, YouTube links, news verification, any language.
- For latest news in local bodies: Use location if provided ({location}) and live search to find latest local news. Detect location of person from message or location share.
- For studies: Give precise complete answers, points with bold headings, no cut, no half answers. If asked alkane alkene alkyne, give all 3 complete.
- For any info: Use live search + your own intelligence, no hardcoding like if "chocolate" in q. No hardcoded answers for specific singers/dancers. Use real knowledge.
- Do NOT say Kim Taehyung is CEO of Pop-up Studio - That is false. Use real knowledge: Kim Taehyung is BTS V, born 1995, singer, not CEO. For any person, say real identity from knowledge, not fake CEO.
- CEO rule: SATYA TRUTH BOT CEO is ONLY HIBA HAANIYA.F. But only mention this when user asks about CEO of SATYA, founder, creator, owner. For general CEO questions about other companies (e.g., Is X CEO of Y company), answer truthfully about that company, not SATYA. Only for SATYA CEO questions, say HIBA.

NAME RULE:
{name_instruction}
- DO NOT ever show in chat that you spell name as H E H A A N I Y or explain voice spelling. That is internal TTS code logic, handled inside code via gTTS, not visible to users. Never mention "Text always HIBA HAANIYA.F, voice He ba Haaniya" in Telegram answers unless asked about creator. Keep voice logic internal.

RULES:
- Use points only with - or emoji
- Bold colored headings with <b>📌 Heading</b> - Use given heading for tone
- No * ** ` ## leaks
- No https:// links - Remove all
- No other AI names - You are SATYA
- No hardcoding - Use live search + intelligence
- Precise + Complete - No cut
- Answer in user's language if needed
- Live context: {search_ctx[:1800]}
- Time context: {time_ctx}
- User location: {location}
- User language: {lang}
- Be helpful, accurate, with sources if available from live search
"""

    try:
        models = ["openai/gpt-oss-20b", "openai/gpt-oss-120b", "qwen/qwen3-32b", "llama-3.3-70b-versatile"]
        for model in models:
            try:
                completion = groq_client.chat.completions.create(
                    model=model,
                    messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": q}],
                    temperature=0.7 if tone!="roast" else 0.85,
                    max_tokens=800,
                )
                txt = completion.choices[0].message.content or ""
                txt = clean(txt)
                # Ensure tone heading present
                expected = {"short": "⚡ Short", "ceo": "👑 CEO", "friendly": "💖 Friendly", "formal": "🎓 Formal", "roast": "Roast"}.get(tone, "📌")
                if expected not in txt:
                    heading_map = {
                        "short": "<b>⚡ Short 👑</b>\n",
                        "ceo": "<b>👑 CEO Mode 💼</b>\n",
                        "friendly": "<b>💖 Friendly 🌸</b>\n",
                        "formal": "<b>🎓 Formal 📝</b>\n",
                        "roast": "<b>📌 Roast 😏🔥</b>\n"
                    }
                    txt = heading_map.get(tone, "<b>📌 Answer</b>\n") + txt
                return txt
            except Exception as e:
                if "decommissioned" in str(e) or "404" in str(e):
                    continue
                print(f"Model {model} error: {e}")
                continue
        return "<b>📌 Error</b>\n- All models busy - Try again"
    except Exception as e:
        print(f"ask_any error: {e}")
        return f"<b>📌 Error</b>\n- {str(e)[:200]}"

# --- HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        USER_TONE[user_id] = "friendly"
        text = (
            "<b>📌 Welcome to SATYA - Truth Bot 👑🌍</b>\n"
            "- In a world of fake forwards... SATYA finds truth\n"
            "- Reads any image perfectly - Real vision\n"
            "- Reads any link - YouTube title/channel + News TRUE/FALSE with proof\n"
            "- Speaks any language - Hindi Telugu Tamil Arabic Korean Japanese etc\n"
            "- Accurate time/weather for any state\n"
            "- Latest news in local bodies - Detects location\n"
            "- Answers any kind of questions - Studies, any info, all round\n"
            "- Tones work different - SHORT CEO FRIENDLY FORMAL ROAST\n"
            "- Voice 🎤 - You speak, SATYA transcribes + answers + speaks back native\n"
        )
        await update.message.reply_text(text, reply_markup=kb_main(), parse_mode='HTML')
    except Exception as e:
        print(f"start error: {e}")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        q = update.message.text or ""
        if not q.strip():
            return
        tone = USER_TONE.get(user_id, "friendly")
        lang = USER_LANG.get(user_id, "en")
        location = USER_LOCATION.get(user_id, None)
        
        # Detect language from script
        if re.search(r'[\u0C00-\u0C7F]', q):
            lang = "te"
        elif re.search(r'[\u0900-\u097F]', q):
            lang = "hi"
        elif re.search(r'[\u0B80-\u0BFF]', q):
            lang = "ta"
        elif re.search(r'[\u0600-\u06FF]', q):
            lang = "ar"
        elif re.search(r'[\u3040-\u309F\u30A0-\u30FF]', q):
            lang = "ja"
        elif re.search(r'[\uAC00-\uD7AF]', q):
            lang = "ko"
        
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        
        extra = ""
        if "http" in q.lower() or "youtube" in q.lower() or "youtu.be" in q.lower():
            extra = live_search_anywhere(q, location=location)
            extra = f"Link analysis: {extra}"
        
        answer = ask_any(q, tone=tone, lang=lang, location=location, extra_context=extra)
        await update.message.reply_text(answer, reply_markup=kb_main(), parse_mode='HTML')
    except Exception as e:
        print(f"handle_text error: {e}")
        try:
            await update.message.reply_text("<b>📌 Error</b>\n- Try again", parse_mode='HTML')
        except:
            pass

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        tone = USER_TONE.get(user_id, "friendly")
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
                await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
                answer = ask_any(q, tone=tone, location=location)
                # TTS - internal logic for voice, not shown in chat
                try:
                    tts_lang = "en"
                    # Internal detection for native voice - not shown to user
                    if re.search(r'[\u0C00-\u0C7F]', q+answer):
                        tts_lang = "te"
                    elif re.search(r'[\u0900-\u097F]', q+answer):
                        tts_lang = "hi"
                    elif re.search(r'[\u0B80-\u0BFF]', q+answer):
                        tts_lang = "ta"
                    elif re.search(r'[\u0600-\u06FF]', q+answer):
                        tts_lang = "ar"
                    elif re.search(r'[\u3040-\u309F\u30A0-\u30FF]', q+answer):
                        tts_lang = "ja"
                    elif re.search(r'[\uAC00-\uD7AF]', q+answer):
                        tts_lang = "ko"
                    # Internal: For creator name, voice says He ba Haaniya naturally, not spelling - handled by gTTS pronouncing HIBA HAANIYA.F as words
                    tts_text = re.sub(r'<[^>]+>', '', answer)[:300]
                    tts = gTTS(text=tts_text, lang=tts_lang, slow=False)
                    audio_path = f"/tmp/answer_{user_id}.mp3"
                    tts.save(audio_path)
                    await update.message.reply_text(answer, reply_markup=kb_main(), parse_mode='HTML')
                    await update.message.reply_voice(voice=open(audio_path, 'rb'))
                except Exception as e:
                    print(f"TTS error: {e}")
                    await update.message.reply_text(answer, reply_markup=kb_main(), parse_mode='HTML')
                try:
                    os.remove(voice_path)
                    os.remove(audio_path)
                except:
                    pass
            except Exception as e:
                print(f"Voice error: {e}")
                await update.message.reply_text("<b>📌 Voice Error</b>\n- Could not transcribe", parse_mode='HTML')
    except Exception as e:
        print(f"handle_voice outer: {e}")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        tone = USER_TONE.get(user_id, "friendly")
        location = USER_LOCATION.get(user_id, None)
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        if groq_client:
            try:
                photo_file = await update.message.photo[-1].get_file()
                photo_path = f"/tmp/photo_{user_id}.jpg"
                await photo_file.download_to_drive(photo_path)
                import base64
                with open(photo_path, "rb") as f:
                    img_b64 = base64.b64encode(f.read()).decode()
                completion = groq_client.chat.completions.create(
                    model="qwen/qwen3-32b",
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": f"Read this image perfectly like ChatGPT vision. Read all text, numbers, diagrams exactly. No fake OCR. User tone: {tone}. Give precise complete answer with bold headings and points. Answer any kind of question from image - studies, info, etc."},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
                        ]
                    }],
                    max_tokens=800,
                )
                vision_answer = completion.choices[0].message.content or ""
                vision_answer = clean(vision_answer)
                await update.message.reply_text(vision_answer, reply_markup=kb_main(), parse_mode='HTML')
                try:
                    os.remove(photo_path)
                except:
                    pass
            except Exception as e:
                print(f"Photo error: {e}")
                await update.message.reply_text("<b>📌 Image</b>\n- Could not read image - Try again", parse_mode='HTML')
    except Exception as e:
        print(f"handle_photo outer: {e}")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        data = query.data
        if data == "change_tone":
            await query.message.reply_text("<b>🎛️ Choose Tone</b>\n- SHORT: 3 points MAX\n- CEO: Powerful\n- FRIENDLY: Warm\n- FORMAL: Professional\n- ROAST: Savage funny\n- Different heading + style", reply_markup=kb_tone(), parse_mode='HTML')
        elif data.startswith("t_"):
            tone_map = {"t_short": "short", "t_ceo": "ceo", "t_friendly": "friendly", "t_formal": "formal", "t_roast": "roast"}
            new_tone = tone_map.get(data, "friendly")
            USER_TONE[user_id] = new_tone
            await query.message.reply_text(f"<b>✅ Tone Changed</b>\n- Now: {new_tone.upper()}", reply_markup=kb_main(), parse_mode='HTML')
        elif data == "speak_voice":
            await query.message.reply_text("<b>🎤 Speak Voice</b>\n- Send voice message - SATYA will transcribe any language + answer + speak back native", parse_mode='HTML')
        elif data == "any_language":
            USER_LANG[user_id] = "any"
            await query.message.reply_text("<b>🌍 Any Language</b>\n- Now speak any language - Hindi Telugu Tamil Arabic Korean Japanese etc - SATYA will answer in same language", parse_mode='HTML')
        elif data == "check_link":
            await query.message.reply_text("<b>🔗 Check Link</b>\n- Send any YouTube link or news link - SATYA reads title/channel + TRUE/FALSE with proof", parse_mode='HTML')
    except Exception as e:
        print(f"callback error: {e}")

async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        loc = update.message.location
        if loc:
            user_id = update.effective_user.id
            lat, lon = loc.latitude, loc.longitude
            # Save location for latest local news
            USER_LOCATION[user_id] = f"{lat},{lon}"
            # Also try to get place name via reverse geocoding using live search
            try:
                now = datetime.now(ZoneInfo("Asia/Kolkata"))
                time_str = now.strftime("%d %B %Y, %I:%M:%S %p IST")
                # Get latest news for this location
                latest_news = live_search_anywhere(f"latest news local bodies {lat} {lon}", location=f"{lat},{lon}")
                answer = f"<b>📍 Location Received</b>\n- Lat: {lat}, Lon: {lon}\n- Time IST: {time_str}\n- Saved for latest local news detection\n"
                if latest_news:
                    answer += f"- Latest local info: {latest_news[:500]}\n"
                answer += "- Now ask 'latest news' and SATYA will find news for your location"
            except:
                answer = f"<b>📍 Location</b>\n- {lat}, {lon} - Saved for local news"
            await update.message.reply_text(answer, reply_markup=kb_main(), parse_mode='HTML')
    except Exception as e:
        print(f"location error: {e}")

def main():
    try:
        if not BOT_TOKEN:
            print("❌ NO TOKEN - Set TELEGRAM_BOT_TOKEN or BOT_TOKEN or TELEGRAM_TOKEN")
            return
        print(f"✅ TOKEN OK - {BOT_TOKEN[:12]}... - SATYA ALL ROUND")
        app = Application.builder().token(BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
        app.add_handler(MessageHandler(filters.VOICE, handle_voice))
        app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
        app.add_handler(CallbackQueryHandler(handle_callback))
        app.add_handler(MessageHandler(filters.LOCATION, handle_location))
        print("✅ HANDLERS OK - ALL ROUND - NO HARDCODE - NAME ONLY WHEN ASKED - NO SPELLING SHOWN")
        print("✅ SATYA POLLING STARTED - ALL ROUND INTELLIGENCE")
        app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        print(f"❌ CRASH: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
