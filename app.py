import hashlib
import hmac
import logging
import os
from typing import Any

import requests
from flask import Flask, jsonify, request

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
app = Flask(__name__)

# Configure these values in Render > Environment, never in source code.
META_VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN", "")
META_APP_SECRET = os.getenv("META_APP_SECRET", "")
META_PAGE_ACCESS_TOKEN = os.getenv("META_PAGE_ACCESS_TOKEN", "")
META_GRAPH_API_VERSION = os.getenv("META_GRAPH_API_VERSION", "v22.0")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_BOT_URL = os.getenv("TELEGRAM_BOT_URL", "https://t.me/KodexAIMGroupBot")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
REQUEST_TIMEOUT = 12


@app.get("/")
def health():
    return jsonify(
        service="KODEX MEDIA GROUP — Social Manager",
        status="running",
        webhook="/webhook",
        platforms=["Facebook", "Instagram"],
    )


@app.get("/health")
def health_check():
    return jsonify(status="ok"), 200


@app.get("/webhook")
def verify_meta_webhook():
    mode = request.args.get("hub.mode", "")
    token = request.args.get("hub.verify_token", "")
    challenge = request.args.get("hub.challenge", "")
    if mode == "subscribe" and META_VERIFY_TOKEN and hmac.compare_digest(token, META_VERIFY_TOKEN):
        return challenge, 200
    return "Verification failed", 403


def valid_meta_signature(raw_body: bytes) -> bool:
    # Meta App Secret is strongly recommended. If configured, reject unsigned/invalid requests.
    if not META_APP_SECRET:
        return True
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not signature.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(
        META_APP_SECRET.encode("utf-8"), raw_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(signature, expected)


def send_telegram_notice(message: str) -> None:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logging.warning("Telegram credentials are not configured; notification skipped.")
        return
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": message[:3900], "disable_web_page_preview": True},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException:
        logging.exception("Telegram notification failed")


def generate_ai_reply(user_message: str) -> str:
    """Use OpenAI when configured; otherwise return a safe, useful fallback."""
    if not OPENAI_API_KEY:
        return (
            "Здравствуйте! Спасибо, что написали в KODEX MEDIA GROUP. "
            "Подскажите, какая услуга вас интересует: реклама, SMM, дизайн или AI-решения? "
            f"Для заявки можно перейти в Telegram: {TELEGRAM_BOT_URL}"
        )
    system_prompt = (
        "Ты — вежливый ИИ-менеджер KODEX MEDIA GROUP, компании в сфере рекламы, "
        "медиа и digital. Отвечай по-русски кратко и естественно. Уточняй задачу, "
        "площадку, сроки и бюджет только по необходимости. Не выдумывай цены, "
        "гарантии или выполненные работы. Если точная цена неизвестна, предложи "
        "оставить заявку менеджеру. Мягко предлагай Telegram для заявки: "
        + TELEGRAM_BOT_URL
    )
    try:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            json={
                "model": OPENAI_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message[:3000]},
                ],
                "max_tokens": 220,
                "temperature": 0.5,
            },
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()
        answer = data["choices"][0]["message"]["content"].strip()
        return answer[:1800] if answer else f"Спасибо! Оставьте заявку: {TELEGRAM_BOT_URL}"
    except (requests.RequestException, KeyError, IndexError, ValueError):
        logging.exception("AI reply generation failed")
        return (
            "Спасибо за сообщение! Чтобы менеджер уточнил детали и стоимость, "
            f"оставьте заявку в Telegram: {TELEGRAM_BOT_URL}"
        )


def send_meta_reply(recipient_id: str, message_text: str) -> bool:
    if not META_PAGE_ACCESS_TOKEN:
        logging.warning("META_PAGE_ACCESS_TOKEN is missing; automatic reply skipped.")
        return False
    url = f"https://graph.facebook.com/{META_GRAPH_API_VERSION}/me/messages"
    try:
        response = requests.post(
            url,
            params={"access_token": META_PAGE_ACCESS_TOKEN},
            json={
                "recipient": {"id": recipient_id},
                "messaging_type": "RESPONSE",
                "message": {"text": message_text[:1900]},
            },
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return True
    except requests.RequestException:
        logging.exception("Meta reply failed. Check Page token, app permissions, and messaging window.")
        return False


def notify_message(platform: str, sender_id: str, text: str) -> None:
    send_telegram_notice(
        "📩 Новое сообщение — KODEX MEDIA GROUP\n"
        f"Платформа: {platform}\n"
        f"ID отправителя: {sender_id}\n"
        f"Текст: {text[:1800]}\n"
        f"Telegram для заявки: {TELEGRAM_BOT_URL}"
    )


def process_messaging_event(event: dict[str, Any], platform: str) -> None:
    sender_id = str((event.get("sender") or {}).get("id", ""))
    if not sender_id or sender_id == "unknown":
        return
    message = event.get("message") or {}
    text = message.get("text")
    if not text or message.get("is_echo") or message.get("is_deleted"):
        return
    text = str(text)[:3000]
    notify_message(platform, sender_id, text)
    reply = generate_ai_reply(text)
    sent = send_meta_reply(sender_id, reply)
    if not sent:
        send_telegram_notice(
            "⚠️ Автоответ не отправлен в соцсеть. Проверьте токен и разрешения Meta.\n"
            f"Платформа: {platform}\nID: {sender_id}\nОтвет для проверки: {reply[:1200]}"
        )


def process_comment_change(change: dict[str, Any], platform: str) -> None:
    value = change.get("value") or {}
    field = str(change.get("field", ""))
    if field not in {"comments", "feed"}:
        return
    text = value.get("text") or value.get("message") or ""
    from_data = value.get("from") or {}
    author = from_data.get("name") or "не указан"
    author_id = from_data.get("id") or "не указан"
    post_id = value.get("media_id") or value.get("post_id") or value.get("id") or "не указан"
    send_telegram_notice(
        "💬 Новый комментарий/событие публикации\n"
        f"Платформа: {platform}\nАвтор: {author}\nID автора: {author_id}\n"
        f"Текст: {str(text)[:1600]}\nID публикации/события: {post_id}\n"
        f"Заявки: {TELEGRAM_BOT_URL}"
    )


@app.post("/webhook")
def receive_meta_webhook():
    raw_body = request.get_data(cache=True)
    if not valid_meta_signature(raw_body):
        return "Invalid signature", 403

    payload = request.get_json(silent=True) or {}
    obj = str(payload.get("object", "unknown"))
    platform = "Instagram" if obj == "instagram" else "Facebook"
    try:
        for entry in payload.get("entry", []):
            for event in entry.get("messaging", []):
                process_messaging_event(event, platform)
            for change in entry.get("changes", []):
                process_comment_change(change, platform)
    except Exception:
        logging.exception("Could not process Meta webhook event")
    return "EVENT_RECEIVED", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "10000")))
