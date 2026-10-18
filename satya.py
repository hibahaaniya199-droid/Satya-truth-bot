import os
import time
import requests
from flask import Flask
import threading

# --- CONFIG ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# Flask to keep Render alive
app = Flask(__name__)

@app.route('/')
def home():
    return "SATYA TRUTH BOT IS ALIVE - 24/7"

def ask_groq(user_text):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    system_prompt = """
You are SATYA - The Truth Bot. You verify news.

CRITICAL LANGUAGE RULE: 
1. Detect the language of the user's message.
2. You MUST answer in the SAME LANGUAGE as the user.
3. If user writes Hindi -> answer in Hindi. Telugu -> Telugu. Korean -> Korean. English -> English.
4. Never default to English unless user wrote in English.

Format your answer EXACTLY like this (but in user's language):
**CLAIM:** <repeat claim>
**VERDICT:** TRUE / FALSE / HALF TRUE
**EXPLANATION:** <short explanation in same language as user>

Be concise and accurate.
"""

    data = {
        "model": "openai/gpt-oss-20b",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text}
        ],
        "temperature": 0.2
    }
    
    try:
        res = requests.post(url, headers=headers, json=data, timeout=30)
        result = res.json()
        return result['choices'][0]['message']['content']
    except Exception as e:
        return f"Error: {e}"

def telegram_bot():
    offset = 0
    print("BOT ALIVE")
    while True:
        try:
            url = f"{TELEGRAM_API}/getUpdates?offset={offset}&timeout=30"
            r = requests.get(url, timeout=35)
            updates = r.json().get("result", [])
            for update in updates:
                offset = update["update_id"] + 1
                if "message" in update and "text" in update["message"]:
                    chat_id = update["message"]["chat"]["id"]
                    user_text = update["message"]["text"]
                    
                    if user_text == "/start":
                        reply = "Namaste! I am SATYA Truth Bot. Send any news and I will check TRUE/FALSE in YOUR language! 🙏"
                    else:
                        reply = ask_groq(user_text)
                    
                    requests.post(f"{TELEGRAM_API}/sendMessage", json={"chat_id": chat_id, "text": reply, "parse_mode": "Markdown"})
        except Exception as e:
            print(f"Loop error: {e}")
            time.sleep(5)

# Start bot in background thread
threading.Thread(target=telegram_bot, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
