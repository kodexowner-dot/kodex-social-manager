# KODEX AI MANAGER — Facebook + Instagram

A separate starter project for a Python webhook receiver. It does not modify the existing Telegram bot or its Render service.

## Important
This is a starter, not a finished Meta integration. To receive real Facebook Page or Instagram messages, configure a Meta developer app, required products/permissions, webhook fields, and the relevant Page/Instagram account. Meta permissions and API rules apply. Do not send unsolicited messages or attempt to automate unsupported events.

## Deploy to Render
1. Push these files to a new GitHub repository named `kodex-social-manager`.
2. In Render, create a **new** Web Service and select this repository. Do not edit the old service.
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn app:app`
5. Add environment variables in Render:
   - `META_VERIFY_TOKEN`: create your own long random verification phrase.
   - `TELEGRAM_BOT_TOKEN`: token for the Telegram bot that should receive notifications.
   - `TELEGRAM_CHAT_ID`: Telegram chat ID for the recipient.
6. Open the service URL. It should return JSON with status `running`.
7. In Meta Webhooks, use `https://YOUR-RENDER-SERVICE.onrender.com/webhook` as the callback URL and use the same `META_VERIFY_TOKEN`.

## Security
Never put tokens in code or commit them to GitHub. Store them only as Render environment variables. Before production, add Meta webhook signature validation and implement the specific supported event schema for your subscribed products.
