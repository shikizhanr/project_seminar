from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from backend.app.api.deps import CurrentUser, DbSession
from backend.app.models.user import TelegramLink
from backend.app.schemas.bot import TelegramLinkRequest, TelegramLinkResponse

router = APIRouter(prefix="/bot", tags=["bot"])


@router.put("/link", response_model=TelegramLinkResponse)
async def link_chat(
    payload: TelegramLinkRequest, db: DbSession, user: CurrentUser
) -> TelegramLink:
    conflicting = await db.scalar(
        select(TelegramLink).where(
            TelegramLink.chat_id == payload.chat_id, TelegramLink.user_id != user.id
        )
    )
    if conflicting:
        raise HTTPException(status_code=409, detail="Telegram chat is linked to another account")
    link = await db.scalar(select(TelegramLink).where(TelegramLink.user_id == user.id))
    if link:
        link.chat_id = payload.chat_id
    else:
        link = TelegramLink(user_id=user.id, chat_id=payload.chat_id)
        db.add(link)
    await db.commit()
    await db.refresh(link)
    return link


@router.get("/link", response_model=TelegramLinkResponse)
async def get_link(db: DbSession, user: CurrentUser) -> TelegramLink:
    link = await db.scalar(select(TelegramLink).where(TelegramLink.user_id == user.id))
    if not link:
        raise HTTPException(status_code=404, detail="Telegram chat is not linked")
    return link

