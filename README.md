# Мини-учёт оплат учебного центра

FastAPI + SQLite, веб-страница для телефона (вариант Б). Суммы — целые числа (в сумах).

## Запуск с нуля

```bash
git clone <repo-url> && cd ecomdev-payments
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app:app --reload
```

- Веб-страница: http://localhost:8000/
- Swagger с описанием API: http://localhost:8000/docs
- БД (`payments.db`) создаётся автоматически; путь меняется переменной `DB_PATH`.
- Тесты: `pytest`

## API

| Метод | Путь | Что делает |
|---|---|---|
| POST | `/students` | создать ученика `{name, phone, group, monthly_fee}` |
| GET | `/students` | список |
| GET | `/students/{id}` | один ученик |
| PUT | `/students/{id}` | изменить |
| DELETE | `/students/{id}` | удалить (его оплаты удаляются каскадом) |
| POST | `/payments` | добавить оплату `{student_id, amount, paid_at?}` (дата по умолчанию — сегодня) |
| GET | `/students/{id}/payments` | оплаты ученика |
| GET | `/debtors?month=YYYY-MM` | у кого сумма оплат за месяц меньше месячной; поля `paid`, `debt` |

Пример:
```bash
curl -X POST localhost:8000/students -H 'Content-Type: application/json' \
  -d '{"name":"Али","phone":"+998901234567","group":"IELTS","monthly_fee":1000000}'
curl 'localhost:8000/debtors?month=2026-10'
```

Оплата относится к месяцу по своей дате. Переплата одного месяца на следующий не переносится.

## Что улучшить, будь ещё неделя

1. Авторизация (сейчас API открыт всем) и роли: администратор / преподаватель.
2. Учёт переплат и долгов прошлых месяцев (баланс нарастающим итогом), а не только разовый месяц.
3. Миграции (Alembic) и PostgreSQL вместо ручного `CREATE TABLE` на SQLite; пагинация списков.
4. Telegram-бот поверх того же API (`/debt`, `/pay`) и напоминания должникам.
5. Редактирование и удаление оплат, история изменений, экспорт в Excel; больше тестов, CI и Docker.

## Не сделано

Telegram-бот (выбран вариант Б), авторизация, удаление/правка оплат, Docker.
