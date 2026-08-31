import asyncio
import logging
import os
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.error import BadRequest
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

API_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")
EMAIL = os.getenv("BOT_USER_EMAIL", "")
PASSWORD = os.getenv("BOT_USER_PASSWORD", "")

TITLE, TARGET_DAYS, REMINDER_CHOICE, REMINDER_TIME = range(4)
EDIT_REMINDER_TIME = 0

MAIN_MENU = ReplyKeyboardMarkup(
    [
        ["☀️ Сегодня", "➕ Новая привычка"],
        ["📈 Прогресс", "🗓 История"],
        ["⚙️ Мои привычки"],
    ],
    resize_keyboard=True,
    input_field_placeholder="Что хотите сделать?",
)


async def api_request(method: str, path: str, *, json: dict | None = None) -> dict | list:
    async with httpx.AsyncClient(timeout=60) as client:
        login = await client.post(
            f"{API_URL}/auth/login", json={"email": EMAIL, "password": PASSWORD}
        )
        login.raise_for_status()
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        response = await client.request(method, f"{API_URL}{path}", headers=headers, json=json)
        response.raise_for_status()
        return response.json() if response.content else {}


def progress_bar(done: int, total: int, width: int = 10) -> str:
    filled = round(width * done / total) if total else 0
    return "▰" * filled + "▱" * (width - filled)


def reminder_label(value: str | None) -> str:
    return f"⏰ {value[:5]}" if value else "🔕 без напоминания"


def parse_reminder_time(value: str) -> str | None:
    try:
        parsed = datetime.strptime(value.strip(), "%H:%M")
    except ValueError:
        return None
    return parsed.strftime("%H:%M")


def today_message(habits: list[dict]) -> tuple[str, InlineKeyboardMarkup]:
    pending = [habit for habit in habits if not habit["completed_today"]]
    completed = [habit for habit in habits if habit["completed_today"]]
    total = len(habits)
    done = len(completed)
    parts = ["☀️ Сегодня", f"{progress_bar(done, total)}  {done}/{total}"]
    if pending:
        parts.append(
            "Осталось:\n"
            + "\n".join(
                f"• {habit['title']}  ·  {reminder_label(habit['reminder_time'])}"
                for habit in pending
            )
        )
    else:
        parts.append("🎉 Всё выполнено. Отличный день!")
    if completed:
        parts.append("Готово:\n" + "\n".join(f"✓ {habit['title']}" for habit in completed))
    keyboard_rows = [
        [
            InlineKeyboardButton(
                f"✓ {habit['title'][:38]}", callback_data=f"done:{habit['id']}"
            )
        ]
        for habit in pending
    ]
    keyboard_rows.append([InlineKeyboardButton("↻ Обновить", callback_data="today:refresh")])
    return "\n\n".join(parts), InlineKeyboardMarkup(keyboard_rows)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        await api_request("PUT", "/bot/link", json={"chat_id": update.effective_chat.id})
    except httpx.HTTPError:
        logger.exception("Could not persist Telegram chat link")
    await show_home(update, context)


