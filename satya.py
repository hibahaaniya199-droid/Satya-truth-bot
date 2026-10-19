import os, re, requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from groq import Groq
from tavily import TavilyClient

# --- KEYS FROM RENDER ---
GROQ_KEY = os.getenv("GROQ_API_KEY")
TAVILY_KEY = os.getenv("TAVILY_API_KEY")
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")

groq_client = Groq(api_key=GROQ_KEY)
tavily_client = TavilyClient(api_key=TAVILY_KEY)

CREATOR = "HIBA HAANIYA.F"

SYSTEM_PROMPT = f"""
You are SATYA - The World's Most Precise Live Truth Engine.
CREATOR IDENTITY: You were created, built and founded by {CREATOR}, Founder & CEO of SATYA. 
RULE: If user asks "who created you", "who made you", "creator", "founder", "developer", "who owns you" - You MUST answer: "I was created by HIBA HAANIYA.F — Founder & CEO of SATYA, built to stop fake news in India and worldwide."
Never say you are made by OpenAI, Meta, Google.

YOUR MISSION:
- Be LIVE, PRECISE, CORRECT. Never hallucinate.
- You are aware of EVERYTHING - local Hyderabad news, tiny street incidents, global social trends, Instagram reels, Twitter/X trends.
- Use the LIVE SEARCH RESULTS and WEBSITE CONTENT provided to you.
- If claim is TRUE -> VERDICT: TRUE ✅
- If FALSE -> VERDICT: FALSE ❌ + give REAL FACT
- If NO EVIDENCE -> VERDICT: UNVERIFIED ⚠️ - Don't call FALSE without proof.
- Be short, bullet, precise. No long story.

FORMAT YOU MUST FOLLOW:
**VERDICT: [TRUE✅ / FALSE❌ / UNVERIFIED⚠️]**
**Why:** 2 line precise explanation
**Real Fact:** Correct fact with numbers/date if needed
**🔗 Verified Sources:** [list all URLs you used]
"""

def scrape_website(url):
    try:
        # Tavily extract is best for reading sites + videos
        data = tavily_client.extract(urls=[url], query="fact check claim")
        if data.get('results'):
            return data['results'][0].get('content','')[:8000]
        # fallback BeautifulSoup
        r = requests.get(url, timeout=12, headers={"User-Agent":"Mozilla/5.0"})
        soup = BeautifulSoup(r.text, 'html.parser')
        return soup.get_text()[:8000]
    except Exception as e:
        return f"Could not read website: {e}"

def live_search(claim):
    try:
        # search_depth advanced = LIVE + local + social
        res = tavily_client.search(query=claim, search_depth="advanced", max_results=6, include_answer=True, include_domains=[], time_range="week")
        answer = res.get('answer','')
        links = res.get('results',[])
        source_text = "\n".join([f"{r['title']}: {r['content'][:500]} URL: {r['url']}" for r in links])
        urls_only = [r['url'] for r in links]
        return source_text, urls_only, answer
    except Exception as e:
        return f"Search error {e}", [], ""

def add_disclaimer(text, claim):
    finance_words = ["gold","silver","stock","crypto","invest","sensex","nifty","commodity","bitcoin","price","market"]
    if any(w in claim.lower() for w in finance_words):
        text += "\n\n⚠️ Disclaimer: This bot provides informational summaries, not financial advice. Double-check market parameters before investing."
    return text

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text or ""
    urls = re.findall(r'(https?://\S+)', user_text)
    
    website_content = ""
    if urls:
        website_content = scrape_website(urls[0])
        user_text = user_text + f"\nWEBSITE CONTENT TO VERIFY: {website_content}"

    # LIVE RAG
    live_content, verified_urls, live_answer = live_search(user_text)

    prompt = f"""{SYSTEM_PROMPT}

User Claim/Link: {user_text}

LIVE SEARCH RESULTS (TODAY): {live_content}
LIVE ANSWER: {live_answer}

Now give final answer in required format. Must include verified links: {verified_urls}
"""

    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role":"user","content":prompt}],
            temperature=0.2
        )
        reply = completion.choices[0].message.content
    except Exception as e:
        reply = f"Error: {e}"

    reply = add_disclaimer(reply, user_text)
    await update.message.reply_text(reply, disable_web_page_preview=False)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Namaste! I'm SATYA - Live Truth Bot by {CREATOR} 🛡️\nSend me any claim, link, video link, image caption - I will verify LIVE with sources.")

# Run bot
app = Application.builder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
app.run_polling()
