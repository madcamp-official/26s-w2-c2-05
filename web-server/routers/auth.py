from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from pydantic import BaseModel

from ..deps import get_db
from ..models import User
from ..auth import hash_password, verify_password, create_access_token

router = APIRouter()


class SignupRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/signup", response_model=TokenResponse)
def signup(req: SignupRequest, db: Session = Depends(get_db)) -> TokenResponse:
    existing = db.exec(select(User).where(User.username == req.username)).first()
    if existing is not None:
        raise HTTPException(status_code=400, detail="이미 사용 중인 아이디입니다")
    user = User(username=req.username, password=hash_password(req.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(user.user_id)
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.exec(select(User).where(User.username == req.username)).first()
    if user is None or not verify_password(req.password, user.password):
        raise HTTPException(status_code=401, detail="아이디 또는 비밀번호가 올바르지 않습니다")
    token = create_access_token(user.user_id)
    return TokenResponse(access_token=token)
