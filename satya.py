import os, re, requests, asyncio, nest_asyncio
nest_asyncio.apply()
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

SYSTEM = f"You are SATYA - Live Truth Engine. Creator is {CREATOR}, Founder & CEO of SATYA. If user asks who created you, MUST say: I was created by HIBA HAANIYA.F — Founder & CEO of SATYA."

def scrape(url):
    try:
        if tavily_client:
            d = tavily_client.extract(urls=[url], query="fact check")
            if d.get('results'): return d['results'][0].get('content','')[:6000]
        r = requests.get(url, timeout=10, headers={"User-Agent":"Mozilla/5.0"})
        return BeautifulSoup(r.text,'html.parser').get_text()[:6000]
    except Exception as e: return str(e)

def live_search(q):
    try:
        if not tavily_client: return "No key", [], ""
        res = tavily_client.search(query=q, search_depth="advanced", max_results=5, include_answer=True)
        text = "\n".join([f"{x['title']}: {x['content'][:400]} URL:{x['url']}" for x in res.get('results',[])])
        urls = [x['url'] for x in res.get('results',[])]
        return text, urls, res.get('answer','')
    except Exception as e: return str(e), [], ""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Namaste! I'm SATYA by {CREATOR} 🛡️ Send any claim/link!")

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text or ""
    urls = re.findall(r'(https?://\S+)', txt)
    if urls:
        txt = txt + f"\nCONTENT: {scrape(urls[0])}"
    if "who created" in txt.lower() or "who made" in txt.lower() or "founder" in txt.lower() or "creator" in txt.lower() or "hiba" in txt.lower():
        await update.message.reply_text(f"I was created by HIBA HAANIYA.F — Founder & CEO of SATYA, built to stop fake news. 🛡️")
        return
    live_text, v_urls, live_ans = live_search(txt)
    prompt = f"{SYSTEM}\nUser Claim: {txt}\nLIVE: {live_text}\nAnswer with VERDICT, Why, Real Fact, Sources {v_urls}. Disclaimer if finance."
    try:
        comp = groq_client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"user","content":prompt}], temperature=0.2)
        reply = comp.choices[0].message.content
    except Exception as e: reply = f"Error: {e}"
    await update.message.reply_text(reply)

async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    print(f"SATYA Live by {CREATOR} starting...")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
