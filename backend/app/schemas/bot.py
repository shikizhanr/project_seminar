from pydantic import BaseModel


class TelegramLinkRequest(BaseModel):
    chat_id: int


class TelegramLinkResponse(BaseModel):
    chat_id: int

    model_config = {"from_attributes": True}

