# users.py — VK Teams пользователи и команды (email как userId / chatId)
TEAMS = {
    1: {
        "team_name": "Отдел развития цифровых каналов и сервисов",
        "tag": "Daily",
        "members": {
            "vostrikovkk@sovcombank.ru": "Кирилл Востриков",
        },
        "managers": ["vostrikovkk@sovcombank.ru","maslenikea@sovcombank.ru"],
    },
    2: {
        "team_name": "Отдел бизнес-анализа операций на финансовых рынках",
        "tag": "Daily",
        "members": {
            "baroninap@sovcombank.ru": "Антон Баронин",
        },
        "managers": ["vostrikovkk@sovcombank.ru","chalikea@sovcombank.ru"],
    },
    3: {
        "team_name": "Отдел бизнес-анализа брокерских операций",
        "tag": "Weekly",
        "members": {
            "voschenkovis@sovcombank.ru": "Илья Вощенков",
        },
        "managers": ["vostrikovkk@sovcombank.ru","ochkinav@sovcombank.ru"],
    },
}

# Плоский словарь: userId -> ФИО
USERS = {}
for t in TEAMS.values():
    USERS.update(t["members"])