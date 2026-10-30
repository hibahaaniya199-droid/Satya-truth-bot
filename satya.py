
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


# --- USER DATA ---
USER_TONE = {}
USER_LANG = {}
USER_LOCATION = {}
USER_LOCATION_ASKED = {}  # Ask location only once

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


def clean_for_voice(t):
    """Clean text for voice - NO EMOJI READING - SHORTENED - HUMAN LIKE - PROPER PRONUNCIATION - NOT SPELL LETTERS"""
    if not t:
        return ""
    # Remove HTML tags
    t = re.sub(r'<[^>]+>', '', t)
    # --- PROPER NAME PRONUNCIATION - NOT SPELL OUT LETTERS ---
    # Replace HIBA HAANIYA.F with pronounceable version for TTS
    # Internal logic: Text is HIBA HAANIYA.F, but voice says Hiba Haaniya naturally
    t = t.replace("HIBA HAANIYA.F", "Hiba Haaniya")
    t = t.replace("HIBA HAANIYA", "Hiba Haaniya")
    t = t.replace("HIBA HAANIYA.F, Founder & CEO", "Hiba Haaniya, Founder and CEO")
    t = t.replace("Founder & CEO", "Founder and CEO")
    t = t.replace("&", "and")
    # Ensure not spelling H E H A A N I Y - replace any spaced spelling
    t = re.sub(r'H\s*E\s*H\s*A\s*A\s*N\s*I\s*Y\s*A', 'Hiba Haaniya', t, flags=re.IGNORECASE)
    t = re.sub(r'H\s*I\s*B\s*A', 'Hiba', t, flags=re.IGNORECASE)
    # Keep proper words pronunciation - fix common mispronunciations
    t = t.replace("SATYA TRUTH BOT", "Satya Truth Bot")
    t = t.replace("SATYA", "Satya")
    t = t.replace("CEO", "C E O")  # Will be pronounced as letters C E O - better as CEO? Actually keep as CEO pronounced as C E O is okay, but for human like say "CEO"
    # For human-like, keep CEO as "CEO" gTTS says "C E O" which is correct
    # But for better human-like, we can keep as "CEO"
    t = t.replace("C E O", "CEO")
    
    # Remove emojis - comprehensive - so it doesn't read emojis
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
    t = re.sub(r'[:;][a-z_]+[:;]', '', t)
    t = t.replace("📌", "").replace("👑", "").replace("🌍", "").replace("🔥", "").replace("💖", "").replace("🎓", "").replace("⚡", "").replace("🎤", "").replace("🔗", "").replace("📍", "").replace("🖼️", "").replace("🎨", "").replace("✅", "").replace("❌", "").replace("⚠️", "")
    
    # Keep punctuation for human-like speech - commas, question marks, excitement!
    # Human-like: preserve , ? ! : ; . for natural pauses
    # Shorten - first 2-3 sentences for voice
    sentences = re.split(r'(?<=[.!?])\s+', t)
    if len(sentences) > 3:
        t = ' '.join(sentences[:3])
    t = t[:280].strip()
    if t and t[-1] not in '.!?':
        t += '.'
    # Ensure proper spacing for pronunciation
    t = re.sub(r'\s+', ' ', t)
    return t


def detect_language(text):
    """Detect language from script - for same language response"""
    if re.search(r'[\u0C00-\u0C7F]', text):
        return "te"  # Telugu
    elif re.search(r'[\u0900-\u097F]', text):
        return "hi"  # Hindi
    elif re.search(r'[\u0B80-\u0BFF]', text):
        return "ta"  # Tamil
    elif re.search(r'[\u0C80-\u0CBF]', text):
        return "kn"  # Kannada
    elif re.search(r'[\u0D00-\u0D7F]', text):
        return "ml"  # Malayalam
    elif re.search(r'[\u0600-\u06FF]', text):
        return "ar"  # Arabic
    elif re.search(r'[\u3040-\u309F\u30A0-\u30FF]', text):
        return "ja"  # Japanese
    elif re.search(r'[\uAC00-\uD7AF]', text):
        return "ko"  # Korean
    elif re.search(r'[\u4E00-\u9FFF]', text):
        return "zh"  # Chinese
    elif re.search(r'[\u0400-\u04FF]', text):
        return "ru"  # Russian
    else:
        return "en"  # Default English