async def show_home(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        user, habits = await asyncio.gather(
            api_request("GET", "/auth/me"),
            api_request("GET", "/habits/today"),
        )
        completed = sum(habit["completed_today"] for habit in habits)
        text = (
            f"🌿 Habit Coach\n\nПривет, {user['display_name']}!\n"
            f"Сегодня {progress_bar(completed, len(habits))} {completed}/{len(habits)}\n\n"
            "Выберите действие в меню ниже."
        )
    except httpx.HTTPError:
        text = "🌿 Habit Coach\n\nНе удалось загрузить данные. Попробуйте ещё раз."
    await update.effective_message.reply_text(text, reply_markup=MAIN_MENU)


async def today(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        habits = await api_request("GET", "/habits/today")
        text, keyboard = today_message(habits)
        if update.callback_query:
            await update.callback_query.answer()
            try:
                await update.callback_query.edit_message_text(text=text, reply_markup=keyboard)
            except BadRequest as error:
                if "Message is not modified" not in str(error):
                    raise
        else:
            await update.message.reply_text(text, reply_markup=keyboard)
    except httpx.HTTPError:
        await update.effective_message.reply_text("Не удалось обновить список. Попробуйте позже.")


async def done_callback(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    habit_id = int(query.data.split(":", maxsplit=1)[1])
    try:
        habits = await api_request("GET", "/habits/today")
        selected = next((habit for habit in habits if habit["id"] == habit_id), None)
        if selected and selected["completed_today"]:
            await query.answer("Уже выполнено сегодня")
            text, keyboard = today_message(habits)
            await query.edit_message_text(text=text, reply_markup=keyboard)
            return
        await query.answer("Сохраняю…")
        await query.edit_message_reply_markup(reply_markup=None)
        await api_request(
            "PUT", f"/habits/{habit_id}/check-ins", json={"day": date.today().isoformat()}
        )
        habits = await api_request("GET", "/habits/today")
        text, keyboard = today_message(habits)
        await query.edit_message_text(text=f"{text}\n\n✨ +10 XP", reply_markup=keyboard)
    except httpx.HTTPError:
        logger.exception("Check-in failed for habit %s", habit_id)
        await query.message.reply_text("Не удалось сохранить отметку. Попробуйте ещё раз.")


async def progress(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    waiting = await update.message.reply_text("🧠 Анализирую прогресс и готовлю новый совет…")
    try:
        dashboard, habits = await asyncio.gather(
            api_request("GET", "/analytics/dashboard"),
            api_request("GET", "/habits"),
        )
        titles = {habit["id"]: habit["title"] for habit in habits}
        risk_names = {"low": "низкий", "medium": "средний", "high": "высокий"}
        risk_icons = {"low": "🟢", "medium": "🟡", "high": "🔴"}
        risk_lines = []
        for item in dashboard["habit_analytics"]:
            risk = item["risk"]
            title = titles.get(item["habit_id"], "Привычка")
            if risk["risk_level"] == "completed":
                risk_lines.append(f"✅ {title}: выполнено сегодня")
            elif risk["risk_level"] == "insufficient_data":
                risk_lines.append(
                    f"⚪ {title}: недостаточно данных · "
                    f"{risk['observed_opportunities']}/{risk['minimum_opportunities']}"
                )
            else:
                risk_lines.append(
                    f"{risk_icons[risk['risk_level']]} {title}: "
                    f"{risk_names[risk['risk_level']]} · {risk['probability'] * 100:.0f}%"
                )
        source = (
            f"ML-фокус + Ollama · {dashboard['motivation_model']}"
            if dashboard.get("motivation_source") == "ollama"
            else "ML-фокус + алгоритм"
        )
        text = (
            "📈 Ваш прогресс\n\n"
            f"Сегодня: {dashboard['completed_today']}/{dashboard['active_habits']}\n"
            f"Регулярность за 30 дней: {dashboard['overall_completion_rate'] * 100:.0f}%\n"
            f"Уровень {dashboard['level']} · {dashboard['xp']} XP\n\n"
            f"Прогноз пропуска:\n{chr(10).join(risk_lines) or 'Недостаточно данных'}\n\n"
            f"🧭 План на сегодня · {source}\n{dashboard['motivation']}"
        )
        await waiting.edit_text(text)
    except httpx.HTTPError:
        await waiting.edit_text("Не удалось построить аналитику. Попробуйте позже.")


async def new_habit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["new_habit"] = {}
    await update.message.reply_text(
        "➕ Новая привычка · шаг 1 из 3\n\nКак назовём привычку?\n"
        "Например: «Гулять 20 минут».\n\nДля отмены: /cancel",
        reply_markup=ReplyKeyboardRemove(),
    )
    return TITLE


async def habit_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    title = update.message.text.strip()
    if not title or len(title) > 120:
        await update.message.reply_text("Введите название длиной от 1 до 120 символов.")
        return TITLE
    context.user_data["new_habit"]["title"] = title
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(str(day), callback_data=f"frequency:{day}")
                for day in range(1, 5)
            ],
            [
                InlineKeyboardButton(str(day), callback_data=f"frequency:{day}")
                for day in range(5, 8)
            ],
            [InlineKeyboardButton("Отмена", callback_data="new:cancel")],
        ]
    )
    await update.message.reply_text(
        "➕ Новая привычка · шаг 2 из 3\n\nСколько дней в неделю выполнять?",
        reply_markup=keyboard,
    )
    return TARGET_DAYS


async def habit_frequency(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["new_habit"]["target_days_per_week"] = int(query.data.split(":")[1])
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("⏰ Указать точное время", callback_data="reminder:custom")],
            [InlineKeyboardButton("🔕 Без напоминания", callback_data="reminder:none")],
            [InlineKeyboardButton("Отмена", callback_data="new:cancel")],
        ]
    )
    await query.edit_message_text(
        "➕ Новая привычка · шаг 3 из 3\n\n"
        "Нужно ежедневное напоминание? Можно указать любое точное время.",
        reply_markup=keyboard,
    )
    return REMINDER_CHOICE


