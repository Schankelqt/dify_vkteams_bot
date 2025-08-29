import os
import asyncio
import json
from datetime import datetime
from pathlib import Path
import pytz
from dotenv import load_dotenv
from vk_teams_async_bot.bot import Bot
from users import USERS, TEAMS
from pyrus_client import upload_json_to_task  # новый импорт

# Загрузка переменных
load_dotenv()
VK_TEAMS_TOKEN = os.getenv("VK_TEAMS_TOKEN")
VK_TEAMS_API_BASE = os.getenv("VK_TEAMS_API_BASE")

# Пути
ANSWERS_FILE = "answers.json"
QUESTIONS_LOG = "last_questions_log.json"
REPORTS_LOG = "last_reports_log.json"

# Время
MSK = pytz.timezone("Europe/Moscow")

# Вопросы
QUESTION_SETS = {
    "daily_start": [
        "Что делал в пятницу?",
        "Что планируешь сегодня?",
        "Есть ли блокеры?"
    ],
    "daily_regular": [
        "Что ты сделал вчера?",
        "Что планируешь сегодня?",
        "Есть ли блокеры?"
    ],
    "weekly": [
        "Что ты делал на этой неделе?",
        "Что планируешь делать на следующей?",
        "Есть ли блокеры?"
    ]
}

def is_time(now: datetime, target: str) -> bool:
    return now.strftime("%H:%M") == target

def load_json(path: str) -> dict:
    if Path(path).exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_json(path: str, data: dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def was_sent(path: str, team_id: int, key: str, date_str: str) -> bool:
    data = load_json(path)
    return data.get(str(team_id), {}).get(key) == date_str

def mark_sent(path: str, team_id: int, key: str, date_str: str):
    data = load_json(path)
    data.setdefault(str(team_id), {})[key] = date_str
    save_json(path, data)

# Рассылка вопросов
async def send_questions(bot: Bot, team_id: int, question_key: str):
    team = TEAMS.get(team_id)
    if not team:
        return
    questions = QUESTION_SETS.get(question_key)
    if not questions:
        return
    message = "\n".join(questions)
    print(f"\U0001F4E8 Команда {team_id}: рассылаем вопросы ({question_key})...")
    for user_id in team.get("members", {}):
        try:
            await bot.send_text(chat_id=user_id, text=message)
            await asyncio.sleep(1)
        except Exception as e:
            print(f"⚠️ Ошибка при отправке → {user_id}: {e}")

# Генерация отчёта (для человека)
def build_report(team_id: int, date_str: str) -> str:
    answers = load_json(ANSWERS_FILE)
    team = TEAMS.get(team_id)
    report_lines = [f"\U0001F4DD Отчёт по команде «{team['team_name']}» за {date_str}"]

    any_found = False
    for user_id in team.get("members", {}):
        entry = answers.get(user_id)
        if not entry:
            continue
        summary = entry.get("summary")
        if not summary:
            continue
        name_parts = entry.get("name", user_id).split()
        name = name_parts[0] + " " + name_parts[-1]
        report_lines.append(f"\n\U0001F464 *{name}*\n{summary}")
        any_found = True

    if not any_found:
        report_lines.append("\n(Нет ответов от участников)")
    return "\n".join(report_lines)

# JSON-отчёт для Pyrus
def build_report_json(team_id: int, date_str: str) -> dict:
    answers = load_json(ANSWERS_FILE)
    team = TEAMS.get(team_id)
    tag = team.get("tag", "Daily")

    members_data = []
    for user_id, full_name in team.get("members", {}).items():
        entry = answers.get(user_id)
        if not entry:
            continue
        summary = entry.get("summary")
        if not summary:
            continue
        members_data.append({
            "e-mail": user_id,
            "full_name": full_name,
            "status": "responded",
            "summary": {"text": summary}
        })

    return {
        "version": "1.0",
        "report_date_utc": date_str,
        "source": {
            "bot": "meetings_dify_bot",
            "tag": tag
        },
        "teams": [
            {
                "team_id": team_id,
                "team_name": team.get("team_name"),
                "tag": tag,
                "managers": team.get("managers", []),
                "members_total": len(team.get("members", {})),
                "members_responded": len(members_data),
                "members": members_data
            }
        ]
    }

# Отправка отчёта менеджерам + выгрузка в Pyrus
async def send_report(bot: Bot, team_id: int, date_str: str):
    if was_sent(REPORTS_LOG, team_id, "report", date_str):
        return
    report_text = build_report(team_id, date_str)
    for manager_id in TEAMS[team_id].get("managers", []):
        try:
            await bot.send_text(chat_id=manager_id, text=report_text)
            await asyncio.sleep(1)
        except Exception as e:
            print(f"⚠️ Ошибка при отправке отчёта → {manager_id}: {e}")

    # Загрузка json в Pyrus
    try:
        json_data = build_report_json(team_id, date_str)
        upload_json_to_task(json_data, report_date=date_str)
    except Exception as e:
        print(f"[Pyrus] Ошибка при загрузке json: {e}")

    mark_sent(REPORTS_LOG, team_id, "report", date_str)

# Планировщик
async def scheduler_loop():
    bot = Bot(bot_token=VK_TEAMS_TOKEN, url=VK_TEAMS_API_BASE)
    print("🕒 Планировщик запущен")
    while True:
        now = datetime.now(MSK)
        today = now.strftime("%Y-%m-%d")
        wd = now.weekday()

        # Команда 1
        if wd == 0 and is_time(now, "09:00") and not was_sent(QUESTIONS_LOG, 1, "daily_start", today):
            await send_questions(bot, 1, "daily_start")
            mark_sent(QUESTIONS_LOG, 1, "daily_start", today)
        elif wd in {1, 2, 3, 4} and is_time(now, "15:22") and not was_sent(QUESTIONS_LOG, 1, "daily_regular", today):
            await send_questions(bot, 1, "daily_regular")
            mark_sent(QUESTIONS_LOG, 1, "daily_regular", today)
        if wd in {0, 1, 2, 3, 4} and is_time(now, "15:24"):
            await send_report(bot, 1, today)

        # Команда 2
        if wd == 0 and is_time(now, "09:00") and not was_sent(QUESTIONS_LOG, 2, "daily_start", today):
            await send_questions(bot, 2, "daily_start")
            mark_sent(QUESTIONS_LOG, 2, "daily_start", today)
        elif wd in {2, 4} and is_time(now, "15:22") and not was_sent(QUESTIONS_LOG, 2, "daily_regular", today):
            await send_questions(bot, 2, "daily_regular")
            mark_sent(QUESTIONS_LOG, 2, "daily_regular", today)
        if wd in {0, 2, 4} and is_time(now, "15:24"):
            await send_report(bot, 2, today)

        # Команда 3
        if wd == 2 and is_time(now, "15:00") and not was_sent(QUESTIONS_LOG, 3, "weekly", today):
            await send_questions(bot, 3, "weekly")
            mark_sent(QUESTIONS_LOG, 3, "weekly", today)
        if wd == 3 and is_time(now, "10:00"):
            await send_report(bot, 3, today)

        await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(scheduler_loop())