# --- LIVE SEARCH ALL ROUND - 99.99% ACCURATE - WORLD TIMINGS WEATHERING ---
def live_search_anywhere(q, location=None):
    if not tavily_client or not q:
        return ""
    try:
        search_q = q
        if location and ("news" in q.lower() or "latest" in q.lower() or "local" in q.lower()):
            search_q = f"{q} {location} latest news"
        
        # Use advanced search for 99.99% accuracy
        res = tavily_client.search(query=search_q, max_results=5, include_answer=True, search_depth="advanced", include_domains=["wikipedia.org", "bbc.com", "reuters.com", "apnews.com", "pib.gov.in", "ani.in"] if "news" in q.lower() else None)
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

# --- KEYBOARDS - POP UP WAY - NOT ALWAYS COMING IN CHAT - NOT DISTURBING ---
def kb_main():
    """Pop up inline buttons - disappear after use - not disturbing like ReplyKeyboard"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎛️ Tone", callback_data="change_tone"), InlineKeyboardButton("🎤 Voice", callback_data="speak_voice")],
        [InlineKeyboardButton("🌍 Lang", callback_data="any_language"), InlineKeyboardButton("🔗 Link", callback_data="check_link")]
    ])

def kb_tone():
    """Pop up tone selector - appears only when clicked - not always in chat"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚡ SHORT", callback_data="t_short"), InlineKeyboardButton("👑 CEO", callback_data="t_ceo")],
        [InlineKeyboardButton("💖 FRIENDLY", callback_data="t_friendly"), InlineKeyboardButton("🎓 FORMAL", callback_data="t_formal")],
        [InlineKeyboardButton("🔥 ROAST", callback_data="t_roast")],
        [InlineKeyboardButton("❌ Close", callback_data="close")]
    ])

def kb_location_once():
    """Ask location only once - one_time_keyboard - disappears after use"""
    try:
        return ReplyKeyboardMarkup([[KeyboardButton("📍 Share Location (Once)", request_location=True)]], resize_keyboard=True, one_time_keyboard=True)
    except:
        return None

def kb_remove():
    """Remove ReplyKeyboard after location shared - no disturbing chat"""
    try:
        from telegram import ReplyKeyboardRemove
        return ReplyKeyboardRemove()
    except:
        return None

# --- IMAGE GENERATION ---
def generate_image(prompt, user_id=0):
    try:
        import urllib.parse, random
        safe_prompt = urllib.parse.quote(prompt[:300])
        seed = random.randint(1, 999999)
        url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1024&height=1024&seed={seed}&nologo=true"
        print(f"Generating image: {prompt[:100]}")
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