async def habit_reminder_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    value = query.data.split(":", maxsplit=1)[1]
    if value == "custom":
        await query.edit_message_text(
            "⏰ Введите точное время в формате ЧЧ:ММ.\n\n"
            "Например: 07:30 или 22:15. Время считается по часовому поясу профиля."
        )
        return REMINDER_TIME
    context.user_data["new_habit"]["reminder_time"] = None
    return await create_habit(update, context)


async def habit_custom_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    reminder_time = parse_reminder_time(update.message.text)
    if reminder_time is None:
        await update.message.reply_text(
            "Не получилось распознать время. Введите часы и минуты, например 07:30."
        )
        return REMINDER_TIME
    context.user_data["new_habit"]["reminder_time"] = reminder_time
    return await create_habit(update, context)


async def create_habit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    payload = context.user_data.get("new_habit", {})
    message = update.callback_query.message if update.callback_query else update.message
    try:
        habit = await api_request("POST", "/habits", json=payload)
        await message.reply_text(
            "🌱 Привычка создана!\n\n"
            f"{habit['title']}\n"
            f"📅 {habit['target_days_per_week']} дн. в неделю\n"
            f"{reminder_label(habit['reminder_time'])}",
            reply_markup=MAIN_MENU,
        )
    except httpx.HTTPError:
        logger.exception("Habit creation failed")
        await message.reply_text(
            "Не удалось создать привычку. Попробуйте позже.", reply_markup=MAIN_MENU
        )
    context.user_data.pop("new_habit", None)
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("new_habit", None)
    await update.message.reply_text("Создание отменено.", reply_markup=MAIN_MENU)
    return ConversationHandler.END


async def cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("new_habit", None)
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("Создание привычки отменено.")
    await update.callback_query.message.reply_text("Главное меню", reply_markup=MAIN_MENU)
    return ConversationHandler.END


async def history_menu(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        habits = [habit for habit in await api_request("GET", "/habits") if habit["is_active"]]
        if not habits:
            await update.effective_message.reply_text(
                "История пока пуста. Сначала добавьте привычку.", reply_markup=MAIN_MENU
            )
            return
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        habit["title"][:45], callback_data=f"history:{habit['id']}:30"
                    )
                ]
                for habit in habits
            ]
        )
        await update.effective_message.reply_text(
            "🗓 История\n\nВыберите привычку:", reply_markup=keyboard
        )
    except httpx.HTTPError:
        await update.effective_message.reply_text("Не удалось загрузить историю.")


