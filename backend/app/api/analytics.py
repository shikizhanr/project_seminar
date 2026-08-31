from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.app.api.deps import CurrentUser, DbSession
from backend.app.core.config import settings
from backend.app.models.habit import Habit
from backend.app.schemas.analytics import DashboardResponse
from backend.app.services.analytics import build_trend, habit_analytics
from backend.app.services.cache import cache_get, cache_set
from backend.app.services.motivation import personalized_motivational_message
from backend.app.services.prediction import get_predictor
from backend.app.services.timezone import local_date, local_today

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/dashboard", response_model=DashboardResponse)
async def dashboard(db: DbSession, user: CurrentUser) -> DashboardResponse:
    cached = None if settings.ollama_enabled else await cache_get(f"dashboard:{user.id}")
    if cached:
        return DashboardResponse.model_validate(cached)
    habits = list(
        await db.scalars(
            select(Habit)
            .options(selectinload(Habit.check_ins))
            .where(Habit.owner_id == user.id, Habit.is_active.is_(True))
        )
    )
    today = local_today(user.timezone)
    predictor = get_predictor()
    analytics = [
        habit_analytics(
            habit,
            list(habit.check_ins),
            predictor,
            today,
            local_date(habit.created_at, user.timezone),
        )
        for habit in habits
    ]
    all_check_ins = [item for habit in habits for item in habit.check_ins]
    completed = sum(item.completed_last_30_days for item in analytics)
    planned = sum(item.total_scheduled_last_30_days for item in analytics)
    total_streak = sum(item.current_streak for item in analytics)
    xp = completed * 10 + sum(5 for item in analytics if item.current_streak >= 7)
    motivation, motivation_source = await personalized_motivational_message(
        user.display_name,
        analytics,
        {
            habit.id: {
                "title": habit.title,
                "reminder_time": (
                    habit.reminder_time.strftime("%H:%M") if habit.reminder_time else None
                ),
            }
            for habit in habits
        },
    )
    result = DashboardResponse(
        active_habits=len(habits),
        completed_today=sum(item.completed for item in all_check_ins if item.day == today),
        overall_completion_rate=round(completed / planned, 3) if planned else 0,
        current_total_streak=total_streak,
        xp=xp,
        level=xp // 100 + 1,
        trend=build_trend(habits, all_check_ins, today),
        habit_analytics=analytics,
        motivation=motivation,
        motivation_source=motivation_source,
        motivation_model=settings.ollama_model if motivation_source == "ollama" else None,
    )
    if not settings.ollama_enabled:
        await cache_set(f"dashboard:{user.id}", result.model_dump(mode="json"))
    return result
