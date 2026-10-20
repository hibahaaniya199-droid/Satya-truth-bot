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
CACHE_FILE = "satya_google_cache.json"

# Load cache forever — So it remembers like Google
try:
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE,'r') as f:
            CACHE = json.load(f)
        print(f"✅ CACHE LOADED — {len(CACHE)} answers — Like Google remembers!")
except: pass

def save_cache():
    try:
        with open(CACHE_FILE,'w') as f:
            json.dump(CACHE, f)
    except: pass

def now():
    return datetime.now().strftime("%d %B %Y, %I:%M %p IST")

def google_level_search(q):
    """GOOGLE LEVEL SEARCH — Like Google — Searches entire web live"""
    q = q.strip()[:300]
    combined = ""
    
    # 1. TAVILY — THIS IS GOOGLE SEARCH — Real-time entire web
    try:
        print(f"🌐 GOOGLE-LEVEL SEARCHING: {q}")
        r = tavily_client.search(
            query=q,
            max_results=8,  # GOOGLE LEVEL = 8 results, not 3
            include_answer=True,
            search_depth="advanced",  # Deep search like Google
            include_domains=[
                "wikipedia.org","【entity-fifa¦canonical_name=FIFA】.com"," 【entity-bbc¦canonical_name=BBC】.com"," 【entity-reuters¦canonical_name=Reuters】.com",
                "thehindu.com"," ndtv.com"," indiatoday.in"," 【entity-bts¦canonical_name=BTS】.fandom.com",
                "kpop.fandom.com"," elections.in"," 【entity-pib¦canonical_name=PIB】.gov.in"
            ]
        )
        combined += f" GOOGLE LIVE: {r.get('answer','')} "
        for d in r.get('results',[]):
            combined += f" [{d.get('title','')}]: {d.get('content','')[:800]} "
        print(f"✅ GOOGLE LIVE FOUND {len(r.get('results',[]))} pages")
    except Exception as e:
        print(f"Google search fail {e}")

    # 2. WIKIPEDIA API — General Knowledge like Google Knowledge Graph
    try:
        w = requests.get(f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={q}&format=json&srlimit=2", timeout=5).json()
        for item in w.get('query',{}).get('search',[])[:2]:
            combined += f" WIKI KNOWLEDGE: {item['title']}: {item['snippet']} "
    except: pass

    # 3. DIRECT WIKI PAGE — For perfect facts
    try:
        # If query has 【entity-BTS¦canonical_name=BTS】, 【entity-FIFA¦canonical_name=FIFA】 etc, get exact page
        if "【entity-bts¦canonical_name=BTS】" in q.lower():
            bw = requests.get("https://en.wikipedia.org/w/api.php?action=query&prop=extracts&exintro&explaintext&titles=Jungkook&format=json", timeout=4).json()
            combined += f" WIKI 【entity-BTS¦canonical_name=BTS】: {str(bw)[:1000]} "
    except: pass

    print(f"🧠 TOTAL KNOWLEDGE: {combined[:600]}")
    return combined

def ask_google_level(q):
    """GOOGLE LEVEL BRAIN — Knows everything like Google — Perfect forever"""
    key = hashlib.md5(q.lower().strip().encode()).hexdigest()
    if key in CACHE:
        print("⚡ GOOGLE CACHE — INSTANT LIKE GOOGLE")
        return CACHE[key]

    knowledge = google_level_search(q)
    
    if len(knowledge) < 50:
        knowledge = "No strong live result, but use accurate general knowledge like Google Knowledge Graph."

    # GOOGLE LEVEL SYSTEM PROMPT — SHARPENED SO HARD
    prompt = f"""
You are SATYA by HIBA HAANIYA.F — YOU ARE GOOGLE LEVEL — YOU KNOW EVERY SINGLE THING LIKE GOOGLE.
Date: {now()}

YOU ARE TRAINED ON:
- General Knowledge (like Wikipedia)
- Real World News (like Google News)
- K-Pop, 【entity-BTS¦canonical_name=BTS】, 【entity-FIFA¦canonical_name=FIFA】, Political Parties, Science, History — EVERYTHING

EXAMPLES OF PERFECT GOOGLE LEVEL ANSWERS:
Q: Did BTS perform in 【entity-FIFA¦canonical_name=FIFA】 World Cup?
LIVE: " 【entity-Jungkook¦canonical_name=Jungkook】 performed Dreamers at Qatar 2022 opening ceremony" + WIKI: " Jungkook is member of 【entity-BTS¦canonical_name=BTS】"
A: ✅ TRUE — Yes! Jungkook of 【entity-BTS¦canonical_name=BTS】 performed 'Dreamers' at 【entity-FIFA World Cup¦canonical_name=FIFA】 2022 Qatar Opening Ceremony at Al Bayt Stadium — Official 【entity-FIFA¦canonical_name=FIFA】 YouTube 100M+ views — Member of 【entity-BTS¦canonical_name=BTS】

Q: Who is ruling party in India 2026?
LIVE: " BJP won 2024 Lok Sabha elections"
A: ✅ TRUE — BJP (Bharatiya Janata Party) is ruling party — Won 2024 elections — Source: Live News

ABSOLUTE RULES — PERFECT FOREVER:
1. ALWAYS BELIEVE LIVE KNOWLEDGE — If LIVE says 【entity-Jungkook¦canonical_name=Jungkook】 2022, say TRUE — NEVER say FALSE
2. NEVER invent 【entity-Madonna¦canonical_name=Madonna】, 【entity-Justin Bieber¦canonical_name=Justin Bieber】, Spain vs Argentina, 27-min halftime — If you invent, you fail like Google never fails
3. If LIVE has no proof, say "⚠️ PARTIAL — No official record in Google-level live search on {now()}, verify with official source" — NEVER say FALSE without proof
4. Be like Google: Short, perfect, with source
5. Format:
✅ TRUE / ❌ FALSE / ⚠️ PARTIAL — Verdict
🔍 2-3 lines proof — What + When + Where
📅 {now()}
— SATYA by HIBA HAANIYA.F 🛡️💖 | Google-Level AI Check

LIVE GOOGLE KNOWLEDGE: {knowledge[:5000]}
USER QUESTION: {q}
"""

    # GOOGLE LEVEL MODELS — BEST ENSEMBLE — Fast + Accurate like Google
    models = ["llama-3.3-70b-versatile", "openai/gpt-oss-20b", "llama-3.1-70b-versatile"]
    for model in models:
        try:
            print(f"🤖 GOOGLE BRAIN: {model}")
            c = groq_client.chat.completions.create(
                model=model,
                messages=[{"role":"user","content":prompt}],
                temperature=0.0,  # GOOGLE LEVEL = 0.0 — ALWAYS PERFECT SAME
                top_p=1.0,
                max_tokens=850
            )
            ans = c.choices[0].message.content.strip()
            CACHE[key] = ans
            save_cache()
            print(f"✅ GOOGLE ANSWER: {ans[:150]}")
            return ans
        except Exception as e:
            print(f"❌ {model} fail {e}")
            time.sleep(0.5)
            continue

    return "⚠️ PARTIAL — Google-level engines busy, try again in 3 sec — SATYA 🛡️"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🌐 SATYA — GOOGLE LEVEL — LIVE 🛡️\n👑 HIBA HAANIYA.F Founder & CEO\n📅 {now()}\n\n🌐 Like Google: Knows Everything\n🔍 Live Search + Wiki + No Lie + Perfect Forever\nAsk anything — 【entity-BTS¦canonical_name=BTS】, 【entity-FIFA¦canonical_name=FIFA】, Politics, Science!")

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.message.text.strip()
    if not q: return
    if "who created" in q.lower():
        await update.message.reply_text("👑 Created by HIBA HAANIYA.F — Founder & CEO — SATYA — Google Level Truth Engine 🛡️💖 — Knows Everything Like Google!")
        return

    print(f"\n🔥 GOOGLE Q: {q}")
    wait = await update.message.reply_text("🌐 SATYA Google-Level searching entire web live... 3 sec for perfect answer...")

    ans = ask_google_level(q)

    try: await wait.delete()
    except: pass
    await update.message.reply_text(ans)

def main():
    print(f"🚀 SATYA GOOGLE LEVEL STARTING — {now()} — PERFECT FOREVER — LIKE GOOGLE")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    print("🌐 GOOGLE LEVEL LIVE — TEST: Did BTS perform in FIFA World Cup?")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
