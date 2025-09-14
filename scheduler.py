# scheduler.py

import os
import json
import schedule
import time
from datetime import datetime
import pytz
from dotenv import load_dotenv
import asyncio

from vk_teams_async_bot.bot import Bot
from users import USERS, TEAMS

# Загрузка переменных окружения
load_dotenv()
VK_TEAMS_TOKEN = os.getenv("VK_TEAMS_TOKEN")
VK_TEAMS_API_BASE = os.getenv("VK_TEAMS_API_BASE")

# Временная зона
MSK = pytz.timezone("Europe/Moscow")

QUESTION_SETS = {
    "daily_start": [
        "Доброе утро! ☀️\n\n"
        "Пожалуйста, ответьте на 3 вопроса:\n"
        "Что делал в пятницу?",
        "Что планируешь сегодня?",
        "Есть ли блокеры?"
    ],
    "daily_regular": [
        "Доброе утро! ☀️\n\n"
        "Пожалуйста, ответьте на 3 вопроса:\n"
        "Что ты сделал вчера?",
        "Что планируешь сегодня?",
        "Есть ли блокеры?"
    ],
    "weekly": [
        "Привет! ☀️\n\n"
        "Пожалуйста, ответьте на 3 вопроса:\n"
        "Что ты делал на этой неделе?",
        "Что планируешь делать на следующей?",
        "Есть ли блокеры?"
    ]
}

def load_answers() -> dict:
    try:
        with open("answers.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_answers(data: dict):
    with open("answers.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def clean_team_answers(today_str: str, team_id: int):
    """
    Чистим только по members конкретной команды.
    Сохраняем ответы этой команды, которые были даны сегодня.
    Остальные команды не трогаем.
    """
    answers = load_answers()
    team = TEAMS.get(team_id, {})
    members = set(team.get("members", {}).keys())

    updated = {}
    for uid, info in answers.items():
        if uid in members:
            if info.get("date") == today_str:
                updated[uid] = info
        else:
            # не трогаем других сотрудников (другие команды)
            updated[uid] = info

    save_answers(updated)

def build_text_report(team_id: int, date_str: str) -> str:
    answers = load_answers()
    team = TEAMS.get(team_id)
    report_lines = [f"📝 Отчёт по команде «{team['team_name']}» за {date_str}"]

    responded = 0
    total = len(team.get("members", {}))

    for user_id, full_name in team.get("members", {}).items():
        entry = answers.get(user_id)
        summary = entry.get("summary") if entry else "-"
        name = full_name.strip()
        report_lines.append(f"\n👤 *{name}*\n{summary}")
        if entry:
            responded += 1

    report_lines.append(f"\n📊 Отчитались: {responded}/{total}")
    return "\n".join(report_lines)

async def send_long_text(bot: Bot, chat_id: str, text: str, chunk_size: int = 1000):
    chunks = []
    while text:
        part = text[:chunk_size]
        last_nl = part.rfind("\n")
        if last_nl > 0 and len(text) > chunk_size:
            part = text[:last_nl]
        chunks.append(part.strip())
        text = text[len(part):].lstrip()

    for i, part in enumerate(chunks):
        header = f"Часть {i+1}/{len(chunks)}:\n" if len(chunks) > 1 else ""
        try:
            await bot.send_text(chat_id=chat_id, text=header + part)
            await asyncio.sleep(1)
        except Exception as e:
            print(f"⚠️ Ошибка при отправке части {i+1} → {chat_id}: {e}")

async def send_questions(team_id: int, question_key: str):
    team = TEAMS.get(team_id)
    if not team:
        return
    questions = QUESTION_SETS.get(question_key)
    if not questions:
        return
    message = "\n".join(questions)
    print(f"📨 Команда {team_id}: рассылаем вопросы ({question_key})...")
    bot = Bot(bot_token=VK_TEAMS_TOKEN, url=VK_TEAMS_API_BASE)
    for user_id in team.get("members", {}):
        try:
            await send_long_text(bot, chat_id=user_id, text=message)
        except Exception as e:
            print(f"⚠️ Ошибка при отправке → {user_id}: {e}")

async def send_report(team_id: int, date_str: str):
    report_text = build_text_report(team_id, date_str)
    bot = Bot(bot_token=VK_TEAMS_TOKEN, url=VK_TEAMS_API_BASE)
    for manager_id in TEAMS[team_id].get("managers", []):
        try:
            await send_long_text(bot, chat_id=manager_id, text=report_text)
        except Exception as e:
            print(f"⚠️ Ошибка при отправке отчёта → {manager_id}: {e}")

    # После отправки отчёта чистим ответы этой команды
    clean_team_answers(date_str, team_id)

def job_send_questions(team_id: int, key: str):
    asyncio.run(send_questions(team_id, key))

def job_send_report(team_id: int):
    today = datetime.now(MSK).strftime("%Y-%m-%d")
    asyncio.run(send_report(team_id, today))

# --- Расписание ---
# Команда 1 (Daily)
schedule.every().monday.at("09:00").do(job_send_questions, team_id=1, key="daily_start")
schedule.every().tuesday.at("09:00").do(job_send_questions, team_id=1, key="daily_regular")
schedule.every().wednesday.at("09:00").do(job_send_questions, team_id=1, key="daily_regular")
schedule.every().thursday.at("09:00").do(job_send_questions, team_id=1, key="daily_regular")

schedule.every().monday.at("09:30").do(job_send_report, team_id=1)
schedule.every().tuesday.at("09:30").do(job_send_report, team_id=1)
schedule.every().wednesday.at("09:30").do(job_send_report, team_id=1)
schedule.every().thursday.at("09:30").do(job_send_report, team_id=1)

# Команда 2 (Daily)
schedule.every().monday.at("09:00").do(job_send_questions, team_id=2, key="daily_start")
schedule.every().wednesday.at("09:00").do(job_send_questions, team_id=2, key="daily_regular")
schedule.every().friday.at("11:00").do(job_send_questions, team_id=2, key="daily_regular")

schedule.every().monday.at("11:00").do(job_send_report, team_id=2)
schedule.every().wednesday.at("11:00").do(job_send_report, team_id=2)
schedule.every().friday.at("11:00").do(job_send_report, team_id=2)

# Команда 3 (Weekly)
schedule.every().wednesday.at("15:00").do(job_send_questions, team_id=3, key="weekly")
schedule.every().wednesday.at("22:00").do(job_send_report, team_id=3)

print("🕒 Планировщик запущен. Ожидание задач...")
while True:
    schedule.run_pending()
    time.sleep(30)