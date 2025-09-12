# pyrus_client.py

import os
import requests
import time
from dotenv import load_dotenv

# Загрузка .env
load_dotenv()

# Прокси URL
PROXY_UPLOAD_URL = os.getenv("PYRUS_UPLOAD_PROXY_URL")

# Разные задачи
TASK_ID_DAILY = os.getenv("PYRUS_TARGET_TASK_ID_DAILY")
TASK_ID_WEEKLY = os.getenv("PYRUS_TARGET_TASK_ID_WEEKLY")

if not PROXY_UPLOAD_URL or not TASK_ID_DAILY or not TASK_ID_WEEKLY:
    raise RuntimeError(
        "Нужно задать PYRUS_UPLOAD_PROXY_URL, PYRUS_TARGET_TASK_ID_DAILY и PYRUS_TARGET_TASK_ID_WEEKLY в .env"
    )


def upload_json_to_task(json_data: dict, file_name: str, team_id: int):
    """
    Загружает JSON-отчёт в Pyrus через прокси эндпоинт.
    Для команд 1–2 (daily) → Daily задача.
    Для команды 3 (weekly) → Weekly задача.
    При неудаче (например, timeout) пытается снова каждые 5 минут до успеха.
    """

    if team_id == 3:
        task_id = int(TASK_ID_WEEKLY)
    else:
        task_id = int(TASK_ID_DAILY)

    payload = {
        "filename": file_name,
        "task_id": task_id,
        "body": json_data
    }

    attempt = 1
    while True:
        print(f"📤 [{attempt}] Отправка {file_name} в Pyrus (задача {task_id})…")
        try:
            resp = requests.post(PROXY_UPLOAD_URL, json=payload, timeout=90)
            print(f"🔁 [{attempt}] Статус: {resp.status_code}")
            if resp.ok:
                print("✅ Успешно загружено!")
                break
            else:
                print(f"⚠️ [{attempt}] Ошибка: {resp.text[:1000]}")
        except requests.RequestException as e:
            print(f"❌ [{attempt}] Ошибка при загрузке: {e}")

        attempt += 1
        print("⏳ Ожидание 5 минут перед повтором...")
        time.sleep(5 * 60)  # 5 минут