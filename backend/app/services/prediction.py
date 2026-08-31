from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier

from backend.app.models.habit import Habit, HabitCheckIn
from backend.app.schemas.analytics import RiskPrediction

MINIMUM_OPPORTUNITIES = 5


@dataclass
class HabitFeatures:
    weekday: int
    current_streak: int
    completion_rate_7d: float
    misses_last_3d: int
    difficulty: int
    target_days: int
    age_days: int

    def vector(self) -> list[float]:
        return [
            self.weekday,
            self.current_streak,
            self.completion_rate_7d,
            self.misses_last_3d,
            self.difficulty,
            self.target_days,
            self.age_days,
        ]


def calculate_streak(check_ins: list[HabitCheckIn], reference: date | None = None) -> int:
    reference = reference or date.today()
    completed = {item.day for item in check_ins if item.completed}
    cursor = reference
    if cursor not in completed:
        cursor -= timedelta(days=1)
    streak = 0
    while cursor in completed:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def longest_streak(check_ins: list[HabitCheckIn]) -> int:
    days = sorted({item.day for item in check_ins if item.completed})
    best = current = 0
    previous: date | None = None
    for day in days:
        current = current + 1 if previous and day == previous + timedelta(days=1) else 1
        best = max(best, current)
        previous = day
    return best


def expected_opportunities(days: int, target_days_per_week: int) -> int:
    return max(0, round(days * target_days_per_week / 7))


def effective_created_on(
    habit: Habit, check_ins: list[HabitCheckIn], target: date, created_on: date | None
) -> date:
    created = created_on or (habit.created_at.date() if habit.created_at else target)
    historical_days = [item.day for item in check_ins if item.day <= target]
    return min([created, *historical_days]) if historical_days else created


def extract_features(
    habit: Habit,
    check_ins: list[HabitCheckIn],
    target: date,
    created_on: date | None = None,
) -> HabitFeatures:
    by_day = {item.day: item.completed for item in check_ins}
    created = effective_created_on(habit, check_ins, target, created_on)
    available_days = max(0, (target - created).days)
    days_7 = min(7, available_days)
    days_3 = min(3, available_days)
    completed_7 = sum(
        by_day.get(target - timedelta(days=offset), False)
        for offset in range(1, days_7 + 1)
    )
    completed_3 = sum(
        by_day.get(target - timedelta(days=offset), False)
        for offset in range(1, days_3 + 1)
    )
    expected_7 = expected_opportunities(days_7, habit.target_days_per_week)
    expected_3 = expected_opportunities(days_3, habit.target_days_per_week)
    return HabitFeatures(
        weekday=target.weekday(),
        current_streak=calculate_streak(check_ins, target - timedelta(days=1)),
        completion_rate_7d=(min(completed_7 / expected_7, 1.0) if expected_7 else 0.5),
        misses_last_3d=max(0, expected_3 - completed_3),
        difficulty=habit.difficulty,
        target_days=habit.target_days_per_week,
        age_days=max(0, (target - created).days),
    )


class LapsePredictor:
    """Bootstrap model; production retraining can replace it without changing the API."""

    def __init__(self) -> None:
        rng = np.random.default_rng(42)
        rows: list[list[float]] = []
        labels: list[int] = []
        for _ in range(5000):
            weekday = int(rng.integers(0, 7))
            streak = int(rng.integers(0, 31))
            rate = float(rng.random())
            misses = int(rng.integers(0, 4))
            difficulty = int(rng.integers(1, 6))
            target_days = int(rng.integers(1, 8))
            age = int(rng.integers(0, 365))
            logit = (
                -1.0
                - 0.12 * streak
                - 2.1 * rate
                + 0.7 * misses
                + 0.32 * difficulty
                + 0.08 * target_days
                + 0.25 * (weekday >= 5)
                - 0.002 * min(age, 180)
                + rng.normal(0, 0.5)
            )
            probability = 1 / (1 + np.exp(-logit))
            rows.append([weekday, streak, rate, misses, difficulty, target_days, age])
            labels.append(int(rng.random() < probability))
        self.model = HistGradientBoostingClassifier(max_depth=4, random_state=42)
        self.model.fit(np.asarray(rows), np.asarray(labels))

    def predict(
        self,
        habit: Habit,
        check_ins: list[HabitCheckIn],
        target: date,
        created_on: date | None = None,
    ) -> RiskPrediction:
        created = effective_created_on(habit, check_ins, target, created_on)
        observed = expected_opportunities(
            max(0, (target - created).days), habit.target_days_per_week
        )
        if any(item.day == target and item.completed for item in check_ins):
            return RiskPrediction(
                habit_id=habit.id,
                probability=None,
                risk_level="completed",
                factors=["привычка уже выполнена сегодня"],
                recommendation="Риск на сегодня больше не рассчитывается.",
                observed_opportunities=observed,
                minimum_opportunities=MINIMUM_OPPORTUNITIES,
            )
        if observed < MINIMUM_OPPORTUNITIES:
            return RiskPrediction(
                habit_id=habit.id,
                probability=None,
                risk_level="insufficient_data",
                factors=[
                    f"накоплено {observed} из {MINIMUM_OPPORTUNITIES} ожидаемых выполнений"
                ],
                recommendation=(
                    "Продолжайте отмечать привычку — прогноз появится после накопления истории."
                ),
                observed_opportunities=observed,
                minimum_opportunities=MINIMUM_OPPORTUNITIES,
            )

        features = extract_features(habit, check_ins, target, created)
        probability = float(self.model.predict_proba([features.vector()])[0][1])
        factors: list[str] = []
        if features.misses_last_3d >= 2:
            factors.append("несколько пропусков за последние 3 дня")
        if features.completion_rate_7d < 0.5:
            factors.append("низкая регулярность за неделю")
        if features.current_streak >= 5:
            factors.append("устойчивая текущая серия снижает риск")
        if features.difficulty >= 4:
            factors.append("высокая субъективная сложность")
        if features.weekday >= 5:
            factors.append("изменение режима в выходной день")
        if not factors:
            factors.append("стабильный поведенческий профиль")
        level = "high" if probability >= 0.65 else "medium" if probability >= 0.35 else "low"
        recommendations = {
            "high": "Упростите привычку до двух минут и привяжите её к знакомому действию.",
            "medium": "Заранее выберите точное время и приготовьте всё необходимое.",
            "low": "Продолжайте в том же ритме и отметьте выполнение сразу после действия.",
        }
        return RiskPrediction(
            habit_id=habit.id,
            probability=round(probability, 3),
            risk_level=level,
            factors=factors,
            recommendation=recommendations[level],
            observed_opportunities=observed,
            minimum_opportunities=MINIMUM_OPPORTUNITIES,
        )


@lru_cache
def get_predictor() -> LapsePredictor:
    return LapsePredictor()
