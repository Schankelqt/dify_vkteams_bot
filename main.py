import asyncio
import logging
import os
import re
import json
import hashlib
from datetime import date
from urllib.parse import urlsplit
from dotenv import load_dotenv
import requests
from transliterate import translit

from vk_teams_async_bot.bot import Bot
from vk_teams_async_bot.events import Event
from vk_teams_async_bot.handler import CommandHandler, MessageHandler
from vk_teams_async_bot.filter import Filter

from users import TEAMS, USERS
from pyrus_client import upload_json_to_task

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

conversation_ids: dict[str, str] = {}
last_date: dict[str, str] = {}

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
    for team_id, team_data in TEAMS.items():
        if user_key in team_data.get("members", {}):
            return team_id
    return None

def determine_tag(user_key: str) -> str:
    team_id = find_team_id_vk(user_key)
    if team_id is None:
        return "daily"
    team = TEAMS.get(team_id, {})
    tag = team.get("tag", "daily").lower()
    weekday = date.today().weekday()
    if tag == "weekly":
        return "weekly"
    elif tag == "daily":
        return "friday" if weekday == 0 else "daily"
    return "daily"

def clean_summary(answer_text: str) -> str:
    lines = (answer_text or "").splitlines()
    for i, line in enumerate(lines):
        if "sum" in line.lower():
            return "\n".join(lines[i+1:]).strip()
    return (answer_text or "").strip()

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

def dify_send_message(user_key: str, text: str, conversation_id: str | None = None, tag: str | None = None):
    payload = {
        "inputs": {"tag": tag or "daily"},
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

def build_individual_report(user_key: str, summary: str, tag: str):
    today = date.today().isoformat()
    team_id = find_team_id_vk(user_key)
    team = TEAMS.get(team_id, {})
    full_name = USERS.get(user_key, "Неизвестный Пользователь")
    first, last = (full_name.split() + ["Unknown", "Unknown"])[:2]

    # Транслитерация
    first_latin = translit(first, 'ru', reversed=True)
    last_latin = translit(last, 'ru', reversed=True)

    file_name = f"{tag.capitalize()}_Report_{first_latin}_{last_latin}_{today}.json"

    report = {
        "version": "1.0",
        "report_date_utc": today,
        "source": {
            "bot": "meetings_dify_bot",
            "tag": tag
        },
        "teams": [
            {
                "team_name": team.get("team_name"),
                "tag": tag,
                "managers": team.get("managers", []),
                "members": [
                    {
                        "e-mail": user_key,
                        "full_name": full_name,
                        "summary": {
                            "text": summary
                        }
                    }
                ]
            }
        ]
    }

    return report, file_name

async def on_message(event: Event, bot: Bot):
    chat_id = getattr(event.chat, "chatId", None)
    from_id = getattr(event.from_, "userId", None) if hasattr(event, "from_") else None
    user_text = getattr(event, "text", "") or ""

    user_key = from_id or chat_id
    if not user_key:
        logger.warning("No user_key (chatId/from.userId) — skip")
        return

    logger.info(f"Incoming VK Teams message from {user_key}: {user_text}")

    today_str = date.today().isoformat()
    if last_date.get(user_key) != today_str:
        conversation_ids.pop(user_key, None)
        last_date[user_key] = today_str
        logger.info(f"[Dify] Новый день для {user_key} — сброшен conversation_id")

    tag = determine_tag(user_key)
    user_text_tagged = f"Тег: {tag}\n{user_text}"

    conv_id = conversation_ids.get(user_key)
    if not conv_id:
        conv_id = dify_get_conversation_id(user_key)
        if conv_id:
            conversation_ids[user_key] = conv_id

    resp = dify_send_message(user_key, user_text_tagged, conv_id, tag=tag)

    if resp is not None and resp.status_code == 400:
        logger.warning(f"[Dify] 400 error — retrying without conversation_id for {user_key}")
        resp = dify_send_message(user_key, user_text_tagged, None, tag=tag)

    if resp is not None and resp.ok:
        body = resp.json()
        answer_text = body.get("answer", "") or ""
        new_conv_id = body.get("conversation_id")
        if new_conv_id:
            conversation_ids[user_key] = new_conv_id

        if is_confirmation(user_text) and ("sum" in answer_text.lower()):
            summary = clean_summary(answer_text)

            try:
                with open("answers.json", "r", encoding="utf-8") as f:
                    answers = json.load(f)
            except Exception:
                answers = {}

            answers[user_key] = {
                "name": USERS.get(user_key, "Неизвестный"),
                "summary": summary
            }

            try:
                with open("answers.json", "w", encoding="utf-8") as f:
                    json.dump(answers, f, ensure_ascii=False, indent=2)
                logger.info(f"[FILE] answers.json обновлён")
            except Exception as e:
                logger.error(f"[FILE] write error: {e}")

            try:
                payload, file_name = build_individual_report(user_key, summary, tag)
                upload_json_to_task(payload, file_name)
                logger.info(f"[PYRUS] Файл {file_name} отправлен в Pyrus")
            except Exception as e:
                logger.error(f"[PYRUS] Ошибка загрузки отчёта в Pyrus: {e}")

            reply = "✅ Спасибо! Отчёт сохранён."
        else:
            reply = answer_text
    else:
        reply = "⚠️ Ошибка при обращении к Dify"

    try:
        await bot.send_text(chat_id=chat_id, text=reply)
    except Exception as e:
        logger.error(f"[VK] send_text error: {e}")

async def main():
    bot = Bot(bot_token=VK_TEAMS_TOKEN, url=VK_TEAMS_API_BASE)
    bot.dispatcher.add_handler(CommandHandler(callback=on_message, filters=Filter.command("/start")))
    bot.dispatcher.add_handler(MessageHandler(callback=on_message))
    logger.info("Start polling…")
    await bot.start_polling()

if __name__ == "__main__":
    asyncio.run(main())