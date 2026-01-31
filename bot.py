import os
import socket
from flask import Flask, request, abort
import telebot
import requests

app = Flask(__name__)

# ────────────────────────────────────────────────
# Load bot token from environment
# ────────────────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is missing. Set it in Render → Environment.")

bot = telebot.TeleBot(BOT_TOKEN, threaded=False)

# ────────────────────────────────────────────────
# Escape helper for MarkdownV2
# ────────────────────────────────────────────────
def escape_md_v2(text: str) -> str:
    """Escape all reserved MarkdownV2 characters"""
    chars = r'_[]()~`>#+-=|{}.!'
    for c in chars:
        text = text.replace(c, f'\\{c}')
    return text

# ────────────────────────────────────────────────
# Validate IPv4 or IPv6
# ────────────────────────────────────────────────
def is_valid_ip(ip_str: str) -> bool:
    try:
        socket.inet_pton(socket.AF_INET, ip_str)
        return True
    except socket.error:
        try:
            socket.inet_pton(socket.AF_INET6, ip_str)
            return True
        except socket.error:
            return False

# ────────────────────────────────────────────────
# /start and /myip handler
# ────────────────────────────────────────────────
@bot.message_handler(commands=['start', 'myip'])
def send_welcome(message):
    markup = telebot.types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        telebot.types.InlineKeyboardButton(
            "Check My Own IP + Details",
            url="https://whatismyipaddress.com"
        )
    )
    markup.add(
        telebot.types.InlineKeyboardButton(
            "Just My Raw IP",
            url="https://api.ipify.org"
        )
    )

    username = escape_md_v2(message.from_user.first_name or "there")

    text = (
        f"Hi {username}\\! 👋\n\n"
        "I can't see your IP \\(Telegram keeps it private\\)\\.\n\n"
        "Use the buttons above to see **your own** public IP details "
        "the same way whatismyipaddress\\.com shows them\\.\n\n"
        "Or just send me any IPv4 or IPv6 address and I'll look it up for you:\n"
        "• Country / Region / City\n"
        "• ISP / Organization\n"
        "• Coordinates / Timezone\n"
        "• Mobile / Proxy / Hosting flags\n\n"
        "Examples:\n"
        "`8\\.8\\.8\\.8`\n"
        "`2001:4860:4860::8888`"
    )

    # Use send_message instead of reply_to to avoid "message not found" in webhook mode
    bot.send_message(message.chat.id, text, parse_mode='MarkdownV2', reply_markup=markup)

# ────────────────────────────────────────────────
# IP lookup (IPv4 + IPv6)
# ────────────────────────────────────────────────
@bot.message_handler(func=lambda message: is_valid_ip(message.text.strip()))
def lookup_ip(message):
    ip = message.text.strip()

    try:
        url = (
            f"http://ip-api.com/json/{ip}?"
            "fields=status,message,query,country,countryCode,regionName,region,"
            "city,zip,lat,lon,timezone,isp,org,as,mobile,proxy,hosting"
        )
        resp = requests.get(url, timeout=8)
        resp.raise_for_status()
        data = resp.json()

        if data.get('status') != 'success':
            text = (
                f"❌ Lookup failed for **{escape_md_v2(ip)}**\n"
                f"Reason: {escape_md_v2(data.get('message', 'Unknown error'))}"
            )
        else:
            country     = escape_md_v2(data.get('country', 'N/A'))
            cc          = escape_md_v2(data.get('countryCode', 'N/A'))
            region_name = escape_md_v2(data.get('regionName', 'N/A'))
            region      = escape_md_v2(data.get('region', 'N/A'))
            city        = escape_md_v2(data.get('city', 'N/A'))
            zip_code    = escape_md_v2(data.get('zip', 'N/A'))
            tz          = escape_md_v2(data.get('timezone', 'N/A'))
            isp         = escape_md_v2(data.get('isp', 'N/A'))
            org         = escape_md_v2(data.get('org', 'N/A'))
            asn         = escape_md_v2(data.get('as', 'N/A'))

            text = (
                f"**IP Lookup** \\(data similar to whatismyipaddress\\.com\\)\n\n"
                f"**{escape_md_v2(data['query'])}**\n\n"
                f"🌍 Country: {country} \\({cc}\\)\n"
                f"🏞 Region: {region_name} \\({region}\\)\n"
                f"🏙 City: {city}\n"
                f"📮 ZIP: {zip_code}\n"
                f"📍 Lat/Lon: {data.get('lat', 'N/A')}, {data.get('lon', 'N/A')}\n"
                f"🕒 Timezone: {tz}\n"
                f"🌐 ISP: {isp}\n"
                f"🏢 Org: {org}\n"
                f"🔗 AS: {asn}\n"
                f"📱 Mobile?: {'Yes' if data.get('mobile') else 'No'}\n"
                f"🕵️ Proxy/VPN/Hosting?: {'Yes' if data.get('proxy') or data.get('hosting') else 'No'}"
            )

    except requests.RequestException as e:
        text = f"⚠️ Network problem while looking up **{escape_md_v2(ip)}**\\.\n{escape_md_v2(str(e))}"
    except Exception as e:
        text = f"❗ Something went wrong\\.\n{escape_md_v2(str(e))}"

    # Use send_message instead of reply_to to avoid "message not found" in webhook mode
    bot.send_message(message.chat.id, text, parse_mode='MarkdownV2')

# ────────────────────────────────────────────────
# Webhook endpoint
# ────────────────────────────────────────────────
@app.route('/webhook', methods=['POST'])
def telegram_webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    else:
        abort(403)

# Health check route
@app.route('/')
@app.route('/health')
def health_check():
    return "Bot is running (webhook mode)", 200

# ────────────────────────────────────────────────
# Set webhook when the app starts
# ────────────────────────────────────────────────
if __name__ == "__main__":
    hostname = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
    if not hostname:
        raise RuntimeError("RENDER_EXTERNAL_HOSTNAME not found – are you running on Render?")

    webhook_url = f"https://{hostname}/webhook"

    print(f"Setting webhook → {webhook_url}")

    try:
        bot.remove_webhook()
        print("Previous webhook removed")

        success = bot.set_webhook(
            url=webhook_url,
            allowed_updates=["message"]
        )
        print("Webhook set successfully" if success else "set_webhook returned False")
    except Exception as e:
        print(f"Webhook setup failed: {str(e)}")

    port = int(os.environ.get("PORT", 5000))
    print(f"Starting server on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)