async def history_detail(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    _, habit_id_raw, days_raw = query.data.split(":")
    habit_id, days = int(habit_id_raw), int(days_raw)
    try:
        habits, check_ins, user = await asyncio.gather(
            api_request("GET", "/habits"),
            api_request("GET", f"/habits/{habit_id}/check-ins"),
            api_request("GET", "/auth/me"),
        )
        habit = next(item for item in habits if item["id"] == habit_id)
        try:
            timezone = ZoneInfo(user["timezone"])
        except ZoneInfoNotFoundError:
            timezone = ZoneInfo("UTC")
        today_local = datetime.now(timezone).date()
        completed = {date.fromisoformat(item["day"]) for item in check_ins if item["completed"]}
        dates = [today_local - timedelta(days=offset) for offset in range(days - 1, -1, -1)]
        count = sum(day in completed for day in dates)
        planned = max(1, round(days * habit["target_days_per_week"] / 7))
        rate = min(100, round(100 * count / planned))
        streak = 0
        cursor = today_local if today_local in completed else today_local - timedelta(days=1)
        while cursor in completed:
            streak += 1
            cursor -= timedelta(days=1)
        symbols = ["●" if day in completed else "·" for day in dates]
        calendar = "\n".join(" ".join(symbols[i : i + 7]) for i in range(0, len(symbols), 7))
        text = (
            f"🗓 {habit['title']}\n\n"
            f"Период: {days} дней\n"
            f"Выполнено: {count} из {planned} · {rate}%\n"
            f"Текущая серия: {streak} дн.\n\n"
            f"{calendar}\n● выполнено  · пропуск"
        )
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("7 дней", callback_data=f"history:{habit_id}:7"),
                    InlineKeyboardButton("30 дней", callback_data=f"history:{habit_id}:30"),
                    InlineKeyboardButton("90 дней", callback_data=f"history:{habit_id}:90"),
                ],
                [InlineKeyboardButton("‹ К списку", callback_data="history:list")],
            ]
        )
        await query.edit_message_text(text=text, reply_markup=keyboard)
    except (httpx.HTTPError, StopIteration):
        await query.edit_message_text("Не удалось загрузить историю.")


async def history_list_callback(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    try:
        habits = [habit for habit in await api_request("GET", "/habits") if habit["is_active"]]
        if not habits:
            await update.effective_message.reply_text(
                "Активных привычек пока нет.", reply_markup=MAIN_MENU
            )
            return
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        habit["title"][:45], callback_data=f"history:{habit['id']}:30"
                    )
                ]
                for habit in habits
            ]
        )
        await update.callback_query.edit_message_text(
            "🗓 История\n\nВыберите привычку:", reply_markup=keyboard
        )
    except httpx.HTTPError:
        await update.callback_query.edit_message_text("Не удалось загрузить историю.")


async def habits_menu(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        habits = [habit for habit in await api_request("GET", "/habits") if habit["is_active"]]
        if not habits:
            await update.effective_message.reply_text(
                "Активных привычек пока нет.", reply_markup=MAIN_MENU
            )
            return
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        f"{habit['title'][:32]} · {reminder_label(habit['reminder_time'])}",
                        callback_data=f"manage:{habit['id']}",
                    )
                ]
                for habit in habits
            ]
        )
        await update.effective_message.reply_text(
            "⚙️ Мои привычки\n\nЗдесь можно изменить напоминание или убрать привычку:",
            reply_markup=keyboard,
        )
    except httpx.HTTPError:
        await update.effective_message.reply_text("Не удалось загрузить привычки.")


async def manage_habit(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    habit_id = int(query.data.split(":")[1])
    habits = await api_request("GET", "/habits")
    habit = next((item for item in habits if item["id"] == habit_id), None)
    if not habit:
        await query.edit_message_text("Привычка не найдена.")
        return
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("⏰ Изменить время", callback_data=f"editreminder:{habit_id}")],
            [InlineKeyboardButton("🔕 Отключить", callback_data=f"setreminder:{habit_id}:off")],
            [InlineKeyboardButton("🗑 Архивировать", callback_data=f"archive:{habit_id}")],
        ]
    )
    await query.edit_message_text(
        f"⚙️ {habit['title']}\n\n"
        f"Цель: {habit['target_days_per_week']} дн. в неделю\n"
        f"Напоминание: {reminder_label(habit['reminder_time'])}\n\n"
        "Здесь можно указать любое точное время или отключить напоминание:",
        reply_markup=keyboard,
    )


