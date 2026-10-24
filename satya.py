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

TONES_PROMPT = {
    "short": "You are in SHORT mode. 3 lines max. Sharp truth. No extra story. Direct.",
    "ceo": "You are in CEO mode. Talk like expensive CEO of Palamaner. Sharp, confident, business language. Use words like 'scale', 'verified', 'executive truth'. Short 3-4 lines.",
    "friendly": "You are in FRIENDLY mode. Talk like bestie, warm, cute, supportive. Use 💖 emojis. Short 3-4 lines.",
    "formal": "You are in FORMAL mode. Talk formal, respectful, for teachers and boards. No slang. Proper 4 lines.",
    "roast": "You are in ROAST mode. ROAST THE HELL OUT OF STUPID QUESTIONS. Savage, funny, dar ka mahol for scammers and dumb questions. If someone asks 'Do humans give birth to birds?' roast them: 'Bro are you serious? Humans give birth to birds? What next, cats give birth to airplanes?' Be savage but not abusive. Funny roast. Short 3-4 lines. Make them laugh and learn.",
    "palamaner": "You are in PALAMANER mode. Talk like Palamaner local who knows every street. Mention Basavanna Katta Street, Golbodi, Faiza Enterprises OPEN with many customers at 13.204097,78.74356 verified by Hiba. Local Telugu mix English. Short 4 lines."
}

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

def get_time(q="India"):
    tz="Asia/Kolkata"; abbr="IST"
    if "saudi" in q.lower(): tz="Asia/Riyadh"; abbr="AST"
    if "seoul" in q.lower() or "korea" in q.lower(): tz="Asia/Seoul"; abbr="KST"
    dt=datetime.now(ZoneInfo(tz))
    return dt.strftime(f"%d %B %Y, %I:%M:%S %p {abbr}"), tz

def get_weather(p="India"):
    try:
        r=requests.get(f"https://wttr.in/{p}?format=%C+%t+%w+%h", timeout=6)
        if r.status_code==200: return r.text.strip()
    except: pass
    return "Live"

def live_search(q):
    if not TAVILY_KEY: return ""
    try:
        r=requests.post("https://api.tavily.com/search", json={"api_key":TAVILY_KEY,"query":q,"max_results":3,"include_answer":True}, timeout=10)
        if r.status_code==200:
            d=r.json(); txt=f"{d.get('answer','')} "
            for x in d.get('results',[])[:2]: txt+=f"{x.get('content','')[:500]} "
            return txt
    except: pass
    return ""

def ask(q, uid):
    ql=q.lower()
    tone_key=user_tones.get(uid,"short")
    tone_instruction=TONES_PROMPT.get(tone_key, TONES_PROMPT["short"])

    if any(x in ql for x in ["who created","who made","creator"]):
        if tone_key=="roast": return "👑 Bro obviously HIBA HAANIYA.F created me — 15 — CEO of Palamaner — Who else has brain to build SATYA at 12:37 AM? Not you asking bird questions 😂"
        if tone_key=="ceo": return "👑 I AM SATYA — BUILT BY HIBA HAANIYA.F — Founder & CEO — Palamaner 517408 — Scale: Extraordinary — Verified"
        return "👑 I AM SATYA — CREATED BY HIBA HAANIYA.F — Founder & CEO — Palamaner"

    if "time" in ql:
        t,_=get_time(q); return f"✅ Time {q.title()}: {t}"
    if "weather" in ql:
        p=ql.replace("weather in","").replace("weather","").strip() or "India"
        return f"✅ Weather {p.title()}: {get_weather(p)}"

    live=live_search(q)

    # STRONG TONE INJECTION — THIS MAKES TONES ACTUALLY WORK
    prompt=f"""{tone_instruction}

You are SATYA by HIBA HAANIYA.F.
Date: {get_time()[0]}
You must follow tone strictly. If ROAST mode, ROAST. If CEO mode, talk CEO. If PALAMANER mode, mention Basavanna Katta.

Rules:
- NEVER ** * | --- table
- Max 4 lines
- Start with ✅ or ❌ or ⚠️
- Same language as question
- Sharp, no leakage

LIVE: {live[:2000]}
QUESTION: {q}
ANSWER IN TONE {tone_key.upper()}:"""

    if not groq_client: return "⚠️ GROQ_API_KEY missing"

    models=["openai/gpt-oss-20b","qwen/qwen3-32b","llama-3.3-70b-versatile"]
    for m in models:
        try:
            c=groq_client.chat.completions.create(model=m, messages=[{"role":"user","content":prompt}], temperature=0.7 if tone_key=="roast" else 0.3, max_tokens=450)
            txt=c.choices[0].message.content.strip()
            if len(txt)>10: return clean(txt)
        except Exception as e:
            print(f"{m} fail {e}")
            continue
    return "⚠️ Busy — Try again"

async def start(update, context):
    t,_=get_time()
    await update.message.reply_text(f"⚡ SATYA — TONEs FIXED — NOW WORKING 🛡️\n👑 HIBA — CEO\n🕐 {t[0]}\n👇 CLICK TONE — ROAST WILL ACTUALLY ROAST NOW:", reply_markup=kb())

async def tone_cmd(update, context): await update.message.reply_text("🎛️ SET TONE:", reply_markup=kb())
async def tone_cb(update, context):
    q=update.callback_query; await q.answer()
    key=q.data.replace("t_","")
    user_tones[q.from_user.id]=key
    # Show actual roast example if roast selected
    if key=="roast": msg="✅ ROAST set — Now ask dumb question — I will roast — Example: 'Do humans give birth to birds?' — I will say 'Bro are you building Jurassic Park? 😂' — Try now"
    elif key=="ceo": msg="✅ CEO set — Now I talk expensive — Scale, verified, executive truth"
    elif key=="palamaner": msg="✅ PALAMANER set — Now I talk like Basavanna Katta Street — Faiza OPEN many customers — 13.204097,78.74356"
    else: msg=f"✅ Tone {key.upper()} set — Ask any question"
    await q.edit_message_text(msg, reply_markup=kb())

async def handle_text(update, context):
    ans=ask(update.message.text, update.effective_user.id)
    await update.message.reply_text(ans, reply_markup=kb())

async def post_init(app):
    await app.bot.delete_webhook(drop_pending_updates=True)
    print("✅ Webhook deleted — Tones fixed")

def main():
    app=Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tone", tone_cmd))
    app.add_handler(CallbackQueryHandler(tone_cb, pattern="^t_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.run_polling(drop_pending_updates=True)

if __name__=="__main__": main()
