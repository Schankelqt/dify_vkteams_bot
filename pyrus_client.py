# pyrus_client.py

import os
import requests
from dotenv import load_dotenv

# Загрузка .env
load_dotenv()

# Прокси URL для загрузки JSON-файла в задачу Pyrus
PROXY_UPLOAD_URL = os.getenv("PYRUS_UPLOAD_PROXY_URL")  # Пример: https://aimatrix-e8zs.onrender.com/upload_files_pyrus
TASK_ID = os.getenv("PYRUS_TARGET_TASK_ID")  # Пример: 106315912

if not PROXY_UPLOAD_URL or not TASK_ID:
    raise RuntimeError("PYRUS_UPLOAD_PROXY_URL и PYRUS_TARGET_TASK_ID должны быть заданы в .env")

def upload_json_to_task(json_data: dict, file_name: str):
    """
    Загружает JSON-отчёт в Pyrus через прокси эндпоинт
    :param json_data: словарь JSON-отчёта
    :param file_name: имя файла (с расширением .json)
    """
    payload = {
        "filename": file_name,
        "task_id": int(TASK_ID),
        "body": json_data
    }

    print(f"📤 Отправка {file_name} в Pyrus (задача {TASK_ID})…")
    try:
        resp = requests.post(PROXY_UPLOAD_URL, json=payload, timeout=30)
        print(f"🔁 Статус: {resp.status_code}")
        if not resp.ok:
            print(f"⚠️ Ошибка: {resp.text[:1000]}")
        else:
            print("✅ Успешно загружено!")
    except requests.RequestException as e:
        print(f"❌ Ошибка при загрузке: {e}")