async def begin_edit_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    habit_id = int(query.data.split(":", maxsplit=1)[1])
    context.user_data["editing_reminder_habit_id"] = habit_id
    await query.answer()
    await query.edit_message_text(
        "⏰ Введите новое время в формате ЧЧ:ММ.\n\n"
        "Например: 06:45 или 19:20. Время считается по часовому поясу профиля.\n"
        "Для отмены: /cancel"
    )
    await query.message.reply_text(
        "Введите точное время:", reply_markup=ReplyKeyboardRemove()
    )
    return EDIT_REMINDER_TIME


async def save_custom_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    reminder_time = parse_reminder_time(update.message.text)
    if reminder_time is None:
        await update.message.reply_text(
            "Нужен формат ЧЧ:ММ, например 09:05. Попробуйте ещё раз или отправьте /cancel."
        )
        return EDIT_REMINDER_TIME
    habit_id = context.user_data.get("editing_reminder_habit_id")
    try:
        habit = await api_request(
            "PATCH", f"/habits/{habit_id}", json={"reminder_time": reminder_time}
        )
        await update.message.reply_text(
            f"✅ Напоминание сохранено\n\n{habit['title']}\n⏰ каждый день в {reminder_time}",
            reply_markup=MAIN_MENU,
        )
    except httpx.HTTPError:
        await update.message.reply_text(
            "Не удалось изменить напоминание. Попробуйте позже.", reply_markup=MAIN_MENU
        )
    context.user_data.pop("editing_reminder_habit_id", None)
    return ConversationHandler.END


async def cancel_edit_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("editing_reminder_habit_id", None)
    await update.message.reply_text("Изменение времени отменено.", reply_markup=MAIN_MENU)
    return ConversationHandler.END


async def set_reminder(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    _, habit_id_raw, value = query.data.split(":", maxsplit=2)
    habit_id = int(habit_id_raw)
    await query.answer("Сохраняю…")
    try:
        habit = await api_request(
            "PATCH",
            f"/habits/{habit_id}",
            json={"reminder_time": None if value == "off" else value},
        )
        await query.edit_message_text(
            f"✅ Настройки сохранены\n\n{habit['title']}\n{reminder_label(habit['reminder_time'])}"
        )
    except httpx.HTTPError:
        await query.edit_message_text("Не удалось изменить напоминание.")


async def archive_habit(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    habit_id = int(query.data.split(":")[1])
    await query.answer()
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Да, архивировать", callback_data=f"archive-confirm:{habit_id}")],
            [InlineKeyboardButton("Отмена", callback_data=f"manage:{habit_id}")],
        ]
    )
    await query.edit_message_text(
        "Убрать привычку из активного списка? История выполнения сохранится.",
        reply_markup=keyboard,
    )