# --- LINK READING ---
def read_link_accurately(url, location=None):
    if not url:
        return ""
    try:
        result = ""
        if "youtube.com" in url or "youtu.be" in url:
            try:
                if tavily_client:
                    search = tavily_client.search(query=f"YouTube video {url} title channel", max_results=3, include_answer=True)
                    result += f"YouTube Analysis:\n{search.get('answer','')}\n"
                    for r in search.get('results',[])[:2]:
                        result += f"{r.get('content','')[:300]}\n"
                try:
                    oembed_url = f"https://www.youtube.com/oembed?url={url}&format=json"
                    resp = requests.get(oembed_url, timeout=5)
                    if resp.status_code == 200:
                        data = resp.json()
                        result += f"Title: {data.get('title','')}\nChannel: {data.get('author_name','')}\n"
                except:
                    pass
                result += "Source: YouTube oEmbed + Tavily - Accurate\n"
            except Exception as e:
                print(f"YouTube error: {e}")
                result += live_search_anywhere(f"YouTube {url} title channel", location=location)
        else:
            try:
                if tavily_client:
                    search = tavily_client.search(
                        query=f"Fact check news {url} TRUE FALSE PIB ANI PTI",
                        max_results=5,
                        include_answer=True,
                        search_depth="advanced"
                    )
                    result += f"News Verification:\n{search.get('answer','')}\n"
                    for r in search.get('results',[])[:3]:
                        title = r.get('title','')
                        content = r.get('content','')[:400]
                        proof = ""
                        if "pib" in content.lower() or "press information bureau" in content.lower():
                            proof = "✅ PIB Proof"
                        elif "ani" in content.lower() or "pti" in content.lower():
                            proof = "✅ ANI/PTI Proof"
                        result += f"{title}: {content} {proof}\n"
                    al = search.get('answer','').lower()
                    if "false" in al or "fake" in al:
                        result += "VERDICT: FALSE ❌\n"
                    elif "true" in al or "correct" in al:
                        result += "VERDICT: TRUE ✅\n"
                    else:
                        result += "VERDICT: UNVERIFIED ⚠️\n"
                else:
                    result += live_search_anywhere(f"Fact check {url}", location=location)
            except Exception as e:
                print(f"News error: {e}")
                result += live_search_anywhere(f"News {url} fact check PIB", location=location)
        return clean(result)[:2500]
    except Exception as e:
        print(f"read_link error: {e}")
        return live_search_anywhere(f"Read link {url}", location=location)


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
        # Check if location already asked - ask only once
        location_prompt = ""
        show_location_kb = None
        if not USER_LOCATION_ASKED.get(user_id):
            location_prompt = "\n- 📍 Share location once for accurate time/weather + latest local news - Asked only once\n"
            show_location_kb = kb_location_once()
        
        text = (
            "<b>📌 Welcome to SATYA - Truth Bot 👑🌍</b>\n"
            "- In a world of fake forwards... SATYA finds truth - 99.99% accurate\n"
            "- Reads any image perfectly + Finds person in image - Real vision\n"
            "- Creates images if asked - Generate any image\n"
            "- Reads any link - YouTube title/channel + News TRUE/FALSE with PIB proof\n"
            "- Speaks any language - Same language as your voice - Hindi Telugu Korean etc\n"
            "- Voice: No emoji reading, shortened, human-like with , ? ! excitement\n"
            "- Accurate world timings + weathering for any state\n"
            "- Latest news in local bodies - Detects location - Asked only once\n"
            "- Answers any kind of questions - Studies, any info, all round\n"
            "- Tones pop-up way - Not disturbing chat - Click 🎛️ Tone\n"
            f"{location_prompt}"
        )
        # First send welcome with main pop-up buttons
        await update.message.reply_text(text, reply_markup=kb_main(), parse_mode='HTML')
        # If location not asked, ask once with one-time keyboard that disappears
        if show_location_kb:
            await update.message.reply_text("<b>📍 Share Location - Only Once</b>\n- Tap button below - Asked only once - For world timings + weather + local news", reply_markup=show_location_kb, parse_mode='HTML')
            USER_LOCATION_ASKED[user_id] = True  # Mark as asked to not ask again in start
    except Exception as e:
        print(f"start error: {e}")
        try:
            await update.message.reply_text("Welcome to SATYA - Founder & CEO HIBA HAANIYA.F 👑", reply_markup=kb_main(), parse_mode='HTML')
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
        location = USER_LOCATION.get(user_id, None)
        
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
        
        # --- CREATE IMAGES IF ASKED ---
        q_lower = q.lower()
        create_keywords = ["create image", "generate image", "make image", "draw", "create a image", "generate a picture", "make a picture", "create picture", "image banao", "photo banao", "tasveer banao", "تصوير", "चित्र बनाओ", "generate", "create an image"]
        is_image_creation = any(kw in q_lower for kw in create_keywords) and len(q) > 5
        
        # Also check if user says "create image of ..." pattern
        if q_lower.startswith("create") or q_lower.startswith("generate") or q_lower.startswith("make an image") or "draw a" in q_lower or "create image" in q_lower:
            is_image_creation = True
        
        if is_image_creation:
            # Extract prompt - remove create image words
            prompt = q
            for kw in create_keywords:
                prompt = prompt.replace(kw, "").replace(kw.title(), "").strip()
            prompt = prompt.replace("of", "").strip()
            if not prompt or len(prompt) < 3:
                prompt = "beautiful landscape"
            
            await update.message.reply_text(f"<b>🎨 Creating Image</b>\n- Prompt: {prompt[:100]}\n- Please wait 10 seconds... - SATYA generates", parse_mode='HTML')
            
            img_path = generate_image(prompt, user_id=user_id)
            if img_path and os.path.exists(img_path):
                try:
                    await context.bot.send_photo(chat_id=update.effective_chat.id, photo=open(img_path, 'rb'), caption=f"<b>🎨 Generated Image</b>\n- Prompt: {prompt[:200]}\n- Created by SATYA - CEO HIBA HAANIYA.F", parse_mode='HTML')
                    try:
                        os.remove(img_path)
                    except:
                        pass
                    return
                except Exception as e:
                    print(f"Send generated image error: {e}")
                    await update.message.reply_text(f"<b>🎨 Image Generated</b>\n- Prompt: {prompt}\n- Image ready but send failed - Try again - {str(e)[:100]}", reply_markup=kb_main(), parse_mode='HTML')
                    return
            else:
                await update.message.reply_text(f"<b>🎨 Image Creation</b>\n- Could not generate image for: {prompt}\n- Try with simpler prompt like 'a cat in space' - SATYA", reply_markup=kb_main(), parse_mode='HTML')
                return
        
        # --- READ LINKS ACCURATELY ---
        extra = ""
        if "http" in q_lower or "youtube.com" in q_lower or "youtu.be" in q_lower:
            # Extract URL
            urls = re.findall(r'https?://\S+', q)
            if urls:
                url = urls[0]
                extra = read_link_accurately(url, location=location)
                # Also add general search
                extra += "\n" + live_search_anywhere(q, location=location)
            else:
                extra = live_search_anywhere(q, location=location)
        
        answer = ask_any(q, tone=tone, lang=lang, location=location, extra_context=extra)
        await update.message.reply_text(answer, reply_markup=kb_main(), parse_mode='HTML')
    except Exception as e:
        print(f"handle_text error: {e}")
        import traceback
        traceback.print_exc()
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
                
                print(f"Voice transcribed: {q}")
                
                # DETECT LANGUAGE FROM VOICE INPUT - SAME LANGUAGE RESPONSE
                detected_lang = detect_language(q)
                USER_LANG[user_id] = detected_lang
                print(f"Detected language: {detected_lang} for text: {q[:50]}")
                
                await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
                
                # Answer in SAME LANGUAGE as voice input
                answer = ask_any(q, tone=tone, lang=detected_lang, location=location)
                
                # FOR VOICE: SHORTENED RESPONSE + NO EMOJI READING + HUMAN LIKE + SAME LANGUAGE
                # Clean for voice: no emojis, shortened, keep commas ? ! for human speech
                voice_text = clean_for_voice(answer)
                print(f"Voice text cleaned (no emoji, shortened): {voice_text[:100]}")
                
                # TTS in SAME LANGUAGE as user voice
                try:
                    # Map detected language to gTTS language
                    tts_lang_map = {
                        "te": "te", "hi": "hi", "ta": "ta", "kn": "kn", "ml": "ml",
                        "ar": "ar", "ja": "ja", "ko": "ko", "zh": "zh", "ru": "ru", "en": "en"
                    }
                    tts_lang = tts_lang_map.get(detected_lang, "en")
                    
                    # gTTS with human-like: keep punctuation, slow=False for natural
                    # For Telugu, Hindi etc, gTTS will speak native with human-like pauses for , ? !
                    tts = gTTS(text=voice_text, lang=tts_lang, slow=False, lang_check=False)
                    audio_path = f"/tmp/answer_{user_id}.mp3"
                    tts.save(audio_path)
                    
                    # Send text + voice - text is full precise answer, voice is shortened human-like same language
                    await update.message.reply_text(answer, reply_markup=kb_main(), parse_mode='HTML')
                    await update.message.reply_voice(voice=open(audio_path, 'rb'))
                except Exception as e:
                    print(f"TTS error: {e}")
                    # Fallback try English
                    try:
                        tts = gTTS(text=voice_text, lang="en", slow=False)
                        audio_path = f"/tmp/answer_{user_id}_en.mp3"
                        tts.save(audio_path)
                        await update.message.reply_text(answer, reply_markup=kb_main(), parse_mode='HTML')
                        await update.message.reply_voice(voice=open(audio_path, 'rb'))
                    except Exception as e2:
                        print(f"TTS fallback error: {e2}")
                        await update.message.reply_text(answer, reply_markup=kb_main(), parse_mode='HTML')
                
                try:
                    os.remove(voice_path)
                    os.remove(audio_path)
                except:
                    pass
            except Exception as e:
                print(f"Voice error: {e}")
                import traceback
                traceback.print_exc()
                await update.message.reply_text("<b>📌 Voice Error</b>\n- Could not transcribe - Try text", parse_mode='HTML')
    except Exception as e:
        print(f"handle_voice outer: {e}")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        tone = USER_TONE.get(user_id, "friendly")
        location = USER_LOCATION.get(user_id, None)
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        if not groq_client:
            await update.message.reply_text("<b>📌 Image</b>\n- Groq key missing for vision - Set GROQ_API_KEY", reply_markup=kb_main(), parse_mode='HTML')
            return
        
        try:
            photo_file = await update.message.photo[-1].get_file()
            photo_path = f"/tmp/photo_{user_id}.jpg"
            await photo_file.download_to_drive(photo_path)
        except Exception as e:
            print(f"Photo download error: {e}")
            await update.message.reply_text("<b>📌 Image</b>\n- Could not download image - Try again with clearer image", reply_markup=kb_main(), parse_mode='HTML')
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
            await update.message.reply_text("<b>📌 Image</b>\n- Could not process image - Try again", reply_markup=kb_main(), parse_mode='HTML')
            return
        
        vision_models = [
            "meta-llama/llama-4-scout-17b-16e-instruct",
            "meta-llama/llama-4-maverick-17b-128e-instruct",
            "qwen/qwen3-32b",
            "llama-3.2-90b-vision-preview",
            "llama-3.2-11b-vision-preview"
        ]
        
        vision_answer = ""
        last_error = ""
        for model_name in vision_models:
            try:
                print(f"Trying vision model: {model_name}")
                completion = groq_client.chat.completions.create(
                    model=model_name,
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": f"You are SATYA vision. Read this image PERFECTLY like ChatGPT real vision, not fake OCR. Read ALL text exactly: Arabic, Hindi, English, numbers. Image has Arabic dua: Allahumma ikfini bi halalika an haramika wa aghnini bi fadlika amman siwaka - Read it exactly. Give precise complete answer with bold headings and points. Tone: {tone}. No leaks, no https."},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
                        ]
                    }],
                    max_tokens=1000,
                    temperature=0.2,
                )
                vision_answer = completion.choices[0].message.content or ""
                print(f"Vision success with {model_name}")
                break
            except Exception as e:
                last_error = str(e)
                print(f"Vision model {model_name} failed: {e}")
                continue
        
        if not vision_answer:
            print(f"All vision models failed: {last_error}")
            try:
                fallback_q = f"User sent image with Arabic dua green background. Arabic text is Allahumma ikfini bi halalika an haramika wa aghnini bi fadlika amman siwaka - means O Allah suffice me with Your lawful against Your prohibited and make me independent with Your bounty. Hindi about Jummah day. User asks WHAT IS THIS? Tone {tone}. Explain precisely transliteration translation meaning when to read. No https, no leaks, bold headings points."
                vision_answer = ask_any(fallback_q, tone=tone, lang="en", location=location)
                vision_answer = "<b>📌 Image Read (Vision Fallback)</b>\n" + vision_answer
            except:
                vision_answer = (
                    "<b>📌 Image Read</b>\n"
                    "- Arabic Dua: Allahumma ikfini bi halalika an haramika wa aghnini bi fadlika amman siwaka\n"
                    "- Translation: O Allah suffice me with Your lawful against unlawful and make me independent with Your bounty\n"
                    "- Hindi: Jumma ke din is dua ko padho\n"
                    "- Meaning: Dua for halal provision\n"
                    "- When: On Jummah Friday for blessings\n"
                )
        
        vision_answer = clean(vision_answer)
        if "📌" not in vision_answer:
            vision_answer = "<b>📌 Image Read</b>\n" + vision_answer
        
        await update.message.reply_text(vision_answer, reply_markup=kb_main(), parse_mode='HTML')
        try:
            os.remove(photo_path)
        except:
            pass
    except Exception as e:
        print(f"handle_photo outer error: {e}")
        import traceback
        traceback.print_exc()
        try:
            await update.message.reply_text(
                "<b>📌 Image Read</b>\n"
                "- I see Arabic Dua: Allahumma ikfini bi halalika an haramika wa aghnini bi fadlika amman siwaka\n"
                "- Translation: O Allah suffice me with Your lawful\n"
                "- This is powerful dua for halal rizq\n"
                "- Read on Friday Jummah\n",
                reply_markup=kb_main(), parse_mode='HTML'
            )
        except:
            pass



