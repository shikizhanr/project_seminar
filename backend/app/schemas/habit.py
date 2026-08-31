from datetime import date, datetime, time

from pydantic import BaseModel, Field, field_validator


class HabitCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=1000)
    color: str = "#6366F1"
    target_days_per_week: int = Field(default=7, ge=1, le=7)
    reminder_time: time | None = None
    difficulty: int = Field(default=2, ge=1, le=5)

    @field_validator("color")
    @classmethod
    def validate_color(cls, value: str) -> str:
        if len(value) != 7 or not value.startswith("#"):
            raise ValueError("color must be a hex value such as #6366F1")
        int(value[1:], 16)
        return value.upper()


class HabitUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    color: str | None = None
    target_days_per_week: int | None = Field(default=None, ge=1, le=7)
    reminder_time: time | None = None
    difficulty: int | None = Field(default=None, ge=1, le=5)
    is_active: bool | None = None


class HabitResponse(BaseModel):
    id: int
    title: str
    description: str
    color: str
    target_days_per_week: int
    reminder_time: time | None
    difficulty: int
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TodayHabitResponse(HabitResponse):
    completed_today: bool


class CheckInCreate(BaseModel):
    day: date = Field(default_factory=date.today)
    completed: bool = True
    mood: int | None = Field(default=None, ge=1, le=5)
    effort: int | None = Field(default=None, ge=1, le=5)
    note: str = Field(default="", max_length=500)


class CheckInResponse(BaseModel):
    id: int
    habit_id: int
    day: date
    completed: bool
    mood: int | None
    effort: int | None
    note: str
    predicted_risk: float | None

    model_config = {"from_attributes": True}
