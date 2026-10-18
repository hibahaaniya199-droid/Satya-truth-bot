import requests, time, os
import threading
from flask import Flask
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
app = Flask(__name__)
@app.route('/')
def home():
    return "SATYA IS ALIVE 24/7!"
def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

def check_truth(news_text):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    data = {"model": "openai/gpt-oss-20b","messages": [{"role": "system","content": "You are Satya Truth Bot. Give CLAIM, VERDICT TRUE/FALSE/HALF TRUE, and short explanation."},{"role": "user","content": news_text}]}
    r = requests.post(url, headers=headers, json=data, timeout=30)
    return r.json()["choices"][0]["message"]["content"]

print("SATYA TRUTH BOT IS ALIVE - FOREVER!")
threading.Thread(target=run_flask, daemon=True).start()
offset=0
while True:
    try:
        url=f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={offset}&timeout=30"
        resp=requests.get(url, timeout=35).json()
        for update in resp.get("result",[]):
            offset=update["update_id"]+1
            if "message" in update:
                chat_id=update["message"]["chat"]["id"]
                text=update["message"].get("text","")
                if text=="/start":
                    reply="Namaste! Send any news LINK and I will tell TRUE/FALSE/HALF TRUE"
                else:
                    reply=check_truth(text)
                requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id":chat_id,"text":reply})
    except Exception as e:
        print(e);time.sleep(5)
