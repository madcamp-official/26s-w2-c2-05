import json

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlmodel import Session as DBSession, select

from .. import ai_client
from ..deps import get_current_user, get_db
from ..matching import match_claude_md_candidate, match_hook_candidate
from ..models import (
    GroupMembership,
    PersonalRecommendation,
    Project,
    ProjectMember,
    RecommendationGroup,
    Session as SessionModel,
    User,
)
from ..preprocessing import extract_pattern_summary

router = APIRouter()

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10MB


class RecommendationOut(BaseModel):
    type: str
    payload: dict


class TeamGroupOut(BaseModel):
    id: str
    type: str
    representative_text: str
    affected_members: int
    promoted: bool


class UploadSessionResponse(BaseModel):
    session_id: str
    status: str
    personal_recommendations: list[RecommendationOut]
    updated_team_groups: list[TeamGroupOut] = []


@router.post("/projects/{project_id}/sessions", response_model=UploadSessionResponse)
async def upload_session(
    project_id: str,
    file: UploadFile = File(...),
    db: DBSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> UploadSessionResponse:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다")
    if db.get(ProjectMember, (project_id, user.user_id)) is None:
        raise HTTPException(status_code=403, detail="접근 권한이 없습니다")

    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="파일이 너무 큽니다 (10MB 초과)")
    jsonl_text = raw.decode("utf-8", errors="ignore")

    pattern_summary = extract_pattern_summary(jsonl_text)

    if pattern_summary is None:
        _replace_prior_session(db, project_id, user.user_id)
        session = SessionModel(
            project_id=project_id, user_id=user.user_id, status="no_patterns"
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return UploadSessionResponse(
            session_id=session.id,
            status="no_patterns",
            personal_recommendations=[],
            updated_team_groups=[],
        )

    try:
        result = await ai_client.analyze(pattern_summary)
    except ai_client.GeminiQuotaExceeded:
        raise HTTPException(status_code=429, detail="오늘의 요청 한도를 모두 사용했습니다")
    except httpx.HTTPStatusError:
        raise HTTPException(status_code=503, detail="잠시 후 다시 시도해주세요")

    _replace_prior_session(db, project_id, user.user_id)
    session = SessionModel(project_id=project_id, user_id=user.user_id, status="processed")
    db.add(session)
    db.commit()
    db.refresh(session)

    personal_out: list[RecommendationOut] = []
    updated_groups: list[RecommendationGroup] = []
    for candidate in result["candidates"]:
        db.add(
            PersonalRecommendation(
                session_id=session.id,
                user_id=user.user_id,
                type=candidate["type"],
                payload=json.dumps(candidate, ensure_ascii=False),
            )
        )
        db.commit()
        personal_out.append(RecommendationOut(type=candidate["type"], payload=candidate))

        if candidate["type"] == "hook":
            group = match_hook_candidate(
                db, project_id, user.user_id, session.id,
                candidate["event"], candidate["matcher"], candidate["command"],
                candidate["reason"], candidate["confidence"],
            )
            updated_groups.append(group)
        elif candidate["type"] == "claude_md":
            vector = await ai_client.embed(candidate["suggested_text"])
            group = match_claude_md_candidate(
                db, project_id, user.user_id, session.id,
                candidate["suggested_text"], vector,
                candidate["reason"], candidate["confidence"],
            )
            updated_groups.append(group)

    team_groups_out = [
        TeamGroupOut(
            id=g.id,
            type=g.type,
            representative_text=g.representative_text,
            affected_members=_count_members(db, g.id),
            promoted=g.promoted,
        )
        for g in updated_groups
    ]

    return UploadSessionResponse(
        session_id=session.id,
        status="processed",
        personal_recommendations=personal_out,
        updated_team_groups=team_groups_out,
    )


def _count_members(db: DBSession, group_id: str) -> int:
    return len(
        db.exec(
            select(GroupMembership).where(GroupMembership.group_id == group_id)
        ).all()
    )


class EvidenceOut(BaseModel):
    user_id: int
    original_text: str


class TeamRecommendationOut(BaseModel):
    id: str
    type: str
    representative_text: str
    affected_members: int
    evidence: list[EvidenceOut]


@router.get(
    "/projects/{project_id}/recommendations/team",
    response_model=list[TeamRecommendationOut],
)
def get_team_recommendations(
    project_id: str, db: DBSession = Depends(get_db), user: User = Depends(get_current_user)
) -> list[TeamRecommendationOut]:
    if db.get(ProjectMember, (project_id, user.user_id)) is None:
        raise HTTPException(status_code=403, detail="접근 권한이 없습니다")
    groups = db.exec(
        select(RecommendationGroup).where(
            RecommendationGroup.project_id == project_id,
            RecommendationGroup.promoted == True,  # noqa: E712
        )
    ).all()

    out = []
    for group in groups:
        memberships = db.exec(
            select(GroupMembership).where(GroupMembership.group_id == group.id)
        ).all()
        out.append(
            TeamRecommendationOut(
                id=group.id,
                type=group.type,
                representative_text=group.representative_text,
                affected_members=len(memberships),
                evidence=[
                    EvidenceOut(user_id=m.user_id, original_text=m.original_text)
                    for m in memberships
                ],
            )
        )
    return out


@router.get(
    "/projects/{project_id}/recommendations/me", response_model=list[RecommendationOut]
)
def get_my_recommendations(
    project_id: str, db: DBSession = Depends(get_db), user: User = Depends(get_current_user)
) -> list[RecommendationOut]:
    if db.get(ProjectMember, (project_id, user.user_id)) is None:
        raise HTTPException(status_code=403, detail="접근 권한이 없습니다")
    recs = db.exec(
        select(PersonalRecommendation).where(
            PersonalRecommendation.user_id == user.user_id,
            PersonalRecommendation.session_id.in_(
                select(SessionModel.id).where(SessionModel.project_id == project_id)
            ),
        )
    ).all()
    return [
        RecommendationOut(type=r.type, payload=json.loads(r.payload)) for r in recs
    ]


def _replace_prior_session(db: DBSession, project_id: str, user_id: int) -> None:
    old_session = db.exec(
        select(SessionModel).where(
            SessionModel.project_id == project_id, SessionModel.user_id == user_id
        )
    ).first()
    if old_session is None:
        return
    old_recs = db.exec(
        select(PersonalRecommendation).where(
            PersonalRecommendation.session_id == old_session.id
        )
    ).all()
    for rec in old_recs:
        db.delete(rec)
    db.delete(old_session)
    db.commit()
