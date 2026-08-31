from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.app.api.deps import CurrentUser, DbSession
from backend.app.models.habit import Habit, HabitCheckIn
from backend.app.schemas.analytics import RiskPrediction
from backend.app.schemas.habit import (
    CheckInCreate,
    CheckInResponse,
    HabitCreate,
    HabitResponse,
    HabitUpdate,
    TodayHabitResponse,
)
from backend.app.services.cache import cache_delete
from backend.app.services.prediction import get_predictor
from backend.app.services.timezone import local_date, local_today

router = APIRouter(prefix="/habits", tags=["habits"])


async def owned_habit(db: DbSession, user_id: int, habit_id: int) -> Habit:
    habit = await db.scalar(
        select(Habit)
        .options(selectinload(Habit.check_ins))
        .where(Habit.id == habit_id, Habit.owner_id == user_id)
    )
    if habit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Habit not found")
    return habit


@router.get("", response_model=list[HabitResponse])
async def list_habits(db: DbSession, user: CurrentUser) -> list[Habit]:
    result = await db.scalars(
        select(Habit).where(Habit.owner_id == user.id).order_by(Habit.is_active.desc(), Habit.id)
    )
    return list(result)


@router.post("", response_model=HabitResponse, status_code=status.HTTP_201_CREATED)
async def create_habit(payload: HabitCreate, db: DbSession, user: CurrentUser) -> Habit:
    habit = Habit(owner_id=user.id, **payload.model_dump())
    db.add(habit)
    await db.commit()
    await db.refresh(habit)
    await cache_delete(f"dashboard:{user.id}")
    return habit


@router.get("/today", response_model=list[TodayHabitResponse])
async def today_habits(db: DbSession, user: CurrentUser) -> list[TodayHabitResponse]:
    today = local_today(user.timezone)
    habits = list(
        await db.scalars(
            select(Habit)
            .options(selectinload(Habit.check_ins))
            .where(Habit.owner_id == user.id, Habit.is_active.is_(True))
            .order_by(Habit.id)
        )
    )
    return [
        TodayHabitResponse(
            **HabitResponse.model_validate(habit).model_dump(),
            completed_today=any(item.day == today and item.completed for item in habit.check_ins),
        )
        for habit in habits
    ]


@router.patch("/{habit_id}", response_model=HabitResponse)
async def update_habit(
    habit_id: int, payload: HabitUpdate, db: DbSession, user: CurrentUser
) -> Habit:
    habit = await owned_habit(db, user.id, habit_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(habit, key, value)
    await db.commit()
    await db.refresh(habit)
    await cache_delete(f"dashboard:{user.id}")
    return habit


@router.delete("/{habit_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_habit(habit_id: int, db: DbSession, user: CurrentUser) -> Response:
    habit = await owned_habit(db, user.id, habit_id)
    habit.is_active = False
    await db.commit()
    await cache_delete(f"dashboard:{user.id}")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/{habit_id}/check-ins", response_model=CheckInResponse)
async def check_in(
    habit_id: int, payload: CheckInCreate, db: DbSession, user: CurrentUser
) -> HabitCheckIn:
    if payload.day > local_today(user.timezone):
        raise HTTPException(status_code=422, detail="A future day cannot be checked in")
    habit = await owned_habit(db, user.id, habit_id)
    existing = next((item for item in habit.check_ins if item.day == payload.day), None)
    risk = get_predictor().predict(
        habit,
        list(habit.check_ins),
        payload.day,
        local_date(habit.created_at, user.timezone),
    ).probability
    values = payload.model_dump()
    if existing:
        for key, value in values.items():
            setattr(existing, key, value)
        existing.predicted_risk = risk
        check_in_item = existing
    else:
        check_in_item = HabitCheckIn(habit_id=habit.id, predicted_risk=risk, **values)
        db.add(check_in_item)
    await db.commit()
    await db.refresh(check_in_item)
    await cache_delete(f"dashboard:{user.id}")
    return check_in_item


@router.get("/{habit_id}/check-ins", response_model=list[CheckInResponse])
async def list_check_ins(habit_id: int, db: DbSession, user: CurrentUser) -> list[HabitCheckIn]:
    await owned_habit(db, user.id, habit_id)
    result = await db.scalars(
        select(HabitCheckIn)
        .where(HabitCheckIn.habit_id == habit_id)
        .order_by(HabitCheckIn.day.desc())
        .limit(90)
    )
    return list(result)


@router.get("/{habit_id}/risk", response_model=RiskPrediction)
async def predict_risk(habit_id: int, db: DbSession, user: CurrentUser) -> RiskPrediction:
    habit = await owned_habit(db, user.id, habit_id)
    return get_predictor().predict(
        habit,
        list(habit.check_ins),
        local_today(user.timezone),
        local_date(habit.created_at, user.timezone),
    )
