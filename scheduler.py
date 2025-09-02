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


def load_answers() -> dict:
    try:
        with open("answers.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def build_report(team_id: int, date_str: str) -> str:
    answers = load_answers()
    team = TEAMS.get(team_id)
    report_lines = [f"📝 Отчёт по команде «{team['team_name']}» за {date_str}"]
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
        report_lines.append(f"\n👤 *{name}*\n{summary}")
        any_found = True
    if not any_found:
        report_lines.append("\n(Нет ответов от участников)")
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
    report_text = build_report(team_id, date_str)
    bot = Bot(bot_token=VK_TEAMS_TOKEN, url=VK_TEAMS_API_BASE)
    for manager_id in TEAMS[team_id].get("managers", []):
        try:
            await send_long_text(bot, chat_id=manager_id, text=report_text)
        except Exception as e:
            print(f"⚠️ Ошибка при отправке отчёта → {manager_id}: {e}")


# Обёртки для schedule (так как он не async)
def job_send_questions(team_id: int, key: str):
    asyncio.run(send_questions(team_id, key))


def job_send_report(team_id: int):
    today = datetime.now(MSK).strftime("%Y-%m-%d")
    asyncio.run(send_report(team_id, today))


# Расписание для всех команд (время — MSK)
schedule.every().monday.at("09:00").do(job_send_questions, team_id=1, key="daily_start")
schedule.every().tuesday.at("09:00").do(job_send_questions, team_id=1, key="daily_regular")
schedule.every().wednesday.at("09:00").do(job_send_questions, team_id=1, key="daily_regular")
schedule.every().thursday.at("09:00").do(job_send_questions, team_id=1, key="daily_regular")
schedule.every().friday.at("09:00").do(job_send_questions, team_id=1, key="daily_regular")

schedule.every().monday.at("09:30").do(job_send_report, team_id=1)
schedule.every().tuesday.at("09:30").do(job_send_report, team_id=1)
schedule.every().wednesday.at("09:30").do(job_send_report, team_id=1)
schedule.every().thursday.at("09:30").do(job_send_report, team_id=1)
schedule.every().friday.at("09:30").do(job_send_report, team_id=1)

schedule.every().monday.at("11:00").do(job_send_report, team_id=2)
schedule.every().wednesday.at("11:00").do(job_send_report, team_id=2)
schedule.every().friday.at("11:00").do(job_send_report, team_id=2)

schedule.every().monday.at("09:00").do(job_send_questions, team_id=2, key="daily_start")
schedule.every().wednesday.at("09:00").do(job_send_questions, team_id=2, key="daily_regular")
schedule.every().friday.at("09:00").do(job_send_questions, team_id=2, key="daily_regular")

schedule.every().wednesday.at("15:00").do(job_send_questions, team_id=3, key="weekly")
schedule.every().thursday.at("10:00").do(job_send_report, team_id=3)

print("🕒 Планировщик запущен. Ожидание задач...")
while True:
    schedule.run_pending()
    time.sleep(30)