from fastapi import APIRouter, Depends
from pydantic import BaseModel

from .. import ai_client
from ..deps import get_current_user
from ..models import User

router = APIRouter()


class QuotaOut(BaseModel):
    remaining_rpd: int


@router.get("/quota", response_model=QuotaOut)
async def get_quota(user: User = Depends(get_current_user)) -> QuotaOut:
    remaining_rpd = await ai_client.get_remaining_rpd()
    return QuotaOut(remaining_rpd=remaining_rpd)
