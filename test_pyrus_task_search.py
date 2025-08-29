import os
import json
import logging
import requests

# ---------- Логирование ----------
logger = logging.getLogger("pyrus")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

# ---------- .env конфигурация ----------
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# ---------- Параметры из .env ----------
PROXY_API_URL = os.getenv("PYRUS_UPLOAD_PROXY_URL", "https://aimatrix-e8zs.onrender.com/upload_files_pyrus").strip()
TARGET_TASK_ID = int(os.getenv("PYRUS_TARGET_TASK_ID", "0"))

# ---------- Основная функция ----------
def upload_json_to_task(json_data: dict, report_date: str):
    if not TARGET_TASK_ID:
        raise RuntimeError("[Pyrus] ❌ PYRUS_TARGET_TASK_ID не задан")
    if not PROXY_API_URL:
        raise RuntimeError("[Pyrus] ❌ PYRUS_UPLOAD_PROXY_URL не задан")

    filename = f"daily_report_{report_date}.json"

    # Сохраняем файл локально
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)
    logger.info(f"[Pyrus] 📎 Файл сохранён локально: {filename}")

    # Формируем запрос
    payload = {
        "filename": filename,
        "task_id": TARGET_TASK_ID,
        "body": json_data
    }

    logger.info(f"[Pyrus] 🌐 Отправка файла через прокси API: {PROXY_API_URL}")
    try:
        resp = requests.post(PROXY_API_URL, json=payload, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"[Pyrus] ❌ Ошибка отправки через прокси API: {e}, body={getattr(e.response, 'text', '')}")
        raise RuntimeError("[Pyrus] Upload via proxy failed")

    logger.info(f"[Pyrus] ✅ Файл успешно отправлен через API. Статус: {resp.status_code}")