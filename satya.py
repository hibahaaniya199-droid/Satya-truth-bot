import os, requests, hashlib
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from groq import Groq
from tavily import TavilyClient

load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN")
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

# 🌍 WORLD TIME MAP — PRECISE FOR EVERY PLACE
TIMEZONES = {
    "india": ("IST", "Asia/Kolkata"), "ist": ("IST", "Asia/Kolkata"),
    "south korea": ("KST", "Asia/Seoul"), "korea": ("KST", "Asia/Seoul"), "seoul": ("KST", "Asia/Seoul"),
    "japan": ("JST", "Asia/Tokyo"), "tokyo": ("JST", "Asia/Tokyo"),
    "new york": ("EST", "America/New_York"), "usa": ("EST", "America/New_York"), "america": ("EST", "America/New_York"),
    "london": ("GMT", "Europe/London"), "uk": ("GMT", "Europe/London"),
    "dubai": ("GST", "Asia/Dubai"), "qatar": ("AST", "Asia/Qatar"),
    "paris": ("CET", "Europe