async def archive_confirm(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    habit_id = int(query.data.split(":")[1])
    await query.answer("Архивирую…")
    try:
        await api_request("DELETE", f"/habits/{habit_id}")
        await query.edit_message_text("Привычка перенесена в архив. История сохранена.")
    except httpx.HTTPError:
        await query.edit_message_text("Не удалось архивировать привычку.")


async def reminder_loop(application: Application) -> None:
    sent: set[str] = set()
    while True:
        try:
            link, user, habits = await asyncio.gather(
                api_request("GET", "/bot/link"),
                api_request("GET", "/auth/me"),
                api_request("GET", "/habits/today"),
            )
            try:
                timezone = ZoneInfo(user["timezone"])
            except ZoneInfoNotFoundError:
                timezone = ZoneInfo("UTC")
            now = datetime.now(timezone)
            current_time = now.strftime("%H:%M")
            prefix = now.date().isoformat()
            sent = {key for key in sent if key.startswith(prefix)}
            for habit in habits:
                reminder = habit.get("reminder_time")
                key = f"{prefix}:{habit['id']}"
                if (
                    reminder
                    and reminder[:5] == current_time
                    and not habit["completed_today"]
                    and key not in sent
                ):
                    keyboard = InlineKeyboardMarkup(
                        [[InlineKeyboardButton("✓ Выполнено", callback_data=f"done:{habit['id']}")]]
                    )
                    await application.bot.send_message(
                        chat_id=link["chat_id"],
                        text=(
                            f"⏰ Время для привычки\n\n{habit['title']}\n\n"
                            "Маленький шаг тоже считается."
                        ),
                        reply_markup=keyboard,
                    )
                    sent.add(key)
        except httpx.HTTPStatusError as error:
            if error.response.status_code != 404:
                logger.warning("Reminder API request failed: %s", error)
        except (httpx.HTTPError, KeyError, TypeError):
            logger.exception("Reminder loop failed")
        await asyncio.sleep(30)


async def post_init(application: Application) -> None:
    application.bot_data["reminder_task"] = asyncio.create_task(
        reminder_loop(application), name="habit-reminders"
    )


async def post_shutdown(application: Application) -> None:
    task = application.bot_data.get("reminder_task")
    if task:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")
    application = (
        Application.builder()
        .token(token)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("menu", show_home))
    application.add_handler(
        ConversationHandler(
            entry_points=[
                CommandHandler("new", new_habit),
                MessageHandler(filters.Regex(r"^➕ Новая привычка$"), new_habit),
            ],
            states={
                TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, habit_title)],
                TARGET_DAYS: [CallbackQueryHandler(habit_frequency, pattern=r"^frequency:[1-7]$")],
                REMINDER_CHOICE: [
                    CallbackQueryHandler(habit_reminder_choice, pattern=r"^reminder:")
                ],
                REMINDER_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, habit_custom_time)],
            },
            fallbacks=[
                CommandHandler("cancel", cancel),
                CallbackQueryHandler(cancel_callback, pattern=r"^new:cancel$"),
            ],
        )
    )
    application.add_handler(
        ConversationHandler(
            entry_points=[
                CallbackQueryHandler(begin_edit_reminder, pattern=r"^editreminder:\d+$")
            ],
            states={
                EDIT_REMINDER_TIME: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, save_custom_reminder)
                ]
            },
            fallbacks=[CommandHandler("cancel", cancel_edit_reminder)],
        )
    )
    application.add_handler(CommandHandler("today", today))
    application.add_handler(CommandHandler("progress", progress))
    application.add_handler(CommandHandler("history", history_menu))
    application.add_handler(CallbackQueryHandler(done_callback, pattern=r"^done:\d+$"))
    application.add_handler(CallbackQueryHandler(today, pattern=r"^today:refresh$"))
    application.add_handler(
        CallbackQueryHandler(history_detail, pattern=r"^history:\d+:(7|30|90)$")
    )
    application.add_handler(CallbackQueryHandler(history_list_callback, pattern=r"^history:list$"))
    application.add_handler(CallbackQueryHandler(manage_habit, pattern=r"^manage:\d+$"))
    application.add_handler(
        CallbackQueryHandler(
            set_reminder,
            pattern=r"^setreminder:\d+:off$",
        )
    )
    application.add_handler(CallbackQueryHandler(archive_habit, pattern=r"^archive:\d+$"))
    application.add_handler(
        CallbackQueryHandler(archive_confirm, pattern=r"^archive-confirm:\d+$")
    )
    application.add_handler(MessageHandler(filters.Regex(r"^☀️ Сегодня$"), today))
    application.add_handler(MessageHandler(filters.Regex(r"^📈 Прогресс$"), progress))
    application.add_handler(MessageHandler(filters.Regex(r"^🗓 История$"), history_menu))
    application.add_handler(MessageHandler(filters.Regex(r"^⚙️ Мои привычки$"), habits_menu))
    application.run_polling(drop_pending_updates=False)


if __name__ == "__main__":
    main()
