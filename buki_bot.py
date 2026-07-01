"""
BUKI Demo Bot — пошук та реєстрація репетиторів у Telegram
============================================================

Стек: aiogram 3.x, Python 3.10+, SQLite (модуль sqlite3, без зовнішніх залежностей)

Встановлення:
    pip install aiogram==3.*

Запуск:
    Windows (cmd):      set BOT_TOKEN=ваш_токен_від_@BotFather
    Windows (PowerShell): $env:BOT_TOKEN="ваш_токен"
    Linux/Mac:           export BOT_TOKEN="ваш_токен"

    python buki_bot.py
"""

import asyncio
import logging
import os
import sqlite3
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from background import keep_alive

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN", "8877692551:AAEZNk41FQYDYFZAOjF_HXNsU-10o2mIYoA")
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "buki.db")

# ---------------------------------------------------------------------------
# Довідники
# ---------------------------------------------------------------------------

# Категорії предметів для швидкого вибору
SUBJECT_CATEGORIES = {
    "math": "Математика",
    "physics": "Фізика",
    "chemistry": "Хімія",
    "biology": "Біологія",
    "computer_science": "Інформатика",
}

# Розширений список предметів (повний)
SUBJECTS_FULL = {
    "math": "Математика",
    "english": "Англійська мова",
    "physics": "Фізика",
    "ukrainian": "Українська мова",
    "chemistry": "Хімія",
    "biology": "Біологія",
    "computer_science": "Інформатика",
    "geography": "Географія",
    "history": "Історія України",
    "world_history": "Всесвітня історія",
    "literature": "Українська література",
    "foreign_literature": "Зарубіжна література",
    "law": "Правознавство",
    "economics": "Економіка",
    "logic": "Логіка",
    "psychology": "Психологія",
    "philosophy": "Філософія",
    "polish": "Польська мова",
    "german": "Німецька мова",
    "french": "Французька мова",
    "spanish": "Іспанська мова",
    "italian": "Італійська мова",
}

SUBJECTS = SUBJECTS_FULL

# Основні міста
CITIES = [
    "Київ", "Львів", "Дніпро", "Одеса", "Харків", 
    "Полтава", "Запоріжжя", "Вінниця", "Івано-Франківськ"
]

FORMAT_LABELS = {"online": "Онлайн", "offline": "Офлайн"}

GOAL_LABELS = {
    "exam": "Підготовка до іспитів (НМТ/ЗНО/ДПА)",
    "school": "Шкільна програма",
    "conversation": "Розмовна практика",
}

LEVEL_LABELS = {
    "beginner": "Початковий",
    "intermediate": "Середній",
    "advanced": "Просунутий",
}

# ---------------------------------------------------------------------------
# Робота з базою даних (SQLite)
# ---------------------------------------------------------------------------


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    
    # Таблиця репетиторів
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tutors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            full_name TEXT NOT NULL,
            subjects TEXT NOT NULL,
            levels TEXT,
            formats TEXT NOT NULL,
            city TEXT,
            price INTEGER NOT NULL,
            education TEXT,
            experience_years INTEGER DEFAULT 0,
            about TEXT,
            contact TEXT,
            rating REAL DEFAULT 0,
            reviews_count INTEGER DEFAULT 0,
            verified INTEGER DEFAULT 0,
            status TEXT DEFAULT 'published',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    
    # Таблиця учнів
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE,
            full_name TEXT,
            phone TEXT,
            city TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    
    # Таблиця заявок
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_telegram_id INTEGER,
            tutor_id INTEGER,
            contact TEXT,
            note TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    
    conn.commit()

    count = conn.execute("SELECT COUNT(*) AS c FROM tutors").fetchone()["c"]
    if count == 0:
        seed_tutors(conn)
    conn.close()