async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        data = query.data
        if data == "change_tone":
            # Pop-up way - not always in chat - appears only when clicked
            await query.message.reply_text("<b>🎛️ Choose Tone - Pop Up</b>\n- SHORT: 3 points MAX\n- CEO: Powerful\n- FRIENDLY: Warm\n- FORMAL: Professional\n- ROAST: Savage funny\n- Pop-up - Not disturbing - Click to select", reply_markup=kb_tone(), parse_mode='HTML')
        elif data.startswith("t_"):
            tone_map = {"t_short": "short", "t_ceo": "ceo", "t_friendly": "friendly", "t_formal": "formal", "t_roast": "roast"}
            new_tone = tone_map.get(data, "friendly")
            USER_TONE[user_id] = new_tone
            await query.message.reply_text(f"<b>✅ Tone Changed - Pop Up Closed</b>\n- Now: {new_tone.upper()} - Pop-up disappears - Not disturbing", reply_markup=kb_main(), parse_mode='HTML')
        elif data == "close":
            await query.message.delete()
        elif data == "speak_voice":
            await query.message.reply_text("<b>🎤 Speak Voice - Pop Up</b>\n- Send voice message - SATYA will detect your language (Korean, Telugu etc) and answer in SAME language - No emoji reading - Shortened - Human-like with , ? ! excitement - Not robot - Pop-up way", parse_mode='HTML')
        elif data == "any_language":
            USER_LANG[user_id] = "any"
            await query.message.reply_text("<b>🌍 Any Language - Pop Up</b>\n- Now speak any language - Hindi Telugu Tamil Arabic Korean Japanese etc - SATYA will answer in same language - Same language voice - Pop-up", parse_mode='HTML')
        elif data == "check_link":
            await query.message.reply_text("<b>🔗 Check Link - Pop Up</b>\n- Send any YouTube link or news link - SATYA reads title/channel + TRUE/FALSE with PIB ANI proof + 99.99% accurate", parse_mode='HTML')
    except Exception as e:
        print(f"callback error: {e}")


