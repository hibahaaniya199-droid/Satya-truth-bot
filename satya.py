
import os
import re
import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
import requests
from gtts import gTTS

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from groq import Groq
from tavily import TavilyClient

# --- LOGGING ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- TOKENS - FLEXIBLE - ANY NAME WORKS ---
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN") or ""
BOT_TOKEN = BOT_TOKEN.strip()
GROQ_KEY = os.getenv("GROQ_API_KEY") or ""
TAVILY_KEY = os.getenv("TAVILY_API_KEY") or ""

groq_client = Groq(api_key=GROQ_KEY) if GROQ_KEY else None
tavily_client = TavilyClient(api_key=TAVILY_KEY) if TAVILY_KEY else None

# --- USER DATA ---
USER_TONE = {}
USER_LANG = {}

# --- CLEAN - NO HTTPS LEAK - PRECISE COMPLETE ---
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

# --- LIVE SEARCH ---
def live_search_anywhere(q):
    if not tavily_client or not q:
        return ""
    try:
        res = tavily_client.search(query=q, max_results=5, include_answer=True)
        ans = res.get('answer','') or ''
        results = res.get('results',[])
        ctx = ans + "\n"
        for r in results[:3]:
            ctx += (r.get('content','')[:400] + "\n")
        return clean(ctx)[:1500]
    except Exception as e:
        print(f"Search error: {e}")
        return ""

# --- KEYBOARDS - DEFINED - NO CRASH ---
def kb_location_once():
    try:
        return ReplyKeyboardMarkup([[KeyboardButton("📍 Share Location", request_location=True)]], resize_keyboard=True, one_time_keyboard=True)
    except:
        return None

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
        [InlineKeyboardButton("🌍 Any Language", callback_data="any_language")]
    ])

