import asyncio
from datetime import date, timedelta

from sqlalchemy import select

from backend.app.core.database import SessionLocal, init_db
from backend.app.core.security import hash_password
from backend.app.models.habit import Habit, HabitCheckIn
from backend.app.models.user import User


async def seed() -> None:
    await init_db()
    async with SessionLocal() as db:
        user = await db.scalar(select(User).where(User.email == "demo@example.com"))
        if not user:
            user = User(
                email="demo@example.com",
                display_name="Демо",
                password_hash=hash_password("demo-password"),
                timezone="Asia/Yekaterinburg",
            )
            db.add(user)
            await db.flush()
        existing = list(await db.scalars(select(Habit).where(Habit.owner_id == user.id)))
        if not existing:
            habits = [
                Habit(
                    owner_id=user.id,
                    title="Прогулка 20 минут",
                    color="#22C55E",
                    target_days_per_week=7,
                ),
                Habit(
                    owner_id=user.id,
                    title="Читать 10 страниц",
                    color="#625BF6",
                    target_days_per_week=5,
                ),
                Habit(
                    owner_id=user.id,
                    title="Без телефона после 22:00",
                    color="#F59E0B",
                    target_days_per_week=6,
                    difficulty=4,
                ),
            ]
            db.add_all(habits)
            await db.flush()
            for offset in range(1, 15):
                for index, habit in enumerate(habits):
                    if (offset + index) % (4 + index) != 0:
                        db.add(
                            HabitCheckIn(
                                habit_id=habit.id,
                                day=date.today() - timedelta(days=offset),
                                completed=True,
                                mood=4,
                            )
                        )
        await db.commit()
    print("Demo user: demo@example.com / demo-password")


if __name__ == "__main__":
    asyncio.run(seed())