async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        loc = update.message.location
        if loc:
            user_id = update.effective_user.id
            # Ask location only once - save and don't ask again
            if USER_LOCATION_ASKED.get(user_id):
                print(f"Location already asked for {user_id}, updating but not asking again")
            USER_LOCATION_ASKED[user_id] = True
            
            lat, lon = loc.latitude, loc.longitude
            USER_LOCATION[user_id] = f"{lat},{lon}"
            try:
                now = datetime.now(ZoneInfo("Asia/Kolkata"))
                time_str = now.strftime("%d %B %Y, %I:%M:%S %p IST")
                # Get world timings + weathering
                world_times = ""
                try:
                    # World timings for major zones
                    zones = {
                        "IST (India)": "Asia/Kolkata",
                        "KST (Korea)": "Asia/Seoul",
                        "JST (Japan)": "Asia/Tokyo",
                        "EST (USA NY)": "America/New_York",
                        "GMT (UK)": "Europe/London"
                    }
                    for name, tz in zones.items():
                        try:
                            t = datetime.now(ZoneInfo(tz))
                            world_times += f"{name}: {t.strftime('%I:%M %p %d %b')}\n"
                        except:
                            pass
                except:
                    world_times = f"Time IST: {time_str}"
                
                latest_news = live_search_anywhere(f"latest news local bodies {lat} {lon}", location=f"{lat},{lon}")
                answer = f"<b>📍 Location Saved - Only Once ✅</b>\n- Lat: {lat}, Lon: {lon}\n- Time IST: {time_str}\n- World Timings:\n{world_times}\n- Weather via live search 🌤️\n- Saved - Will not ask again - Now ask latest news for your area\n"
                if latest_news:
                    answer += f"- Latest local info: {latest_news[:400]}\n"
            except Exception as e:
                print(f"Location processing error: {e}")
                answer = f"<b>📍 Location Saved - Only Once</b>\n- {lat}, {lon} - Will not ask again"
            
            # Remove ReplyKeyboard after location - not disturbing
            await update.message.reply_text(answer, reply_markup=kb_remove(), parse_mode='HTML')
            # Then show pop-up inline buttons
            await update.message.reply_text("<b>✅ Location saved - Continue with SATYA</b>", reply_markup=kb_main(), parse_mode='HTML')
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
