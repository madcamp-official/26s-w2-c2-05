import os
import secrets

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlmodel import Session

from ..deps import get_db, get_current_user
from ..models import GithubOAuthState, User
from .. import github_client

router = APIRouter(prefix="/auth/github")

FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")


@router.get("/login")
def github_login(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> dict:
    state = secrets.token_urlsafe(32)
    db.add(GithubOAuthState(state=state, user_id=user.user_id))
    db.commit()
    return {"authorize_url": github_client.build_authorize_url(state)}


@router.get("/status")
def github_status(user: User = Depends(get_current_user)) -> dict:
    return {"connected": user.github_token_encrypted is not None}


@router.post("/disconnect")
def github_disconnect(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> dict:
    user.github_token_encrypted = None
    db.add(user)
    db.commit()
    return {"connected": False}


@router.get("/callback")
def github_callback(code: str, state: str, db: Session = Depends(get_db)):
    oauth_state = db.get(GithubOAuthState, state)
    if oauth_state is None:
        raise HTTPException(status_code=400, detail="유효하지 않은 요청입니다")
    user = db.get(User, oauth_state.user_id)
    db.delete(oauth_state)
    db.commit()

    try:
        token = github_client.exchange_code_for_token(code)
    except ValueError:
        return RedirectResponse(f"{FRONTEND_URL}/?github=error")

    user.github_token_encrypted = github_client.encrypt_token(token)
    db.add(user)
    db.commit()
    return RedirectResponse(f"{FRONTEND_URL}/?github=connected")
