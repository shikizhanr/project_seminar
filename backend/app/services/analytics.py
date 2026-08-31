from datetime import date, timedelta

from backend.app.models.habit import Habit, HabitCheckIn
from backend.app.schemas.analytics import DailyPoint, HabitAnalytics
from backend.app.services.prediction import (
    LapsePredictor,
    calculate_streak,
    effective_created_on,
    longest_streak,
)


def scheduled_count(habit: Habit, days: int) -> int:
    return max(1, round(days * habit.target_days_per_week / 7))


def habit_analytics(
    habit: Habit,
    check_ins: list[HabitCheckIn],
    predictor: LapsePredictor,
    today: date,
    created_on: date | None = None,
) -> HabitAnalytics:
    created = effective_created_on(habit, check_ins, today, created_on)
    since = max(today - timedelta(days=29), created)
    recent = [item for item in check_ins if since <= item.day <= today]
    complete = sum(item.completed for item in recent)
    elapsed_days = max(1, (today - since).days + 1)
    planned = scheduled_count(habit, elapsed_days)
    return HabitAnalytics(
        habit_id=habit.id,
        completion_rate=round(min(complete / planned, 1.0), 3),
        current_streak=calculate_streak(check_ins, today),
        longest_streak=longest_streak(check_ins),
        completed_last_30_days=complete,
        total_scheduled_last_30_days=planned,
        risk=predictor.predict(habit, check_ins, today, created),
    )


def build_trend(
    habits: list[Habit], check_ins: list[HabitCheckIn], today: date
) -> list[DailyPoint]:
    active_ids = {habit.id for habit in habits if habit.is_active}
    completion_days: dict[date, int] = {}
    for item in check_ins:
        if item.habit_id in active_ids and item.completed:
            completion_days[item.day] = completion_days.get(item.day, 0) + 1
    return [
        DailyPoint(
            day=day,
            completed=completion_days.get(day, 0),
            planned=round(
                sum(habit.target_days_per_week / 7 for habit in habits if habit.is_active)
            ),
        )
        for day in (today - timedelta(days=offset) for offset in range(13, -1, -1))
    ]
