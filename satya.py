import os, requests, hashlib, time, json
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from groq import Groq
from tavily import TavilyClient

load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN")
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

CACHE = {}

def now():
    return datetime.now().strftime("%d %B %Y, %I:%M %p IST")

def google_search(q):
    combined = ""
    try:
        r = tavily_client.search(query=q, max_results=8, include_answer=True, search_depth="advanced")
        combined += f" LIVE: {r.get('answer','')} "
        for d in r.get('results',[])[:3]:
            combined += f" {d.get('title','')}: {d.get('content','')[:700]} "
    except: pass
    try:
        w = requests.get(f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={q}&format=json&srlimit=2", timeout=5).json()
        for item in w.get('query',{}).get('search',[])[:2]:
            combined += f" WIKI: {item['title']}: {item['snippet']} "
    except: pass
    return combined

def ask_best(q):
    key = hashlib.md5(q.lower().strip().encode()).hexdigest()
    if key in CACHE:
        return CACHE[key]
    knowledge = google_search(q)
    if len(knowledge) < 30:
        knowledge = "No strong live result, use accurate general knowledge."

    prompt = f"""
You are SATYA by HIBA HAANIYA.F, Founder and CEO. Date: {now()}
You know everything like Google — general knowledge + real world news.

RULES FOR PERFECT FOREVER:
1. If live knowledge says 【entity-Jungkook¦canonical_name=Jungkook】 performed Dreamers at Qatar 2022 opening, you MUST say TRUE — 【entity-Jungkook¦canonical_name=Jungkook】 of the famous K-pop group performed in 2022.
2. Believe live knowledge for politics, elections, sports.
3. NEVER invent singers or finals unless live knowledge says it.
4. If no proof, say PARTIAL, never FALSE without proof.
5. PLAIN TEXT ONLY — Never output tags like entity or brackets. Only plain English.
6. Format:
TRUE/FALSE/PARTIAL verdict in one line
2 lines proof
Date: {now()}
— SATYA by HIBA HAANIYA.F

LIVE KNOWLEDGE: {knowledge[:5000]}
USER QUESTION: {q}
"""
    for model in ["llama-3.3-70b-versatile", "openai/gpt-oss-20b", "llama-3.1-8b-instant"]:
        try:
            c = groq_client.chat.completions.create(model=model, messages=[{"role":"user","content":prompt}], temperature=0.0, max_tokens=800)
            ans = c.choices[0].message.content.strip()
            # CLEAN ANY ENTITY TAGS IF MODEL STILL ADDS
            ans = ans.replace("【entity-", "").replace("】", "").replace("canonical_name=", "").replace("'", "").replace("[", "").replace("]", "")
            CACHE[key] = ans
            return ans
        except: continue
    return "PARTIAL — Busy, try again — SATYA by HIBA HAANIYA.F"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # CLEAN START MESSAGE — NO TRIGGER WORDS — SO NO TAGS EVER
    await update.message.reply_text(
        f"SATYA - GOOGLE LEVEL - LIVE\n"
        f"HIBA HAANIYA.F Founder and CEO\n"
        f"{now()}\n\n"
        f"Like Google: Knows Everything\n"
        f"Live Search + Wiki + No Lie + Perfect Forever\n"
        f"Ask anything - music, football, politics, science!"
    )

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.message.text.strip()
    if "who created" in q.lower():
        await update.message.reply_text("Created by HIBA HAANIYA.F - Founder and CEO - SATYA - Google Level")
        return
    wait = await update.message.reply_text("SATYA Google-Level searching entire web live... 3 sec...")
    ans = ask_best(q)
    try: await wait.delete()
    except: pass
    await update.message.reply_text(ans)

def main():
    print(f"STARTING CLEAN BEST SATYA — {now()} — NO ENTITY TAGS")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
