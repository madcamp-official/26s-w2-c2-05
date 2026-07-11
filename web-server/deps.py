from typing import Iterator
import jwt
from fastapi import Depends, Header, HTTPException
from sqlmodel import Session
from .db import engine
from .auth import decode_access_token
from .models import User


def get_db() -> Iterator[Session]:
    with Session(engine) as session:
        yield session


def get_current_user(
    authorization: str = Header(None), db: Session = Depends(get_db)
) -> User:
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="인증이 필요합니다")
    token = authorization.removeprefix("Bearer ")
    try:
        user_id = decode_access_token(token)
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다")
    return user