def seed_tutors(conn: sqlite3.Connection):
    """Демо-анкети репетиторів."""
    seeds = [
        dict(
            full_name="Анна Ковальчук",
            subjects="math",
            levels="8-11 клас",
            formats="online,offline",
            city="Київ",
            price=600,
            education="Київський національний університет ім. Тараса Шевченка, механіко-математичний факультет",
            experience_years=6,
            about="Готую до НМТ та ЗНО. Середній прогрес учнів +15 балів за курс підготовки.",
            contact="@anna_math_tutor",
            rating=4.9,
            reviews_count=87,
            verified=1,
        ),
        dict(
            full_name="Дмитро Олексенко",
            subjects="math,physics",
            levels="5-9 клас",
            formats="online",
            city="Харків",
            price=450,
            education="Харківський національний університет ім. В.Н. Карабіна",
            experience_years=3,
            about="Простими словами пояснюю складні теми. Спеціалізація — алгебра, геометрія, основи фізики.",
            contact="@dmytro_tutor",
            rating=4.7,
            reviews_count=42,
            verified=0,
        ),
        dict(
            full_name="Олена Петренко",
            subjects="english",
            levels="Дорослі, підготовка до IELTS",
            formats="online,offline",
            city="Київ",
            price=550,
            education="Cambridge CELTA, Київський національний лінгвістичний університет",
            experience_years=8,
            about="Розмовна англійська та підготовка до IELTS. Працюю з дорослими.",
            contact="@olena_english",
            rating=5.0,
            reviews_count=120,
            verified=1,
        ),
        dict(
            full_name="Максим Іваненко",
            subjects="physics",
            levels="9-11 клас, олімпіади",
            formats="offline",
            city="Львів",
            price=500,
            education="Львівський національний університет ім. Івана Франка, фізичний факультет",
            experience_years=5,
            about="Фізика для олімпіадників та підготовка до вступних іспитів у технічні виші.",
            contact="+380671234567",
            rating=4.8,
            reviews_count=33,
            verified=1,
        ),
        dict(
            full_name="Софія Гриценко",
            subjects="english,ukrainian",
            levels="1-9 клас",
            formats="online",
            city="Одеса",
            price=400,
            education="Одеський національний університет ім. І.І. Мечникова",
            experience_years=2,
            about="Англійська та українська для школярів 1-9 класів. Заняття в ігровій формі.",
            contact="@sofia_teach",
            rating=4.6,
            reviews_count=58,
            verified=0,
        ),
        dict(
            full_name="Ірина Мельник",
            subjects="chemistry,ukrainian",
            levels="7-11 клас",
            formats="online,offline",
            city="Дніпро",
            price=480,
            education="Дніпровський національний університет ім. Олеся Гончара",
            experience_years=4,
            about="Хімія без страху та зазубрювання. Готую до ДПА та НМТ.",
            contact="@irina_chem",
            rating=4.85,
            reviews_count=61,
            verified=1,
        ),
        dict(
            full_name="Андрій Шевченко",
            subjects="english,german",
            levels="5-11 клас, дорослі",
            formats="online",
            city="Львів",
            price=650,
            education="Львівський національний університет ім. Івана Франка, факультет іноземних мов",
            experience_years=7,
            about="Англійська та німецька для школярів та дорослих. Сертифікований викладач.",
            contact="@andriy_lang",
            rating=4.95,
            reviews_count=94,
            verified=1,
        ),
        dict(
            full_name="Наталія Коваленко",
            subjects="math,computer_science",
            levels="8-11 клас, програмування",
            formats="online,offline",
            city="Полтава",
            price=520,
            education="Полтавський національний технічний університет, факультет інформаційних технологій",
            experience_years=4,
            about="Математика та програмування для школярів. Допомагаю з розумінням алгоритмів.",
            contact="@nata_coding",
            rating=4.7,
            reviews_count=45,
            verified=0,
        ),
        dict(
            full_name="Василь Степанов",
            subjects="history,world_history,ukrainian",
            levels="5-11 клас",
            formats="online",
            city="Вінниця",
            price=350,
            education="Вінницький державний педагогічний університет, історичний факультет",
            experience_years=9,
            about="Історія України та всесвітня історія. Цікаві факти, аналіз подій.",
            contact="@vasyl_history",
            rating=4.8,
            reviews_count=76,
            verified=1,
        ),
        dict(
            full_name="Марія Бондар",
            subjects="biology,chemistry",
            levels="7-11 клас, медспрямування",
            formats="online,offline",
            city="Івано-Франківськ",
            price=580,
            education="Прикарпатський національний університет, біолого-хімічний факультет",
            experience_years=5,
            about="Біологія та хімія для вступників у медичні ВНЗ. Підготовка до НМТ.",
            contact="@maria_bio_chem",
            rating=4.92,
            reviews_count=68,
            verified=1,
        ),
    ]
    for s in seeds:
        conn.execute(
            """
            INSERT INTO tutors
                (telegram_id, full_name, subjects, levels, formats, city, price,
                 education, experience_years, about, contact, rating, reviews_count,
                 verified, status)
            VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'published')
            """,
            (
                s["full_name"], s["subjects"], s["levels"], s["formats"], s["city"],
                s["price"], s["education"], s["experience_years"], s["about"],
                s["contact"], s["rating"], s["reviews_count"], s["verified"],
            ),
        )
    conn.commit()


