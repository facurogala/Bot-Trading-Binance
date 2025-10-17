import os
import time
import json
import requests
import html
from typing import Optional

# Simple notifier for Telegram with retries, backoff, basic HTML escaping and logging.
# Reads TELEGRAM_TOKEN and TELEGRAM_CHAT_ID from env by default.

LOG_PATH = os.getenv("TELEGRAM_LOG_PATH", "telegram.log")


def _log(entry: dict):
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        # best-effort
        pass


def send_telegram(message: str, token: Optional[str] = None, chat_id: Optional[str] = None, max_retries: int = 3, backoff_base: float = 1.0) -> bool:
    """Send a message to Telegram with retries and simple HTML escaping.

    Returns True if sent, False otherwise.
    """
    token = token or os.getenv("TELEGRAM_TOKEN")
    chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        entry = {"ts": time.time(), "status": "no_token", "message": message[:1000]}
        _log(entry)
        print("⚠️ Telegram no configurado (TOKEN/CHAT_ID faltante)")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    # Basic HTML-escape to avoid parse errors
    safe_message = html.escape(message)

    payload = {"chat_id": chat_id, "text": safe_message, "parse_mode": "HTML"}

    attempt = 0
    while attempt < max_retries:
        attempt += 1
        ts = time.time()
        try:
            r = requests.post(url, data=payload, timeout=10)
            entry = {
                "ts": ts,
                "attempt": attempt,
                "status_code": getattr(r, 'status_code', None),
                "response_text": r.text[:200] if hasattr(r, 'text') else None,
                "message": message[:1000]
            }
            _log(entry)

            if r.status_code == 200:
                print("✅ Mensaje enviado a Telegram")
                return True
            # Rate limited -> backoff and retry
            if r.status_code == 429:
                wait = backoff_base * (2 ** (attempt - 1))
                time.sleep(wait)
                continue
            # Bad request possibly due to parse error: try plain text fallback once
            if r.status_code == 400 and attempt == 1:
                try:
                    payload_plain = {"chat_id": chat_id, "text": message, "parse_mode": None}
                    r2 = requests.post(url, data=payload_plain, timeout=8)
                    entry2 = {"ts": time.time(), "attempt": attempt, "status_code": getattr(r2, 'status_code', None), "response_text": getattr(r2, 'text', '')[:200]}
                    _log(entry2)
                    if getattr(r2, 'status_code', None) == 200:
                        print("✅ Mensaje enviado a Telegram (plain)")
                        return True
                except Exception as ex2:
                    _log({"ts": time.time(), "error": repr(ex2)})
            # Other errors -> don't retry aggressively
            break
        except requests.RequestException as e:
            _log({"ts": ts, "attempt": attempt, "error": repr(e), "message": message[:1000]})
            wait = backoff_base * (2 ** (attempt - 1))
            time.sleep(wait)
            continue

    print("⚠️ No se pudo enviar mensaje a Telegram después de reintentos")
    return False
