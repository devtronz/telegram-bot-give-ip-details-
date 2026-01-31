import os
import threading
from flask import Flask
import telebot
import requests

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("Missing BOT_TOKEN env var – set it in Render → Environment tab!")

bot = telebot.TeleBot(BOT_TOKEN)


# Your existing handlers (copy-paste from before)
@bot.message_handler(commands=['start', 'myip'])
def help_message(message):
    markup = telebot.types.InlineKeyboardMarkup(row_width=1)
    markup.add(telebot.types.InlineKeyboardButton("Check My Own IP + Full Details", url="https://whatismyipaddress.com"))
    markup.add(telebot.types.InlineKeyboardButton("Just My Raw IP", url="https://api.ipify.org"))

    text = (
        f"Hi {message.from_user.first_name}! 👋\n"
        "Telegram doesn't share your IP with bots.\n"
        "Tap above for your own details (like on whatismyipaddress.com).\n\n"
        "Or send any IP (e.g. 8.8.8.8) → I'll show country, city, ISP, etc."
    )
    bot.reply_to(message, text, reply_markup=markup)

@bot.message_handler(regexp=r'\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b')
def ip_lookup(message):
    ip = message.text.strip()
    try:
        url = f"http://ip-api.com/json/{ip}?fields=status,message,query,country,countryCode,regionName,region,city,zip,lat,lon,timezone,isp,org,as,mobile,proxy,hosting"
        r = requests.get(url, timeout=5)
        data = r.json()
        if data.get('status') == 'success':
            reply = (
                f"**IP Lookup Results** (similar to whatismyipaddress.com):\n\n"
                f"IP: **{data['query']}**\n"
                f"Country: {data['country']} ({data['countryCode']})\n"
                f"Region: {data['regionName']} ({data['region']})\n"
                f"City: {data['city']}\n"
                f"ZIP/Postal: {data.get('zip', 'N/A')}\n"
                f"Coordinates: {data['lat']}, {data['lon']}\n"
                f"Timezone: {data['timezone']}\n"
                f"ISP: {data['isp']}\n"
                f"Organization: {data.get('org', 'N/A')}\n"
                f"AS Number: {data.get('as', 'N/A')}\n"
                f"Mobile Network?: {'Yes' if data['mobile'] else 'No'}\n"
                f"Proxy/VPN/Tor/Hosting?: {'Yes' if data['proxy'] or data['hosting'] else 'No'}"
            )
        else:
            reply = f"Error: {data.get('message', 'Could not lookup this IP')}"
    except Exception as e:
        reply = f"Lookup failed: {str(e)}"
    bot.reply_to(message, reply, parse_mode='Markdown')

# Simple health endpoint for Render
@app.route('/')
def home():
    return "Bot is alive! Send /myip in Telegram."

@app.route('/health')
def health():
    return "OK", 200

def run_bot():
    bot.infinity_polling(none_stop=True, interval=0, timeout=20)

if __name__ == "__main__":
    # Run polling in background thread
    threading.Thread(target=run_bot, daemon=True).start()
    # Run Flask server on Render's PORT
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
