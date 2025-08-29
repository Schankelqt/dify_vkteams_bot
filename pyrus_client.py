import os
import time
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

# ---------- Загрузка .env ----------
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# ---------- Конфиг из .env ----------
BASE_URL = (os.getenv("PYRUS_BASE_URL") or "").rstrip("/")
PYRUS_LOGIN = os.getenv("PYRUS_LOGIN")
PYRUS_SECURITY_KEY = os.getenv("PYRUS_SECURITY_KEY")
TARGET_TASK_ID = int(os.getenv("PYRUS_TARGET_TASK_ID", "0"))

# ---------- Глобальные переменные токена ----------
_token = ""
_token_exp_ts = 0

# ---------- Авторизация ----------
def _auth_url() -> str:
    return f"{BASE_URL}/auth"

def _headers() -> dict:
    return {
        "Authorization": f"Bearer {_token}" if _token else "",
        "Accept": "application/json",
    }

def _obtain_token() -> None:
    global _token, _token_exp_ts
    if not (PYRUS_LOGIN and PYRUS_SECURITY_KEY):
        raise RuntimeError("PYRUS_LOGIN or PYRUS_SECURITY_KEY not set")
    
    url = _auth_url()
    logger.info(f"[Pyrus] 🔐 Получение токена по адресу: {url}")
    
    try:
        resp = requests.post(url, json={"login": PYRUS_LOGIN, "security_key": PYRUS_SECURITY_KEY}, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        _token = data.get("access_token", "")
        _token_exp_ts = time.time() + 3600
        logger.info(f"[Pyrus] ✅ Токен получен: {_token[:10]}...")
    except requests.RequestException as e:
        logger.error(f"[Pyrus] ❌ Ошибка авторизации: {e}, body={getattr(e.response, 'text', '')}")
        raise

def _ensure_token():
    if not _token or time.time() >= _token_exp_ts:
        _obtain_token()

# ---------- Добавление комментария к задаче ----------
def _add_comment(task_id: int, text: str):
    _ensure_token()
    url = f"{BASE_URL}/tasks/{task_id}/comments"
    headers = _headers()
    payload = {"text": text}
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=15)
        if not resp.ok:
            logger.error(f"[Pyrus] ⚠️ Не удалось добавить комментарий: {resp.status_code}, body={resp.text}")
        else:
            logger.info(f"[Pyrus] 💬 Комментарий добавлен в задачу {task_id}")
    except requests.RequestException as e:
        logger.error(f"[Pyrus] ❌ Ошибка при добавлении комментария: {e}")

# ---------- Загрузка JSON-файла в задачу ----------
def upload_json_to_task(json_data: dict, report_date: str):
    task_id = int(os.getenv("PYRUS_TARGET_TASK_ID") or 0)
    if not task_id:
        raise RuntimeError("[Pyrus] ❌ PYRUS_TARGET_TASK_ID не задан")

    filename = f"daily_report_{report_date}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)

    logger.info(f"[Pyrus] 📎 Файл создан: {filename}")

    _ensure_token()
    url = f"{BASE_URL}/tasks/{task_id}/attachments"
    headers = {"Authorization": f"Bearer {_token}"}
    with open(filename, "rb") as f:
        files = {
            "attachment": (filename, f, "application/json")
        }
        resp = requests.post(url, headers=headers, files=files)

    if not resp.ok:
        logger.error(f"[Pyrus] ❌ Ошибка при загрузке файла: {resp.status_code}, body={resp.text}")
        raise RuntimeError(f"[Pyrus] Upload failed: {resp.status_code}")
    
    logger.info(f"[Pyrus] ✅ JSON-файл успешно загружен в задачу {task_id}")

    # Добавляем комментарий
    _add_comment(task_id, "добавлен файл из бота Daily/Weekly")