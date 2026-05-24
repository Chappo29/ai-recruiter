from pydantic import BaseModel, Field


class BotStartRequest(BaseModel):
    token: str | None = Field(default=None, min_length=1)


class BotStatusResponse(BaseModel):
    status: str
    has_token: bool
    bot_username: str | None = None


class BotTokenResponse(BaseModel):
    has_token: bool
    masked: str | None = None


class BotActionResponse(BaseModel):
    status: str
