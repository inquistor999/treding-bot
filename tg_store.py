"""Telegram'da login qilgan chatlar ro'yxati (faylda saqlanadi)."""
import json
import os

import config as C


def authorized():
    try:
        with open(C.TG_AUTH_FILE, encoding="utf-8") as f:
            return set(json.load(f))
    except (OSError, ValueError):
        return set()


def add(chat_id):
    ids = authorized() | {int(chat_id)}
    with open(C.TG_AUTH_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(ids), f)


def is_authorized(chat_id):
    return int(chat_id) in authorized()