def save_student(telegram_id: int, full_name: str = None, phone: str = None, city: str = None):
    """Зберігає або оновлює дані учня"""
    conn = get_conn()
    conn.execute(
        """
        INSERT INTO students (telegram_id, full_name, phone, city)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(telegram_id) DO UPDATE SET
            full_name = COALESCE(?, full_name),
            phone = COALESCE(?, phone),
            city = COALESCE(?, city)
        """,
        (telegram_id, full_name, phone, city, full_name, phone, city)
    )
    conn.commit()
    conn.close()


def insert_tutor(data: dict) -> int:
    conn = get_conn()
    cur = conn.execute(
        """
        INSERT INTO tutors
            (telegram_id, full_name, subjects, levels, formats, city, price,
             education, experience_years, about, contact, rating, reviews_count,
             verified, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 'published')
        """,
        (
            data["telegram_id"], data["full_name"], data["subjects"], data["levels"],
            data["formats"], data["city"], data["price"], data["education"],
            data["experience_years"], data["about"], data["contact"],
        ),
    )
    conn.commit()
    tutor_id = cur.lastrowid
    conn.close()
    return tutor_id


def find_tutors(filters: dict) -> list[dict]:
    conn = get_conn()
    query = "SELECT * FROM tutors WHERE status = 'published'"
    params: list = []

    subject = filters.get("subject")
    if subject:
        query += " AND subjects LIKE ?"
        params.append(f"%{subject}%")

    fmt = filters.get("format")
    if fmt and fmt != "any":
        query += " AND formats LIKE ?"
        params.append(f"%{fmt}%")

    # Фільтр по ціні від-до
    price_from = filters.get("price_from")
    price_to = filters.get("price_to")
    if price_from is not None and price_from > 0:
        query += " AND price >= ?"
        params.append(price_from)
    if price_to is not None and price_to > 0:
        query += " AND price <= ?"
        params.append(price_to)

    city = filters.get("city")
    if city and city != "any":
        query += " AND city LIKE ?"
        params.append(f"%{city}%")

    query += " ORDER BY verified DESC, rating DESC, reviews_count DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_tutor_by_id(tutor_id: int) -> dict | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM tutors WHERE id = ?", (tutor_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def insert_request(student_telegram_id: int, tutor_id: int, contact: str, note: str):
    conn = get_conn()
    conn.execute(
        "INSERT INTO requests (student_telegram_id, tutor_id, contact, note) VALUES (?, ?, ?, ?)",
        (student_telegram_id, tutor_id, contact, note),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# FSM стани
# ---------------------------------------------------------------------------


class MainMenu(StatesGroup):
    main = State()


class Search(StatesGroup):
    choosing_subject = State()
    choosing_goal = State()
    choosing_format = State()
    choosing_city = State()
    entering_price_from = State()
    entering_price_to = State()
    choosing_level = State()
    viewing_card = State()
    entering_contact = State()


class TutorReg(StatesGroup):
    entering_name = State()
    choosing_subjects = State()
    entering_levels = State()
    choosing_formats = State()
    entering_city = State()
    entering_price = State()
    entering_education = State()
    entering_experience = State()
    entering_about = State()
    entering_contact = State()


# ---------------------------------------------------------------------------
# Клавіатури
# ---------------------------------------------------------------------------


def kb_main_menu():
    """Головне меню"""
    b = InlineKeyboardBuilder()
    b.button(text="Знайти репетитора", callback_data="menu:search")
    b.button(text="Зареєструватись як репетитор", callback_data="menu:tutor_reg")
    b.button(text="Мій профіль", callback_data="menu:profile")
    b.adjust(1)
    return b.as_markup()


def kb_back_to_main():
    """Кнопка повернення в головне меню"""
    b = InlineKeyboardBuilder()
    b.button(text="Головне меню", callback_data="menu:main")
    return b.as_markup()


def kb_subject_choice():
    """Клавіатура для вибору предмета"""
    b = InlineKeyboardBuilder()
    for key, label in SUBJECT_CATEGORIES.items():
        b.button(text=label, callback_data=f"s_subj:{key}")
    b.button(text="Інші предмети", callback_data="s_subj:other")
    b.button(text="Головне меню", callback_data="menu:main")
    b.adjust(1)
    return b.as_markup()


def kb_full_subjects():
    """Повний список предметів"""
    b = InlineKeyboardBuilder()
    other_subjects = {k: v for k, v in SUBJECTS.items() if k not in SUBJECT_CATEGORIES}
    for key, label in other_subjects.items():
        b.button(text=label, callback_data=f"s_subj:{key}")
    b.button(text="Назад", callback_data="s_subj:back")
    b.button(text="Головне меню", callback_data="menu:main")
    b.adjust(1)
    return b.as_markup()


def kb_city_choice():
    """Клавіатура для вибору міста"""
    b = InlineKeyboardBuilder()
    for city in CITIES:
        b.button(text=f"{city}", callback_data=f"s_city:{city}")
    b.button(text="Будь-яке місто", callback_data="s_city:any")
    b.button(text="Головне меню", callback_data="menu:main")
    b.adjust(1)
    return b.as_markup()


def kb_single(options: dict, prefix: str, extra: list[tuple[str, str]] | None = None):
    b = InlineKeyboardBuilder()
    for key, label in options.items():
        b.button(text=label, callback_data=f"{prefix}:{key}")
    for text, cb in extra or []:
        b.button(text=text, callback_data=cb)
    b.adjust(1)
    return b.as_markup()


def kb_tutor_card(tutor_id: int, has_prev: bool, has_next: bool):
    b = InlineKeyboardBuilder()
    b.button(text="Записатися", callback_data=f"request:{tutor_id}")
    if has_prev:
        b.button(text="Попередній", callback_data="nav:prev")
    if has_next:
        b.button(text="Наступний", callback_data="nav:next")
    b.button(text="Головне меню", callback_data="menu:main")
    b.adjust(1)
    return b.as_markup()


def kb_after_action():
    b = InlineKeyboardBuilder()
    b.button(text="Новий пошук", callback_data="menu:search")
    b.button(text="Головне меню", callback_data="menu:main")
    b.adjust(1)
    return b.as_markup()


# ---------------------------------------------------------------------------
# Допоміжні функції
# ---------------------------------------------------------------------------


def format_tutor_card(t: dict, position: int, total: int) -> str:
    subjects_label = ", ".join(SUBJECTS.get(s, s) for s in t["subjects"].split(","))
    formats_label = " / ".join(FORMAT_LABELS.get(f, f) for f in t["formats"].split(","))

    if t["reviews_count"] and t["reviews_count"] > 0:
        stars = "⭐" * round(t["rating"])
        rating_line = f"{stars} {t['rating']:.1f} ({t['reviews_count']} відгуків)"
    else:
        rating_line = "🆕 Новий репетитор (ще без відгуків)"

    lines = [f"<b>{t['full_name']}</b>  ({position}/{total})", rating_line]
    if t["verified"]:
        lines.append("✅ Перевірений репетитор BUKI")
    lines.append("")
    lines.append(f"<b>Предмети:</b> {subjects_label}")
    if t.get("levels"):
        lines.append(f"<b>Рівень учнів:</b> {t['levels']}")
    lines.append(f"<b>Ціна:</b> {t['price']} грн/год")
    lines.append(f"<b>Формат:</b> {formats_label}")
    lines.append(f"<b>Місто:</b> {t['city']}" if t.get("city") else "📍 Заняття лише онлайн")
    if t.get("education"):
        lines.append(f"<b>Освіта:</b> {t['education']}")
    lines.append(f"<b>Досвід викладання:</b> {t['experience_years']} р.")
    lines.append("")
    lines.append(f"<i>{t['about']}</i>")
    return "\n".join(lines)


async def show_tutor_card(message: Message, state: FSMContext, edit: bool = False):
    data = await state.get_data()
    ids = data["results"]
    index = data["index"]
    tutor = get_tutor_by_id(ids[index])

    text = format_tutor_card(tutor, index + 1, len(ids))
    kb = kb_tutor_card(tutor["id"], has_prev=index > 0, has_next=index < len(ids) - 1)

    if edit:
        await message.edit_text(text, reply_markup=kb)
    else:
        await message.answer(text, reply_markup=kb)


# ---------------------------------------------------------------------------
# Хендлери: головне меню
# ---------------------------------------------------------------------------

dp = Dispatcher(storage=MemoryStorage())


@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    # Зберігаємо інформацію про учня
    save_student(message.from_user.id, full_name=message.from_user.full_name)
    
    await message.answer(
        "👋 Привіт! Я бот <b>BUKI</b> — платформа для пошуку репетиторів.\n\n"
        "Оберіть дію в меню нижче:",
        reply_markup=kb_main_menu()
    )
    await state.set_state(MainMenu.main)


@dp.callback_query(F.data == "menu:main")
async def on_main_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text(
        "Головне меню\n\n"
        "Оберіть дію:",
        reply_markup=kb_main_menu()
    )
    await state.set_state(MainMenu.main)
    await call.answer()


@dp.callback_query(F.data == "menu:profile")
async def on_profile(call: CallbackQuery, state: FSMContext):
    conn = get_conn()
    student = conn.execute(
        "SELECT * FROM students WHERE telegram_id = ?",
        (call.from_user.id,)
    ).fetchone()
    conn.close()
    
    if student:
        text = (
            f"<b>Ваш профіль</b>\n\n"
            f"Ім'я: {student['full_name'] or 'Не вказано'}\n"
            f"Телефон: {student['phone'] or 'Не вказано'}\n"
            f"Місто: {student['city'] or 'Не вказано'}"
        )
    else:
        text = "Профіль не знайдено"
    
    await call.message.edit_text(text, reply_markup=kb_back_to_main())
    await state.set_state(MainMenu.main)
    await call.answer()


@dp.callback_query(F.data == "menu:search")
async def on_search_start(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text(
        "<b>Пошук репетитора</b>\n\n"
        "По якому предмету шукаємо репетитора?",
        reply_markup=kb_subject_choice()
    )
    await state.set_state(Search.choosing_subject)
    await call.answer()


@dp.callback_query(F.data == "menu:tutor_reg")
async def on_tutor_reg_start(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text(
        "<b>Реєстрація репетитора</b>\n\n"
        "Як вас звати? (прізвище та ім'я)"
    )
    await state.set_state(TutorReg.entering_name)
    await call.answer()


# ---------------------------------------------------------------------------
# Хендлери: пошук репетитора
# ---------------------------------------------------------------------------


@dp.callback_query(Search.choosing_subject, F.data.startswith("s_subj:"))
async def on_subject(call: CallbackQuery, state: FSMContext):
    subject = call.data.split(":")[1]
    
    if subject == "other":
        await call.message.edit_text(
            "Оберіть предмет зі списку:",
            reply_markup=kb_full_subjects()
        )
        await call.answer()
        return
    
    if subject == "back":
        await call.message.edit_text(
            "По якому предмету шукаємо репетитора?",
            reply_markup=kb_subject_choice()
        )
        await call.answer()
        return
    
    await state.update_data(subject=subject)
    await call.message.edit_text(
        "Яка мета занять?",
        reply_markup=kb_single(GOAL_LABELS, "goal", extra=[("🏠 Головне меню", "menu:main")])
    )
    await state.set_state(Search.choosing_goal)
    await call.answer()


@dp.callback_query(Search.choosing_goal, F.data.startswith("goal:"))
async def on_goal(call: CallbackQuery, state: FSMContext):
    goal = call.data.split(":")[1]
    await state.update_data(goal=goal)
    
    await call.message.edit_text(
        "У якому форматі зручніше займатись?",
        reply_markup=kb_single(
            {"online": "💻 Онлайн", "offline": "🏠 Офлайн"},
            "s_fmt",
            extra=[("🤷 Не важливо", "s_fmt:any"), ("🏠 Головне меню", "menu:main")]
        )
    )
    await state.set_state(Search.choosing_format)
    await call.answer()


@dp.callback_query(Search.choosing_format, F.data.startswith("s_fmt:"))
async def on_format(call: CallbackQuery, state: FSMContext):
    fmt = call.data.split(":")[1]
    await state.update_data(format=fmt)
    
    await call.message.edit_text(
        "У якому місті шукаємо?",
        reply_markup=kb_city_choice()
    )
    await state.set_state(Search.choosing_city)
    await call.answer()


@dp.callback_query(Search.choosing_city, F.data.startswith("s_city:"))
async def on_city(call: CallbackQuery, state: FSMContext):
    city = call.data.split(":")[1]
    await state.update_data(city=city)
    
    await call.message.edit_text(
        "Введіть мінімальну ціну (грн/год) або 0, щоб пропустити:"
    )
    await state.set_state(Search.entering_price_from)
    await call.answer()


@dp.message(Search.entering_price_from)
async def on_price_from(message: Message, state: FSMContext):
    try:
        price_from = int(message.text.strip())
        if price_from < 0:
            raise ValueError
    except ValueError:
        await message.answer("Будь ласка, введіть коректне число (наприклад: 300)")
        return
    
    await state.update_data(price_from=price_from)
    await message.answer(
        "Введіть максимальну ціну (грн/год) або 0, щоб пропустити:"
    )
    await state.set_state(Search.entering_price_to)


@dp.message(Search.entering_price_to)
async def on_price_to(message: Message, state: FSMContext):
    try:
        price_to = int(message.text.strip())
        if price_to < 0:
            raise ValueError
    except ValueError:
        await message.answer("Будь ласка, введіть коректне число (наприклад: 1000)")
        return
    
    await state.update_data(price_to=price_to)
    
    await message.answer(
        "Який рівень підготовки в учня?",
        reply_markup=kb_single(LEVEL_LABELS, "level", extra=[("🏠 Головне меню", "menu:main")])
    )
    await state.set_state(Search.choosing_level)


@dp.callback_query(Search.choosing_level, F.data.startswith("level:"))
async def on_level(call: CallbackQuery, state: FSMContext):
    level = call.data.split(":")[1]
    await state.update_data(level=level)
    
    await call.message.edit_text("🔎 Шукаю репетиторів за твоїми критеріями...")
    await asyncio.sleep(0.8)
    
    data = await state.get_data()
    results = find_tutors(data)
    
    if not results:
        await call.message.edit_text(
            "😕 За цими критеріями нікого не знайдено. Спробуйте інші параметри.",
            reply_markup=kb_after_action()
        )
        await call.answer()
        return
    
    await state.update_data(results=[t["id"] for t in results], index=0)
    await show_tutor_card(call.message, state, edit=True)
    await state.set_state(Search.viewing_card)
    await call.answer()


@dp.callback_query(Search.viewing_card, F.data.startswith("nav:"))
async def on_nav(call: CallbackQuery, state: FSMContext):
    direction = call.data.split(":")[1]
    data = await state.get_data()
    index = data["index"] + (1 if direction == "next" else -1)
    await state.update_data(index=index)
    await show_tutor_card(call.message, state, edit=True)
    await call.answer()


@dp.callback_query(Search.viewing_card, F.data.startswith("request:"))
async def on_request(call: CallbackQuery, state: FSMContext):
    tutor_id = int(call.data.split(":")[1])
    await state.update_data(chosen_tutor_id=tutor_id)
    tutor = get_tutor_by_id(tutor_id)
    
    await call.message.edit_text(
        f"Супер! Залиш номер телефону або @username, "
        f"щоб {tutor['full_name']} могла(міг) з тобою зв'язатись.\n\n"
        f"Напиши його текстом нижче 👇"
    )
    await state.set_state(Search.entering_contact)
    await call.answer()


@dp.message(Search.entering_contact)
async def on_contact(message: Message, state: FSMContext):
    data = await state.get_data()
    tutor = get_tutor_by_id(data["chosen_tutor_id"])
    contact = message.text.strip()
    
    # Зберігаємо контакт учня
    save_student(message.from_user.id, phone=contact)
    
    note = (
        f"Предмет: {SUBJECTS.get(data.get('subject'), '-')}; "
        f"Мета: {GOAL_LABELS.get(data.get('goal'), '-')}; "
        f"Рівень: {LEVEL_LABELS.get(data.get('level'), '-')}"
    )
    insert_request(message.from_user.id, tutor["id"], contact, note)
    
    await message.answer(
        f"✅ Заявку відправлено!\n\n"
        f"<b>{tutor['full_name']}</b> зв'яжеться з тобою за контактом:\n"
        f"<code>{contact}</code>\n\n"
        f"Зазвичай репетитори відповідають протягом кількох годин 🙌",
        reply_markup=kb_after_action()
    )
    await state.clear()
    await state.set_state(MainMenu.main)


# ---------------------------------------------------------------------------
# Хендлери: реєстрація репетитора
# ---------------------------------------------------------------------------


@dp.message(TutorReg.entering_name)
async def reg_name(message: Message, state: FSMContext):
    await state.update_data(full_name=message.text.strip(), reg_subjects=[])
    await message.answer(
        "Які предмети викладаєш? Обери один або кілька, потім натисни «Готово».",
        reply_markup=kb_multi_select(SUBJECTS, set(), "reg_subj")
    )
    await state.set_state(TutorReg.choosing_subjects)


def kb_multi_select(options: dict, selected: set, prefix: str):
    b = InlineKeyboardBuilder()
    for key, label in options.items():
        mark = "✅ " if key in selected else "▫️ "
        b.button(text=f"{mark}{label}", callback_data=f"{prefix}:{key}")
    b.button(text="Готово", callback_data=f"{prefix}_done")
    b.button(text="Головне меню", callback_data="menu:main")
    b.adjust(1)
    return b.as_markup()


@dp.callback_query(TutorReg.choosing_subjects, F.data.startswith("reg_subj:"))
async def reg_toggle_subject(call: CallbackQuery, state: FSMContext):
    key = call.data.split(":")[1]
    data = await state.get_data()
    selected = set(data.get("reg_subjects", []))
    selected.symmetric_difference_update({key})
    await state.update_data(reg_subjects=list(selected))
    await call.message.edit_reply_markup(reply_markup=kb_multi_select(SUBJECTS, selected, "reg_subj"))
    await call.answer()


@dp.callback_query(TutorReg.choosing_subjects, F.data == "reg_subj_done")
async def reg_subjects_done(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data.get("reg_subjects"):
        await call.answer("Обери хоча б один предмет!", show_alert=True)
        return
    await call.message.edit_text("Учням якого віку/класу викладаєш?\n(наприклад: 5-11 клас, дорослі)")
    await state.set_state(TutorReg.entering_levels)
    await call.answer()


@dp.message(TutorReg.entering_levels)
async def reg_levels(message: Message, state: FSMContext):
    await state.update_data(levels=message.text.strip(), reg_formats=[])
    await message.answer(
        "У якому форматі проводиш заняття? Обери один або кілька.",
        reply_markup=kb_multi_select(FORMAT_LABELS, set(), "reg_fmt")
    )
    await state.set_state(TutorReg.choosing_formats)


@dp.callback_query(TutorReg.choosing_formats, F.data.startswith("reg_fmt:"))
async def reg_toggle_format(call: CallbackQuery, state: FSMContext):
    key = call.data.split(":")[1]
    data = await state.get_data()
    selected = set(data.get("reg_formats", []))
    selected.symmetric_difference_update({key})
    await state.update_data(reg_formats=list(selected))
    await call.message.edit_reply_markup(reply_markup=kb_multi_select(FORMAT_LABELS, selected, "reg_fmt"))
    await call.answer()


@dp.callback_query(TutorReg.choosing_formats, F.data == "reg_fmt_done")
async def reg_formats_done(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    formats = data.get("reg_formats", [])
    if not formats:
        await call.answer("Обери хоча б один формат!", show_alert=True)
        return
    
    if "offline" in formats:
        await call.message.edit_text(
            "У якому місті проводиш офлайн-заняття?",
            reply_markup=kb_city_choice()
        )
        await state.set_state(TutorReg.entering_city)
    else:
        await state.update_data(city=None)
        await call.message.edit_text("Яка вартість заняття? Напиши число у грн/год (наприклад: 500)")
        await state.set_state(TutorReg.entering_price)
    await call.answer()


@dp.callback_query(TutorReg.entering_city, F.data.startswith("s_city:"))
async def reg_city(call: CallbackQuery, state: FSMContext):
    city = call.data.split(":")[1]
    await state.update_data(city=city)
    await call.message.edit_text("Яка вартість заняття? Напиши число у грн/год (наприклад: 500)")
    await state.set_state(TutorReg.entering_price)
    await call.answer()


@dp.message(TutorReg.entering_city)
async def reg_city_manual(message: Message, state: FSMContext):
    await state.update_data(city=message.text.strip())
    await message.answer("Яка вартість заняття? Напиши число у грн/год (наприклад: 500)")
    await state.set_state(TutorReg.entering_price)


@dp.message(TutorReg.entering_price)
async def reg_price(message: Message, state: FSMContext):
    try:
        price = int("".join(ch for ch in message.text if ch.isdigit()))
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Будь ласка, введи вартість цифрами, наприклад: 500")
        return
    await state.update_data(price=price)
    await message.answer("Яка у тебе освіта? (виш, факультет — або просто короткий опис)")
    await state.set_state(TutorReg.entering_education)


@dp.message(TutorReg.entering_education)
async def reg_education(message: Message, state: FSMContext):
    await state.update_data(education=message.text.strip())
    await message.answer("Скільки років досвіду викладання? Напиши число (наприклад: 3)")
    await state.set_state(TutorReg.entering_experience)


@dp.message(TutorReg.entering_experience)
async def reg_experience(message: Message, state: FSMContext):
    try:
        years = int("".join(ch for ch in message.text if ch.isdigit()) or "-1")
        if years < 0:
            raise ValueError
    except ValueError:
        await message.answer("Будь ласка, введи кількість років цифрами, наприклад: 3")
        return
    await state.update_data(experience_years=years)
    await message.answer("Розкажи трохи про себе та свій підхід до навчання (2-3 речення)")
    await state.set_state(TutorReg.entering_about)


@dp.message(TutorReg.entering_about)
async def reg_about(message: Message, state: FSMContext):
    await state.update_data(about=message.text.strip())
    await message.answer("Залиш номер телефону або @username, за яким учні зможуть з тобою зв'язатись")
    await state.set_state(TutorReg.entering_contact)


@dp.message(TutorReg.entering_contact)
async def reg_contact(message: Message, state: FSMContext):
    data = await state.get_data()
    contact = message.text.strip()
    
    tutor_data = {
        "telegram_id": message.from_user.id,
        "full_name": data["full_name"],
        "subjects": ",".join(data["reg_subjects"]),
        "levels": data.get("levels"),
        "formats": ",".join(data["reg_formats"]),
        "city": data.get("city"),
        "price": data["price"],
        "education": data.get("education"),
        "experience_years": data.get("experience_years", 0),
        "about": data.get("about"),
        "contact": contact,
    }
    tutor_id = insert_tutor(tutor_data)
    saved_tutor = get_tutor_by_id(tutor_id)
    
    await message.answer("🎉 Анкету збережено! Ось як вона виглядатиме для учнів:")
    await message.answer(format_tutor_card(saved_tutor, 1, 1))
    await message.answer(
        "Анкета успішно створена й доступна для пошуку",
        reply_markup=kb_after_action()
    )
    await state.clear()
    await state.set_state(MainMenu.main)


# ---------------------------------------------------------------------------
# Точка входу
# ---------------------------------------------------------------------------


async def main():
    init_db()
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await dp.start_polling(bot)



keep_alive()
if __name__ == "__main__":
    asyncio.run(main())