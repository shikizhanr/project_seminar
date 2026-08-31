from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from backend.app.api.deps import CurrentUser, DbSession
from backend.app.models.habit import Habit
from backend.app.models.user import Friendship, User
from backend.app.schemas.analytics import LeaderboardEntry

router = APIRouter(prefix="/social", tags=["social"])


class FollowRequest(BaseModel):
    email: EmailStr


@router.post("/follow", status_code=status.HTTP_201_CREATED)
async def follow(payload: FollowRequest, db: DbSession, user: CurrentUser) -> dict[str, str]:
    target = await db.scalar(select(User).where(User.email == payload.email.lower()))
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    if target.id == user.id:
        raise HTTPException(status_code=422, detail="Cannot follow yourself")
    existing = await db.scalar(
        select(Friendship).where(
            Friendship.follower_id == user.id, Friendship.following_id == target.id
        )
    )
    if not existing:
        db.add(Friendship(follower_id=user.id, following_id=target.id))
        await db.commit()
    return {"status": "following"}


@router.get("/leaderboard", response_model=list[LeaderboardEntry])
async def leaderboard(db: DbSession, user: CurrentUser) -> list[LeaderboardEntry]:
    friendships = list(
        await db.scalars(
            select(Friendship).where(
                or_(Friendship.follower_id == user.id, Friendship.following_id == user.id)
            )
        )
    )
    peer_ids = {user.id}
    for friendship in friendships:
        peer_ids.add(friendship.follower_id)
        peer_ids.add(friendship.following_id)
    users = {item.id: item for item in await db.scalars(select(User).where(User.id.in_(peer_ids)))}
    habits = list(
        await db.scalars(
            select(Habit).options(selectinload(Habit.check_ins)).where(Habit.owner_id.in_(peer_ids))
        )
    )
    since = date.today() - timedelta(days=29)
    stats: list[tuple[int, float, int]] = []
    for user_id in peer_ids:
        owned = [habit for habit in habits if habit.owner_id == user_id and habit.is_active]
        completed = sum(
            item.completed for habit in owned for item in habit.check_ins if item.day >= since
        )
        planned = sum(max(1, round(30 * habit.target_days_per_week / 7)) for habit in owned)
        stats.append((user_id, completed / planned if planned else 0, completed))
    stats.sort(key=lambda item: (item[1], item[2]), reverse=True)
    return [
        LeaderboardEntry(
            user_id=user_id,
            display_name=users[user_id].display_name,
            completion_rate=round(rate, 3),
            completed_last_30_days=completed,
            rank=index,
        )
        for index, (user_id, rate, completed) in enumerate(stats, start=1)
    ]

