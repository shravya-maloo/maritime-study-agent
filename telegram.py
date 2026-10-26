"""Tiny wrapper around the Telegram Bot API (https://core.telegram.org/bots/api).

Every call is a plain HTTPS request to api.telegram.org with your bot token.
"""

import os

import httpx


def _url(method):
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    return f"https://api.telegram.org/bot{token}/{method}"


def send(chat_id, text):
    httpx.post(_url("sendMessage"), json={"chat_id": chat_id, "text": text}, timeout=15)


def download_file(file_id):
    """Download a file someone sent the bot (like a .md of notes)."""
    info = httpx.get(_url("getFile"), params={"file_id": file_id}, timeout=15).json()
    path = info["result"]["file_path"]
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    return httpx.get(f"https://api.telegram.org/file/bot{token}/{path}", timeout=30).content


def set_webhook(url, secret):
    """Tell Telegram to forward every new message to our /telegram endpoint."""
    response = httpx.post(
        _url("setWebhook"), json={"url": url, "secret_token": secret}, timeout=15
    )
    return response.json()


def get_updates(offset):
    """Fetch messages sent since `offset` (used only in poll mode)."""
    response = httpx.get(_url("getUpdates"), params={"offset": offset}, timeout=15)
    return response.json().get("result", [])
