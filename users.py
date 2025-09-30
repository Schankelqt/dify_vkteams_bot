# users.py — VK Teams пользователи и команды (email как userId / chatId)
TEAMS = {
    1: {
        "team_name": "Отдел развития цифровых каналов и сервисов",
        "tag": "Daily",
        "members": {
            "vostrikovkk@sovcombank.ru": "Кирилл Востриков",
            "moiseenkovd@sovcombank.ru": "Виктория Моисеенко",
            "zaitsevav4@sovcombank.ru": "Александр Зайцев",
            "voronkovats@sovcombank.ru": "Татьяна Воронкова",
            "goloschapovana@sovcombank.ru": "Наталья Голощапова",
            "dmitrievskayamn@sovcombank.ru": "Марьяна Попова",
            "khvana@sovcombank.ru": "Алексей Хван",
            "karimovam1@sovcombank.ru": "Айрат Каримов",
        },
        "managers": ["vostrikovkk@sovcombank.ru","maslenikea@sovcombank.ru"],
    },
    2: {
        "team_name": "Отдел бизнес-анализа операций на финансовых рынках",
        "tag": "Daily",
        "members": {
            "malyutinda@sovcombank.ru": "Дмитрий Малютин",
            "baroninap@sovcombank.ru": "Антон Баронин",
            "chasovaa@sovcombank.ru": "Андрей Часов",
            "rahmankulovrk@sovcombank.ru": "Радмир Рахманкулов",
        },
        "managers": ["vostrikovkk@sovcombank.ru","chalikea@sovcombank.ru"],
    },
    3: {
        "team_name": "Отдел бизнес-анализа брокерских операций",
        "tag": "Weekly",
        "members": {
            "vasilevaea10@sovcombank.ru": "Екатерина Васильева",
            "eremindv@sovcombank.ru": "Денис Еремин",
            "provotorovaig@sovcombank.ru": "Ирина Провоторова",
            "plotnikovaes@sovcombank.ru": "Екатерина Плотникова",
            "voschenkovis@sovcombank.ru": "Илья Вощенков",
            "akinshinany@sovcombank.ru": "Наталья Акиньшина",
            "yurkovkv@sovcombank.ru": "Константин Юрков",
            "korepanovaev@sovcombank.ru": "Екатерина Бахур",
        },
        "managers": ["vostrikovkk@sovcombank.ru","ochkinav@sovcombank.ru"],
    },
    4: {
        "team_name": "Отдел аналитики данных и неторговых операций",
        "tag": "Weekly",
        "members": {
            "vostrikovkk@sovcombank.ru": "Кирилл Востриков", #+       
        },
        "managers": ["vostrikovkk@sovcombank.ru",],
    },
}

# Плоский словарь: userId -> ФИО
USERS = {}
for t in TEAMS.values():
    USERS.update(t["members"])