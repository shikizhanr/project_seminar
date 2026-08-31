from datetime import date

from pydantic import BaseModel


class RiskPrediction(BaseModel):
    habit_id: int
    probability: float | None
    risk_level: str
    factors: list[str]
    recommendation: str
    observed_opportunities: int = 0
    minimum_opportunities: int = 5


class HabitAnalytics(BaseModel):
    habit_id: int
    completion_rate: float
    current_streak: int
    longest_streak: int
    completed_last_30_days: int
    total_scheduled_last_30_days: int
    risk: RiskPrediction


class DailyPoint(BaseModel):
    day: date
    completed: int
    planned: int


class DashboardResponse(BaseModel):
    active_habits: int
    completed_today: int
    overall_completion_rate: float
    current_total_streak: int
    xp: int
    level: int
    trend: list[DailyPoint]
    habit_analytics: list[HabitAnalytics]
    motivation: str
    motivation_source: str = "rules"
    motivation_model: str | None = None


class LeaderboardEntry(BaseModel):
    user_id: int
    display_name: str
    completion_rate: float
    completed_last_30_days: int
    rank: int