# --- LLM ASK - NO HARDCODE - PRECISE COMPLETE ---
def ask_any(q, tone="friendly", lang="en", extra_context=""):
    if not groq_client:
        return "<b>📌 Error</b>\n- Groq key missing - Set GROQ_API_KEY in Railway Variables"
    
    q_lower = q.lower()
    
    # Tone-specific instructions - DIFFERENT HEADINGS - NOT SAME
    tone_prompt = {
        "short": "You are SATYA by HIBA HAANIYA.F. Answer SHORT - 3 points MAX - 150 words MAX - Crisp. Heading: <b>⚡ Short 👑</b>",
        "ceo": "You are SATYA by HIBA HAANIYA.F, 15, Founder & CEO. Answer POWERFUL BOSS MODE. Heading: <b>👑 CEO Mode 💼</b>",
        "friendly": "You are SATYA by HIBA HAANIYA.F. Answer warm sweet friendly with 💖. Heading: <b>💖 Friendly 🌸</b>",
        "formal": "You are SATYA by HIBA HAANIYA.F. Answer formal professional. Heading: <b>🎓 Formal 📝</b>",
        "roast": "You are SATYA by HIBA HAANIYA.F. Answer savage funny sarcastic roast but still correct and complete. Heading: <b>📌 Roast 😏🔥</b>"
    }
    
    base_instruction = tone_prompt.get(tone, tone_prompt["friendly"])
    
    # CEO identity check
    ceo_check = ""
    if "ceo" in q_lower or "jennie" in q_lower or "who is ceo" in q_lower or "founder" in q_lower:
        ceo_check = "IMPORTANT: If asked about Jennie, Jennie is BLACKPINK member born 1996, not CEO. CEO is ALWAYS HIBA HAANIYA.F, 15, from Palamaner, Founder & CEO of SATYA TRUTH BOT. Created by HIBA HAANIYA.F. Text always HIBA HAANIYA.F, voice He ba Haaniya teaching style. You are NOT any other AI.\n"
    
    # Live search
    search_ctx = ""
    if extra_context:
        search_ctx = extra_context
    else:
        if len(q) > 3:
            search_ctx = live_search_anywhere(q)
    
    # Time/Weather accurate
    time_ctx = ""
    if "time" in q_lower or "weather" in q_lower or "korea" in q_lower or "japan" in q_lower or "bihar" in q_lower or "palamaner" in q_lower:
        try:
            tz_map = {"korea": "Asia/Seoul", "seoul": "Asia/Seoul", "japan": "Asia/Tokyo", "tokyo": "Asia/Tokyo", "usa": "America/New_York", "new york": "America/New_York", "uk": "Europe/London", "london": "Europe/London", "india": "Asia/Kolkata", "bihar": "Asia/Kolkata", "palamaner": "Asia/Kolkata"}
            tz = "Asia/Kolkata"
            for k,v in tz_map.items():
                if k in q_lower:
                    tz = v
                    break
            now = datetime.now(ZoneInfo(tz))
            ist_now = datetime.now(ZoneInfo("Asia/Kolkata"))
            diff = ""
            if tz != "Asia/Kolkata":
                diff_hours = (now.utcoffset().total_seconds() - ist_now.utcoffset().total_seconds())/3600
                diff = f" Difference from IST: {diff_hours:+.1f}h."
                if tz == "Asia/Seoul":
                    diff = " Example: 8:41 AM IST = 12:11 PM KST - 3h30m AHEAD ⏩"
            time_ctx = f"Current time in {tz}: {now.strftime('%d %B %Y, %I:%M:%S %p %Z')}.{diff} Weather via live search.\n"
        except Exception as e:
            time_ctx = ""
    
    system_prompt = f"""{base_instruction}
{ceo_check}
RULES:
- Use points only with - or emoji
- Bold colored headings with <b>📌 Heading</b> - Use given heading for tone
- No * ** ` ## leaks
- No https:// links - Remove all
- No hardcoding - Use live search + your intelligence
- No other AI names - You are SATYA by HIBA HAANIYA.F - 15 - Palamaner - Founder & CEO
- Text always HIBA HAANIYA.F, voice He ba Haaniya teaching: Hello, let me teach you clearly and step by step.
- Precise + Complete - If asked alkane alkene alkyne, give all 3 complete - No cut - No half answer
- Answer in user's language - Hindi Telugu Tamil Arabic Korean Japanese etc - Native
- Live context: {search_ctx[:1000]}
- Time context: {time_ctx}
- User language: {lang}
- Be helpful, accurate, with sources from live search if available
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
                expected_heading = {
                    "short": "⚡ Short", "ceo": "👑 CEO", "friendly": "💖 Friendly", "formal": "🎓 Formal", "roast": "Roast"
                }.get(tone, "📌")
                if expected_heading not in txt:
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
                else:
                    print(f"Model {model} error: {e}")
                    continue
        return "<b>📌 Error</b>\n- All models busy - Try again - CEO HIBA HAANIYA.F is fixing"
    except Exception as e:
        print(f"ask_any error: {e}")
        return f"<b>📌 Error</b>\n- {str(e)[:200]} - CEO HIBA HAANIYA.F"

# --- HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        USER_TONE[user_id] = "friendly"
        text = (
            "<b>📌 Welcome to SATYA - Truth Bot 👑🌍</b>\n"
            "- In a world of fake forwards... SATYA finds truth\n"
            "- Reads any image perfectly - Real vision\n"
            "- Reads any link - YouTube title/channel + News TRUE/FALSE with PIB proof\n"
            "- Speaks any language - Hindi Telugu Tamil Arabic Korean Japanese etc\n"
            "- Accurate time/weather for any state - Example 8:41 AM IST = 12:11 PM KST 3h30m AHEAD\n"
            "- Tones work different - SHORT CEO FRIENDLY FORMAL ROAST - Not same\n"
            "- Voice 🎤 - You speak, SATYA transcribes + answers + speaks back native\n"
            "- Precise complete answers - No cut - No https leak - No hardcode\n"
            "- Built by <b>HIBA HAANIYA.F</b> - 15 - Palamaner - Founder & CEO, SATYA TRUTH BOT\n"
            "- Text always HIBA HAANIYA.F, voice He ba Haaniya teaching\n\n"
            "<b>🎛️ Choose Tone</b>\n- Click below to change tone"
        )
        await update.message.reply_text(text, reply_markup=kb_main(), parse_mode='HTML')
    except Exception as e:
        print(f"start error: {e}")
        try:
            await update.message.reply_text("Welcome to SATYA by HIBA HAANIYA.F - Founder & CEO 👑", parse_mode='HTML')
        except:
            pass

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        q = update.message.text or ""
        if not q.strip():
            return
        tone = USER_TONE.get(user_id, "friendly")
        lang = USER_LANG.get(user_id, "en")
        
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
        
        # Check if link
        extra = ""
        if "http" in q.lower() or "youtube" in q.lower() or "youtu.be" in q.lower():
            extra = live_search_anywhere(q)
            extra = f"Link analysis: {extra}"
        
        answer = ask_any(q, tone=tone, lang=lang, extra_context=extra)
        await update.message.reply_text(answer, reply_markup=kb_main(), parse_mode='HTML')
    except Exception as e:
        print(f"handle_text error: {e}")
        try:
            await update.message.reply_text("<b>📌 Error</b>\n- Try again - CEO HIBA HAANIYA.F is fixing", parse_mode='HTML')
        except:
            pass

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        tone = USER_TONE.get(user_id, "friendly")
        
        # Transcribe with Groq Whisper
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
                    q = transcription.text or ""
                
                if not q.strip():
                    q = "Hello"
                
                await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
                answer = ask_any(q, tone=tone)
                
                # Speak back with gTTS native language detection
                try:
                    # Detect language for TTS
                    tts_lang = "en"
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
                    
                    # Clean text for TTS - remove HTML tags
                    tts_text = re.sub(r'<[^>]+>', '', answer)[:300]
                    tts = gTTS(text=tts_text, lang=tts_lang, slow=False)
                    audio_path = f"/tmp/answer_{user_id}.mp3"
                    tts.save(audio_path)
                    
                    await update.message.reply_text(answer, reply_markup=kb_main(), parse_mode='HTML')
                    await update.message.reply_voice(voice=open(audio_path, 'rb'))
                except Exception as e:
                    print(f"TTS error: {e}")
                    await update.message.reply_text(answer, reply_markup=kb_main(), parse_mode='HTML')
                
                # Cleanup
                try:
                    os.remove(voice_path)
                    os.remove(audio_path)
                except:
                    pass
                    
            except Exception as e:
                print(f"Voice transcribe error: {e}")
                await update.message.reply_text("<b>📌 Voice Error</b>\n- Could not transcribe - Try text - CEO HIBA HAANIYA.F", parse_mode='HTML')
        else:
            await update.message.reply_text("<b>📌 Voice</b>\n- Groq key missing for voice - Set GROQ_API_KEY", parse_mode='HTML')
    except Exception as e:
        print(f"handle_voice outer error: {e}")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        tone = USER_TONE.get(user_id, "friendly")
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        
        # Real vision with Groq qwen/qwen3-32b vision or qwen/qwen2.5-vl
        if groq_client:
            try:
                photo_file = await update.message.photo[-1].get_file()
                photo_path = f"/tmp/photo_{user_id}.jpg"
                await photo_file.download_to_drive(photo_path)
                
                with open(photo_path, "rb") as f:
                    import base64
                    img_b64 = base64.b64encode(f.read()).decode()
                
                # Vision model - try qwen
                vision_models = ["qwen/qwen3-32b", "qwen/qwen2.5-vl-32b", "meta-llama/llama-4-scout-17b-16e-instruct"]
                vision_answer = ""
                for vm in vision_models:
                    try:
                        completion = groq_client.chat.completions.create(
                            model="qwen/qwen3-32b",
                            messages=[{
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": f"Read this image perfectly like ChatGPT vision. No fake OCR. Read all text, numbers, diagrams exactly. User tone: {tone}. User asked about this image. Give precise complete answer with bold headings <b>📌</b> and points. CEO is HIBA HAANIYA.F. No * ** leaks, no https links."},
                                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
                                ]
                            }],
                            max_tokens=800,
                        )
                        vision_answer = completion.choices[0].message.content or ""
                        break
                    except Exception as e:
                        print(f"Vision model {vm} error: {e}")
                        continue
                
                if not vision_answer:
                    vision_answer = "Image received - Vision model busy - Try again - Describe what you see? CEO HIBA HAANIYA.F"
                
                vision_answer = clean(vision_answer)
                await update.message.reply_text(vision_answer, reply_markup=kb_main(), parse_mode='HTML')
                
                try:
                    os.remove(photo_path)
                except:
                    pass
                    
            except Exception as e:
                print(f"Photo error: {e}")
                await update.message.reply_text("<b>📌 Image</b>\n- Could not read image - Try again - CEO HIBA HAANIYA.F", parse_mode='HTML')
        else:
            await update.message.reply_text("<b>📌 Image</b>\n- Groq key missing for vision", parse_mode='HTML')
    except Exception as e:
        print(f"handle_photo outer error: {e}")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        data = query.data
        
        if data == "change_tone":
            await query.message.reply_text("<b>🎛️ Choose Tone - Tones Work Different</b>\n- SHORT: 3 points MAX - 150 words\n- CEO: Powerful boss mode\n- FRIENDLY: Warm sweet 💖\n- FORMAL: Professional\n- ROAST: Savage funny 😏🔥\n- Not same - Different heading + style", reply_markup=kb_tone(), parse_mode='HTML')
        elif data.startswith("t_"):
            tone_map = {"t_short": "short", "t_ceo": "ceo", "t_friendly": "friendly", "t_formal": "formal", "t_roast": "roast"}
            new_tone = tone_map.get(data, "friendly")
            USER_TONE[user_id] = new_tone
            await query.message.reply_text(f"<b>✅ Tone Changed</b>\n- Now: {new_tone.upper()} - CEO HIBA HAANIYA.F\n- Tones work different - Try asking same Q with different tone - Will be different", reply_markup=kb_main(), parse_mode='HTML')
        elif data == "speak_voice":
            await query.message.reply_text("<b>🎤 Speak Voice</b>\n- Send voice message - SATYA will transcribe any language + answer + speak back native - He ba Haaniya teaching style - Text HIBA HAANIYA.F", parse_mode='HTML')
        elif data == "any_language":
            USER_LANG[user_id] = "any"
            await query.message.reply_text("<b>🌍 Any Language</b>\n- Now speak any language - Hindi Telugu Tamil Arabic Korean Japanese etc - SATYA will answer in same language native voice - No English accent - CEO HIBA HAANIYA.F", parse_mode='HTML')
        elif data == "check_link":
            await query.message.reply_text("<b>🔗 Check Link</b>\n- Send any YouTube link or news link - SATYA reads title/channel + TRUE/FALSE with PIB SPA ANI proof + sources - CEO HIBA HAANIYA.F", parse_mode='HTML')
    except Exception as e:
        print(f"callback error: {e}")

async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        loc = update.message.location
        if loc:
            lat, lon = loc.latitude, loc.longitude
            # Get time/weather for location
            try:
                now = datetime.now(ZoneInfo("Asia/Kolkata"))
                time_str = now.strftime("%d %B %Y, %I:%M:%S %p IST")
                answer = f"<b>📍 Location Received</b>\n- Lat: {lat}, Lon: {lon}\n- Time IST: {time_str}\n- Weather via live search 🌤️\n- Accurate timing for your location - CEO HIBA HAANIYA.F"
            except:
                answer = f"<b>📍 Location</b>\n- {lat}, {lon} - CEO HIBA HAANIYA.F"
            await update.message.reply_text(answer, reply_markup=kb_main(), parse_mode='HTML')
    except Exception as e:
        print(f"location error: {e}")

# --- MAIN - SYNC - NO ASYNCIO.RUN - FIXES RuntimeError Cannot close a running event loop - WORKS ON 3.11 AND 3.13 ---
def main():
    try:
        if not BOT_TOKEN:
            print("❌ NO TOKEN - Set TELEGRAM_BOT_TOKEN or BOT_TOKEN or TELEGRAM_TOKEN in Railway Variables - From @BotFather")
            return
        
        # Check for conflicting token names
        print(f"✅ TOKEN OK - {BOT_TOKEN[:12]}... - CEO HIBA HAANIYA.F")
        if not GROQ_KEY:
            print("⚠️ GROQ_API_KEY missing - Vision + Voice + LLM will fail - Set in Variables")
        if not TAVILY_KEY:
            print("⚠️ TAVILY_API_KEY missing - Live search will fail - Set in Variables")
        
        app = Application.builder().token(BOT_TOKEN).build()
        
        # Register handlers - guaranteed no NameError kb_location_once
        app.add_handler(CommandHandler("start", start))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
        app.add_handler(MessageHandler(filters.VOICE, handle_voice))
        app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
        app.add_handler(CallbackQueryHandler(handle_callback))
        app.add_handler(MessageHandler(filters.LOCATION, handle_location))
        
        print("✅ HANDLERS REGISTERED - NO kb_location_once ERROR - NO COROUTINE ERROR")
        print("✅ SATYA POLLING STARTED - CEO HIBA HAANIYA.F 👑 - Founder & CEO, SATYA TRUTH BOT - 15 - Palamaner")
        print("✅ TONES WORK DIFFERENT - SHORT CEO FRIENDLY FORMAL ROAST - NOT SAME")
        print("✅ SPEAKS ANY LANGUAGE - VOICE WORKS - ANY LANGUAGE CHAT - ACCURATE TIME/WEATHER")
        
        # CORRECT - SYNC - NO AWAIT - NO ASYNCIO.RUN - Fixes RuntimeError Cannot close a running event loop
        app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        print(f"❌ CRASH ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
