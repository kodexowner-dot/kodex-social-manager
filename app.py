import logging
import os
import requests
from flask import Flask, request, jsonify

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)

META_VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

@app.get("/")
def health():
    return jsonify(service="KODEX AI MANAGER", status="running")

@app.get("/webhook")
def verify_meta_webhook():
    """Meta webhook verification endpoint."""
    mode = request.args.get("hub.mode", "")
    token = request.args.get("hub.verify_token", "")
    challenge = request.args.get("hub.challenge", "")
    if mode == "subscribe" and META_VERIFY_TOKEN and token == META_VERIFY_TOKEN:
        return challenge, 200
    return "Verification failed", 403

def send_telegram_notice(text: str) -> None:
    """Send an incoming lead/message notice to the configured Telegram chat."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logging.warning("Telegram credentials are not configured; notice not sent.")
        return
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text},
            timeout=10,
        )
        response.raise_for_status()
    except requests.RequestException:
        logging.exception("Telegram notification failed")

@app.post("/webhook")
def receive_meta_webhook():
    """
    Initial webhook receiver. Meta app permissions, product setup, subscriptions,
    and signature validation must be configured before production use.
    """
    payload = request.get_json(silent=True) or {}
    logging.info("Received Meta webhook object=%s", payload.get("object", "unknown"))

    # Deliberately don't reply to users yet. First configure and test the official
    # Meta webhook subscription and event format for the connected Page/Instagram.
    # This starter only forwards text message events if they appear in the standard
    # messaging structure; actual payloads differ by Meta product/API version.
    try:
        for entry in payload.get("entry", []):
            for event in entry.get("messaging", []):
                sender_id = event.get("sender", {}).get("id", "unknown")
                message = event.get("message", {})
                text = message.get("text")
                if text:
                    send_telegram_notice(
                        "📩 Новое сообщение из подключённой соцсети\n"
                        f"ID отправителя: {sender_id}\n"
                        f"Сообщение: {str(text)[:2500]}"
                    )
    except Exception:
        logging.exception("Could not process webhook payload")

    return "EVENT_RECEIVED", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "10000")))
