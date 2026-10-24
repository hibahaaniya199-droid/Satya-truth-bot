import os, requests, re
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
TONES = {
    "short": "Ultra short. 2 lines max. Direct truth.",
    "ceo": "CEO style — sharp, expensive, confident. 2 lines.",
    "friendly": "Bestie style — friendly, warm. 2 lines.",
    "formal": "Formal — for boards. Short respectful.",
    "roast": "Roast scammers — savage short — dar ka mahol.",
    "palamaner": "Palamaner local — knows Basavanna Katta, Faiza OPEN. Short."
}

def ultra_clean(text):
    # Remove ALL markdown leakage
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)  # **word** -> word
    text = re.sub(r'\*([^*]+)\*', r'\1', text)      # *is* -> is
    text = text.replace('**','').replace('*','').replace('__','').replace('##','')
    # Remove table pipes
    lines = []
    for line in text.split('\n'):
        if '|' in line and '---' in line: continue
        if line.strip().startswith('|') and line.strip().endswith('|'):
            # Convert table row to simple text
            line = line.replace('|',' ').strip()
            line = re.sub(r'\s+',' ', line)
        if 'Bottom line' in line or 'Believe LIVE' in line or 'Never invent' in line or 'Be mindful' in line:
            continue
        if 'What the sources say' in line or 'Tradition | Concept' in line:
            continue
        lines.append(line)
    text = '\n'.join(lines)
    text = re.sub(r'\n\s*\n', '\n', text)
    # Keep only first 3 lines max
    parts = text.split('\n')
    text = '\n'.join(parts[:3])
    return text.strip()

def get_keyboard():
    kb = [
        [InlineKeyboardButton("⚡ SHORT", callback_data="tone_short"), InlineKeyboardButton("👑 CEO", callback_data="tone_ceo")],
        [InlineKeyboardButton("💖 FRIENDLY", callback_data="tone_friendly"), InlineKeyboardButton("🎓 FORMAL", callback_data="tone_formal")],
        [InlineKeyboardButton("🔥 ROAST", callback_data="tone_roast"), InlineKeyboardButton("📍 PALAMANER", callback_data="tone_palamenar")]
    ]
    return InlineKeyboardMarkup(kb)

def get_time(q):
    q=q.lower(); abbr,tz="IST","Asia/Kolkata"
    if "seoul" in q or "korea" in q: abbr,tz="KST","Asia/Seoul"
    if "tokyo" in q or "japan" in q: abbr,tz="JST","Asia/Tokyo"
    dt=datetime.now(ZoneInfo(tz))
    return dt.strftime(f"%d %B %Y, %I:%M %p {abbr}")

def ask(q, uid):
    ql = q.lower()
    tone = user_tones.get(uid, "short")
    ti = TONES[tone]

    if any(x in ql for x in ["who created","who made","creator","founder"]):
        return "👑 SATYA by HIBA HAANIYA.F — Founder & CEO — Palamaner"
    if "faiza" in ql:
        return "✅ FAIZA ENTERPRISES — Basavanna Katta St — OPEN — Many customers — Verified by Hiba — Google says Closed but WRONG"
    if "cjp" in ql:
        return "✅ CJP Protest 10 Oct Jantar Mantar — ~150 detained — Claims 2000, water cannons = FALSE — SATYA table 12:37 AM"
    if "god for the universe" in ql or "god of universe" in ql:
        return "✅ No single god for universe — Each faith different — Christianity: God creator — Islam: Allah one — Hindu: Brahma — Respect all"
    if "time" in ql or ql=="ist":
        return f"✅ Time: {get_time(q)} — SATYA"
    
    know=""
    if TAVILY_KEY:
        try:
            r=requests.post("https://api.tavily.com/search", json={"api_key":TAVILY_KEY,"query":q,"max_results":2,"include_answer":True}, timeout=8)
            if r.status_code==200:
                d=r.json(); know=d.get('answer','')[:600]
        except: pass

    prompt=f"You are SATYA by HIBA. Tone: {ti}. RULES: NEVER use ** or * or | or --- or table. NEVER say Bottom line, What sources say, Believe LIVE. Max 2 lines. Short perfect. No markdown. Q: {q} Live: {know}"

    if not groq_client: return "⚠️ Add GROQ_API_KEY"
    for m in ["llama-3.1-8b-instant","llama-3.3-70b-versatile"]:
        try:
            c=groq_client.chat.completions.create(model=m, messages=[{"role":"user","content":prompt}], temperature=0.2, max_tokens=200)
            return ultra_clean(c.choices[0].message.content)
        except: continue
    return "⚠️ Busy — Try again"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"⚡ SATYA LIVE 🛡️\n👑 HIBA HAANIYA.F — CEO\n🕐 {get_time('India')}\n👇 SET TONE — CLICK:", reply_markup=get_keyboard())

async def tone_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎛️ SET TONE:", reply_markup=get_keyboard())

async def tone_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query; await q.answer()
    tone=q.data.replace("tone_","")
    user_tones[q.from_user.id]=tone
    await q.edit_message_text(f"✅ Tone {tone.upper()} set — Ask now — Short perfect — /tone to change", reply_markup=get_keyboard())

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ans=ask(update.message.text, update.effective_user.id)
    await update.message.reply_text(ans, reply_markup=get_keyboard())

def main():
    app=Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tone", tone_cmd))
    app.add_handler(CallbackQueryHandler(tone_cb, pattern="^tone_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    app.run_polling(drop_pending_updates=True)

if __name__=="__main__": main()
