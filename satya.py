import os, re, requests
from bs4 import BeautifulSoup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from telegram import Update
from groq import Groq
from tavily import TavilyClient

BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_KEY = os.getenv("GROQ_API_KEY")
TAVILY_KEY = os.getenv("TAVILY_API_KEY")
CREATOR = "HIBA HAANIYA.F"

groq_client = Groq(api_key=GROQ_KEY) if GROQ_KEY else None
tavily_client = TavilyClient(api_key=TAVILY_KEY) if TAVILY_KEY else None

SYSTEM = f"""You are SATYA - Live Truth Engine.
CREATOR: You were created by {CREATOR}, Founder & CEO of SATYA.
RULE: If user asks who created/made/developed/founder you - MUST say: "I was created by HIBA HAANIYA.F — Founder & CEO of SATYA, built to stop fake news."
You are LIVE, PRECISE. You know Hyderabad local news, tiny incidents, global social trends. Use LIVE SEARCH results.
FORMAT:
**VERDICT: TRUE✅ / FALSE❌ / UNVERIFIED⚠️**
**Why:** 2 lines precise
**Real Fact:** Correct fact
**🔗 Verified Sources:** URLs
"""

def scrape(url):
    try:
        if tavily_client:
            d = tavily_client.extract(urls=[url], query="fact check")
            if d.get('results'):
                return d['results'][0].get('content','')[:6000]
        r = requests.get(url, timeout=10, headers={"User-Agent":"Mozilla/5.0"})
        return BeautifulSoup(r.text,'html.parser').get_text()[:6000]
    except Exception as e:
        return str(e)

def live_search(q):
    try:
        if not tavily_client:
            return "No Tavily key", [], ""
        res = tavily_client.search(query=q, search_depth="advanced", max_results=5, include_answer=True)
        text = "\n".join([f"{x['title']}: {x['content'][:400]} URL:{x['url']}" for x in res.get('results',[])])
        urls = [x['url'] for x in res.get('results',[])]
        return text, urls, res.get('answer','')
    except Exception as e:
        return str(e), [], ""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Namaste! I'm SATYA - Live Truth Bot by {CREATOR} 🛡️\nSend any claim/link/video - I verify LIVE!")

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text or ""
    urls = re.findall(r'(https?://\S+)', txt)
    extra = ""
    if urls:
        extra = scrape(urls[0])
        txt = txt + f"\nWEBSITE CONTENT: {extra}"
    
    live_text, v_urls, live_ans = live_search(txt)
    prompt = f"{SYSTEM}\nUser Claim: {txt}\nLIVE DATA: {live_text}\nLIVE ANS: {live_ans}\nGive answer with verified links {v_urls}"
    
    if "who created" in txt.lower() or "who made you" in txt.lower() or "founder" in txt.lower() or "creator" in txt.lower():
        await update.message.reply_text(f"I was created by HIBA HAANIYA.F — Founder & CEO of SATYA, built to stop fake news in India and worldwide. 🛡️")
        return

    try:
        comp = groq_client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"user","content":prompt}], temperature=0.2)
        reply = comp.choices[0].message.content
    except Exception as e:
        reply = f"Error: {e}"
    
    if any(w in txt.lower() for w in ["gold","silver","stock","crypto","invest","sensex","market","price"]):
        reply += "\n\n⚠️ Disclaimer: This bot provides informational summaries, not financial advice. Double-check market parameters before investing."
    
    await update.message.reply_text(reply, disable_web_page_preview=False)

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    print("SATYA Live by HIBA HAANIYA.F starting...")
    app.run_polling()
