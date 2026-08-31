from datetime import UTC, date, datetime, time, timedelta

from backend.app.models.habit import Habit, HabitCheckIn
from backend.app.services.prediction import LapsePredictor, extract_features


def make_habit(created_on: date, *, habit_id: int = 1) -> Habit:
    return Habit(
        id=habit_id,
        owner_id=1,
        title="Читать",
        target_days_per_week=7,
        difficulty=2,
        created_at=datetime.combine(created_on, time(), tzinfo=UTC),
    )


def test_new_habit_has_no_fictitious_misses() -> None:
    today = date(2026, 8, 30)
    habit = make_habit(today)

    features = extract_features(habit, [], today, today)
    risk = LapsePredictor().predict(habit, [], today, today)

    assert features.misses_last_3d == 0
    assert features.completion_rate_7d == 0.5
    assert risk.risk_level == "insufficient_data"
    assert risk.probability is None
    assert risk.observed_opportunities == 0


def test_completed_habit_has_no_current_day_risk() -> None:
    today = date(2026, 8, 30)
    habit = make_habit(today)
    check_ins = [HabitCheckIn(habit_id=habit.id, day=today, completed=True)]

    risk = LapsePredictor().predict(habit, check_ins, today, today)

    assert risk.risk_level == "completed"
    assert risk.probability is None


def test_probability_appears_after_enough_observation() -> None:
    today = date(2026, 8, 30)
    created_on = today - timedelta(days=7)
    habit = make_habit(created_on)
    check_ins = [
        HabitCheckIn(habit_id=habit.id, day=today - timedelta(days=offset), completed=True)
        for offset in (1, 2, 4, 5, 7)
    ]

    risk = LapsePredictor().predict(habit, check_ins, today, created_on)

    assert risk.risk_level in {"low", "medium", "high"}
    assert risk.probability is not None
    assert 0 <= risk.probability <= 1
    assert risk.observed_opportunities == 7
