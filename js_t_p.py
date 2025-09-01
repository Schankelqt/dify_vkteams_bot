# test_upload_json.py
import requests

UPLOAD_ENDPOINT = "https://aimatrix-e8zs.onrender.com/upload_files_pyrus"
TASK_ID = 106315912

# Тестовый JSON отчёт
json_body = {
    "version": "1.0",
    "report_date_utc": "2025-09-01",
    "source": {
        "bot": "meetings_dify_bot",
        "tag": "Daily"
    },
    "teams": [
        {
            "team_id": 1,
            "team_name": "Отдел развития цифровых каналов и сервисов",
            "tag": "Daily",
            "managers": [
                "vostrikovkk@sovcombank.ru"
            ],
            "members_total": 1,
            "members_responded": 1,
            "members": [
                {
                    "e-mail": "vostrikovkk@sovcombank.ru",
                    "full_name": "Кирилл Востриков",
                    "status": "responded",
                    "summary": {
                        "text": "Вчера: \n- отрисовал прототип калькулятора\n- синковался с дизайнерами по рисде\n- пошарили бота на команду брокерки\n\nСегодня: \n- Синки с дизайнерами и АйТи по рисде\n- правки по боту для инструкций\n- добавить новую команду в бота daily/weekly\n\nБлокеры: Нет"
                    }
                }
            ]
        }
    ]
}

def main():
    payload = {
        "filename": "daily_report_2025-09-01.json",
        "task_id": TASK_ID,
        "body": json_body
    }

    print(f"📤 Отправка отчёта в задачу {TASK_ID}…")
    try:
        resp = requests.post(UPLOAD_ENDPOINT, json=payload, timeout=30)
        print(f"🔁 Статус: {resp.status_code}")
        print(f"📦 Ответ: {resp.text[:1000]}")
        resp.raise_for_status()
        print("✅ Успешно загружено!")
    except requests.RequestException as e:
        print(f"❌ Ошибка при загрузке: {e}")

if __name__ == "__main__":
    main()