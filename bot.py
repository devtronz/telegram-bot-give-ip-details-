import os
from flask import Flask, request, abort
import telebot
import requests
import json

app = Flask(__name__)

# ────────────────────────────────────────────────
# Load Telegram Bot Token from environment variable
# ────────────────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is not set! Set it in Render → Environment tab.")

# Create bot instance WITHOUT threading (required on Render free tier)
bot = telebot.TeleBot(BOT_TOKEN, threaded=False)

# ────────────────────────────────────────────────
# Helper to escape special characters for MarkdownV2
# ────────────────────────────────────────────────
def escape_md_v2(text: str) -> str:
    """Escape Telegram MarkdownV2 special characters"""
    chars_to_escape = r'_[]()~`>#+-=|{}.!'
    for char in chars_to_escape:
        text = text.replace(char, f'\\{char}')
    return text

# ────────────────────────────────────────────────
# /start and /myip command – shows help + links
# ────────────────────────────────────────────────
@bot.message_handler(commands=['start', 'myip'])
def help_message(message):
    markup = telebot.types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        telebot.types.InlineKeyboardButton(
            "Check My Own IP + Full Details",
            url="https://whatismyipaddress.com"
        )
    )
    markup.add(
        telebot.types.InlineKeyboardButton(
            "Just My Raw IP",
            url="https://api.ipify.org"
        )
    )

    text = (
        f"Hi {escape_md_v2(message.from_user.first_name)}! 👋\n"
        "Telegram doesn't share your real IP with bots \\(privacy first\\).\n\n"
        "Tap the buttons above to see your own public IP details \\(like on whatismyipaddress\\.com\\).\n\n"
        "Or send me any IP address \\(example: `8\\.8\\.8\\.8`\\) and I'll show:\n"
        "• Country, city, region\n"
        "• ISP, organization\n"
        "• Coordinates, timezone\n"
        "• Proxy/VPN status\n"
    )

    bot.reply_to(message, text, parse_mode='MarkdownV2', reply_markup=markup)

# ────────────────────────────────────────────────
# Handle messages that look like IPv4 addresses
# ────────────────────────────────────────────────
@bot.message_handler(regexp=r'\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b')
def ip_lookup(message):
    ip = message.text.strip()

    try:
        url = (
            f"http://ip-api.com/json/{ip}?"
            "fields=status,message,query,country,countryCode,regionName,region,"
            "city,zip,lat,lon,timezone,isp,org,as,mobile,proxy,hosting"
        )
        r = requests.get(url, timeout=8)
        r.raise_for_status()
        data = r.json()

        if data.get('status') == 'success':
            country     = escape_md_v2(data['country'])
            countryCode = escape_md_v2(data['countryCode'])
            regionName  = escape_md_v2(data['regionName'])
            region      = escape_md_v2(data['region'])
            city        = escape_md_v2(data['city'])
            zip_code    = escape_md_v2(data.get('zip', 'N/A'))
            timezone    = escape_md_v2(data['timezone'])
            isp         = escape_md_v2(data['isp'])
            org         = escape_md_v2(data.get('org', 'N/A'))
            as_info     = escape_md_v2(data.get('as', 'N/A'))

            reply = (
                f"**IP Lookup Results** \\(similar to whatismyipaddress\\.com\\):\n\n"
                f"IP: **{data['query']}**\n\n"
                f"🌍 Country: {country} \\({countryCode}\\)\n"
                f"🏞️ Region: {regionName} \\({region}\\)\n"
                f"🏙️ City: {city}\n"
                f"📮 ZIP/Postal: {zip_code}\n"
                f"📍 Coordinates: {data['lat']}, {data['lon']}\n"
                f"🕒 Timezone: {timezone}\n"
                f"🌐 ISP: {isp}\n"
                f"🏢 Organization: {org}\n"
                f"🔗 AS: {as_info}\n"
                f"📱 Mobile network?: {'Yes' if data.get('mobile') else 'No'}\n"
                f"🕵️ Proxy/VPN/Hosting?: {'Yes' if data.get('proxy') or data.get('hosting') else 'No'}"
            )
        else:
            reply = (
                f"❌ Lookup failed\n"
                f"Message: {escape_md_v2(data.get('message', 'Unknown error'))}"
            )

    except requests.exceptions.RequestException as e:
        reply = f"⚠️ Network error while fetching IP info: {escape_md_v2(str(e))}"
    except Exception as e:
        reply = f"❗ Unexpected error: {escape_md_v2(str(e))}\nTry again later."

    bot.reply_to(message, reply, parse_mode='MarkdownV2')

# ────────────────────────────────────────────────
# Webhook endpoint – Telegram sends POST requests here
# ────────────────────────────────────────────────
@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    else:
        abort(403)

# Simple health check route (Render likes this)
@app.route('/')
@app.route('/health')
def health():
    return "Telegram IP Lookup Bot is running via webhook 🚀", 200

# ────────────────────────────────────────────────
# Set webhook on startup (only once per deploy)
# ────────────────────────────────────────────────
if __name__ == "__main__":
    # Get the public URL Render provides (automatic env var)
    render_hostname = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
    if not render_hostname:
        raise ValueError("RENDER_EXTERNAL_HOSTNAME not found – are you running on Render?")

    webhook_url = f"https://{render_hostname}/webhook"

    print(f"Preparing to set webhook to: {webhook_url}")

    try:
        # Clear any old webhook or polling first
        bot.remove_webhook(drop_pending_updates=True)
        print("Old webhook/polling removed (if any)")

        # Set the new webhook
        bot.set_webhook(
            url=webhook_url,
            drop_pending_updates=True,   # Clear queue on switch
            allowed_updates=["message"]  # Only need text messages for this bot
        )
        print(f"Webhook successfully set to {webhook_url}")
    except Exception as e:
        print(f"Failed to set webhook: {e}")
        # Don't crash the app – Render will restart if needed

    # Start Flask
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting Flask server on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)