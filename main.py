# main.py
import asyncio
import logging
import os
import re
import json
import hashlib
from urllib.parse import urlsplit
from dotenv import load_dotenv
import requests
from vk_teams_async_bot.bot import Bot
from vk_teams_async_bot.events import Event
from vk_teams_async_bot.handler import CommandHandler, MessageHandler
from vk_teams_async_bot.filter import Filter
from users import TEAMS, USERS

# ---------- Логирование ----------
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("vk_teams_main")

# ---------- Переменные окружения ----------
load_dotenv()

def _env(name: str, required: bool = True) -> str:
    val = (os.getenv(name) or "").strip()
    if required and not val:
        raise RuntimeError(f"ENV {name} is empty")
    return val

VK_TEAMS_TOKEN = _env("VK_TEAMS_TOKEN")
_raw_base = _env("VK_TEAMS_API_BASE")
_s = urlsplit(_raw_base)
VK_TEAMS_API_BASE = f"{_s.scheme}://{_s.netloc}"
if VK_TEAMS_API_BASE != _raw_base:
    logger.warning(f"VK_TEAMS_API_BASE normalized: {_raw_base!r} -> {VK_TEAMS_API_BASE!r}")

DIFY_API_KEY = _env("DIFY_API_KEY")
DIFY_API_URL = _env("DIFY_API_URL").rstrip("/")
logger.info(f"[Dify] base url = {DIFY_API_URL}")

DIFY_HEADERS = {
    "Authorization": f"Bearer {DIFY_API_KEY}",
    "Content-Type": "application/json",
}

# ---------- Поддержка ключей и формата ----------
conversation_ids: dict[str, str] = {}

CONFIRMATION_PHRASES = {
    "да", "да все верно", "да, все верно", "все верно", "всё верно",
    "подтверждаю", "подтверждаю все", "подтверждаю вариант",
    "все так", "всё так", "ок", "окей", "ага", "точно", "верно",
    "готов", "готова", "готово", "да, подтверждаю", "да, отправляй",
    "да, можно отправлять", "все правильно", "всё правильно",
    "абсолютно", "правильно", "так и есть", "да-да", "все супер",
    "всё супер", "супер", "хорошо", "отлично", "всё четко", "все четко",
    "четко", "ясно"
}
CONFIRM_STRIP_RE = re.compile(r"[^\w\sёЁ]+", re.UNICODE)

def normalize_confirmation(s: str) -> str:
    s = (s or "").strip().lower()
    s = s.replace("ё", "е")
    s = CONFIRM_STRIP_RE.sub("", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def is_confirmation(text: str) -> bool:
    return normalize_confirmation(text) in CONFIRMATION_PHRASES

def to_numeric_id(user_key: str) -> int:
    h = hashlib.sha1(user_key.encode("utf-8")).digest()
    return int.from_bytes(h[:8], "big", signed=False)

def find_team_id_vk(user_key: str) -> int | None:
    try:
        for team_id, team_data in TEAMS.items():
            members = team_data.get("members", {})
            if user_key in members or to_numeric_id(user_key) in members:
                return team_id
    except Exception:
        pass
    return None

def clean_summary(answer_text: str) -> str:
    lines = (answer_text or "").splitlines()
    for i, line in enumerate(lines):
        if "sum" in line.lower():
            return "\n".join(lines[i+1:]).strip()
    return (answer_text or "").strip()

# ---------- Dify API ----------
def dify_get_conversation_id(user_key: str) -> str | None:
    url = f"{DIFY_API_URL}/conversations"
    try:
        resp = requests.get(url, headers=DIFY_HEADERS, params={"user": user_key}, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        logger.info(f"[Dify] get_conversation_id for {user_key}: {data}")
        items = data.get("data") or []
        if items:
            return items[0]["id"]
    except Exception as e:
        logger.error(f"[Dify] get_conversation_id error for {user_key}: {e}")
    return None

def dify_send_message(user_key: str, text: str, conversation_id: str | None = None):
    payload = {
        "inputs": {},
        "query": text,
        "response_mode": "blocking",
        "user": user_key,
    }
    if conversation_id:
        payload["conversation_id"] = conversation_id
    url = f"{DIFY_API_URL}/chat-messages"
    resp = requests.post(url, headers=DIFY_HEADERS, json=payload, timeout=60)
    logger.info(f"[Dify] status={resp.status_code} body={resp.text[:2000]}")
    return resp

# ---------- Обработка сообщений ----------
async def on_message(event: Event, bot: Bot):
    chat_id = getattr(event.chat, "chatId", None)
    from_id = getattr(event.from_, "userId", None) if hasattr(event, "from_") else None
    first_name = getattr(event.from_, "firstName", None)
    last_name = getattr(event.from_, "lastName", None)
    user_text = getattr(event, "text", "") or ""

    user_key = from_id or chat_id
    if not user_key:
        logger.warning("No user_key (chatId/from.userId) — skip")
        return

    logger.info(f"Incoming VK Teams message from {user_key}: {user_text}")

    conv_id = conversation_ids.get(user_key)
    if not conv_id:
        conv_id = dify_get_conversation_id(user_key)
        if conv_id:
            conversation_ids[user_key] = conv_id

    # Первый вызов — с conv_id
    resp = dify_send_message(user_key, user_text, conv_id)

    # Если ошибка 400 → fallback без conv_id
    if resp is not None and resp.status_code == 400:
        logger.warning(f"[Dify] 400 error — retrying without conversation_id for {user_key}")
        resp = dify_send_message(user_key, user_text, None)

    # Обработка ответа
    if resp is not None and resp.ok:
        body = resp.json()
        answer_text = body.get("answer", "") or ""
        new_conv_id = body.get("conversation_id")

        if new_conv_id:
            conversation_ids[user_key] = new_conv_id  # обновляем

        if is_confirmation(user_text) and ("sum" in answer_text.lower()):
            summary = clean_summary(answer_text)
            first_clean = first_name.split()[0] if first_name else ""
            display_name = f"{first_clean} {last_name or ''}".strip() or "Неизвестный"

            try:
                with open("answers.json", "r", encoding="utf-8") as f:
                    try:
                        answers = json.load(f)
                    except json.JSONDecodeError:
                        logger.warning("[FILE] answers.json пустой или повреждён — пересоздаём")
                        answers = {}
            except FileNotFoundError:
                answers = {}

            answers[user_key] = {
                "name": display_name,
                "summary": summary
            }

            try:
                with open("answers.json", "w", encoding="utf-8") as f:
                    json.dump(answers, f, ensure_ascii=False, indent=2)
                logger.info(f"[FILE] answers.json успешно сохранён в {os.path.abspath('answers.json')}")
            except Exception as e:
                logger.error(f"[FILE] answers.json write error: {e}")

            reply = "✅ Спасибо! Отчёт сохранён."
        else:
            reply = answer_text
    else:
        reply = "⚠️ Ошибка при обращении к Dify"

    try:
        await bot.send_text(chat_id=chat_id, text=reply)
    except Exception as e:
        logger.error(f"[VK] send_text error: {e}")

# ---------- Запуск бота ----------
async def main():
    bot = Bot(bot_token=VK_TEAMS_TOKEN, url=VK_TEAMS_API_BASE)
    bot.dispatcher.add_handler(CommandHandler(callback=on_message, filters=Filter.command("/start")))
    bot.dispatcher.add_handler(MessageHandler(callback=on_message))
    logger.info("Start polling…")
    await bot.start_polling()

if __name__ == "__main__":
    asyncio.run(main())