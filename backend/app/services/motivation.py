import re
import secrets

import httpx

from backend.app.core.config import settings
from backend.app.schemas.analytics import HabitAnalytics

STRATEGIES = ("mini_step", "environment", "time_anchor", "reward")
_last_strategy_by_habit: dict[int, str] = {}


def motivational_message(name: str, analytics: list[HabitAnalytics]) -> str:
    if not analytics:
        return f"{name}, добавьте первую привычку — после этого здесь появится план на день."
    eligible = [item for item in analytics if item.risk.probability is not None]
    if not eligible:
        if all(item.risk.risk_level == "completed" for item in analytics):
            return "🎉 Все привычки на сегодня выполнены. Прогноз срыва больше не нужен."
        return (
            "🌱 Пока недостаточно истории для персонального прогноза. "
            "Продолжайте делать отметки — модель начнёт оценку после 5 ожидаемых выполнений."
        )
    target = max(eligible, key=lambda item: item.risk.probability or 0)
    return build_action_plan(name, target, "Привычка", None, "mini_step")


def tiny_step(title: str) -> str:
    normalized = title.casefold()
    if any(word in normalized for word in ("чита", "книг")):
        return "откройте книгу и прочитайте одну страницу"
    if any(word in normalized for word in ("гуля", "прогул", "ходь")):
        return "наденьте обувь и выйдите на прогулку хотя бы на 5 минут"
    if any(word in normalized for word in ("телефон", "смартфон", "соцсет")):
        return "включите режим «Не беспокоить» и уберите телефон подальше"
    if any(word in normalized for word in ("вод", "пить")):
        return "налейте стакан воды и выпейте его сейчас"
    if any(word in normalized for word in ("спорт", "трен", "заряд", "упраж")):
        return "сделайте двухминутную разминку"
    if any(word in normalized for word in ("уч", "курс", "урок")):
        return "откройте учебный материал и позанимайтесь 5 минут"
    return f"уделите привычке «{title}» всего 2 минуты"


def strategy_action(title: str, reminder_time: str | None, strategy: str) -> str:
    if strategy == "environment":
        return (
            f"подготовьте всё необходимое для «{title}» заранее и уберите "
            "одно отвлечение"
        )
    if strategy == "time_anchor":
        if reminder_time:
            return f"в {reminder_time} сразу начните с малого: {tiny_step(title)}"
        return f"выберите точное время на сегодня и тогда {tiny_step(title)}"
    if strategy == "reward":
        return (
            f"выполните минимальную версию «{title}», сразу отметьте её в боте "
            "и сделайте короткую приятную паузу"
        )
    return tiny_step(title)


def build_action_plan(
    name: str,
    target: HabitAnalytics,
    title: str,
    reminder_time: str | None,
    strategy: str,
) -> str:
    probability = round((target.risk.probability or 0) * 100)
    regularity = round(target.completion_rate * 100)
    factor = target.risk.factors[0] if target.risk.factors else "текущая регулярность"
    action = strategy_action(title, reminder_time, strategy)
    return (
        f"🎯 Фокус: «{title}»\n"
        f"Почему: это самый высокий прогноз пропуска — {probability}%. "
        f"Регулярность — {regularity}%; главный сигнал: {factor}.\n"
        f"Что сделать сегодня: {action}."
    )


async def personalized_motivational_message(
    name: str,
    analytics: list[HabitAnalytics],
    habit_details: dict[int, dict[str, str | None]],
) -> tuple[str, str]:
    if not analytics:
        return motivational_message(name, analytics), "rules"

    eligible = [item for item in analytics if item.risk.probability is not None]
    if not eligible:
        return motivational_message(name, analytics), "rules"

    target = max(
        eligible,
        key=lambda item: (item.risk.probability or 0, -item.completion_rate),
    )
    details = habit_details.get(target.habit_id, {})
    title = details.get("title") or "Привычка"
    reminder_time = details.get("reminder_time")

    previous = _last_strategy_by_habit.get(target.habit_id)
    available = [strategy for strategy in STRATEGIES if strategy != previous]
    fallback_strategy = secrets.choice(available)
    strategy = fallback_strategy
    source = "rules"

    if settings.ollama_enabled:
        prompt = (
            "/no_think\n"
            "Ты выбираешь стратегию для тренера привычек. Ответь только одним кодом "
            "из списка, без пояснений: "
            f"{', '.join(available)}. "
            f"Привычка: {title}. Регулярность: {target.completion_rate * 100:.0f}%. "
            f"Факторы: {', '.join(target.risk.factors)}."
        )
        try:
            async with httpx.AsyncClient(timeout=settings.ollama_timeout_seconds) as client:
                response = await client.post(
                    f"{settings.ollama_url.rstrip('/')}/api/chat",
                    json={
                        "model": settings.ollama_model,
                        "messages": [{"role": "user", "content": prompt}],
                        "stream": False,
                        "think": False,
                        "keep_alive": "10m",
                        "options": {"temperature": 0.7, "num_predict": 12},
                    },
                )
                response.raise_for_status()
                content = response.json().get("message", {}).get("content", "")
                content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL)
                selected = next((item for item in available if item in content), None)
                if selected:
                    strategy = selected
                    source = "ollama"
        except (httpx.HTTPError, KeyError, ValueError):
            pass

    _last_strategy_by_habit[target.habit_id] = strategy
    return build_action_plan(name, target, title, reminder_time, strategy), source
