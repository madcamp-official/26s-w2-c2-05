import json

import numpy as np
from sqlmodel import Session as DBSession, select

from .models import GroupMembership, RecommendationGroup

PROMOTION_THRESHOLD = 2  # DESIGN.md D4: 실제 팀 규모(2인팀)에 맞춤
SIMILARITY_THRESHOLD = 0.85


def normalize_command(command: str) -> str:
    return " ".join(command.strip().lower().split())


def cosine_similarity(a: list[float], b: list[float]) -> float:
    va, vb = np.array(a), np.array(b)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)


def match_hook_candidate(
    db: DBSession,
    project_id: str,
    user_id: int,
    session_id: str,
    event: str,
    matcher: str,
    command: str,
    reason: str,
    confidence: str,
) -> RecommendationGroup:
    normalized = normalize_command(command)
    existing = db.exec(
        select(RecommendationGroup).where(
            RecommendationGroup.project_id == project_id,
            RecommendationGroup.type == "hook",
            RecommendationGroup.event == event,
            RecommendationGroup.matcher == matcher,
            RecommendationGroup.representative_text == normalized,
        )
    ).first()
    group = _join_or_create_group(
        db, existing, project_id, "hook", normalized, user_id, session_id,
        command, reason, confidence,
    )
    if existing is None:
        group.event = event
        group.matcher = matcher
        db.add(group)
        db.commit()
        db.refresh(group)
    return group


def match_claude_md_candidate(
    db: DBSession,
    project_id: str,
    user_id: int,
    session_id: str,
    suggested_text: str,
    vector: list[float],
    reason: str,
    confidence: str,
) -> RecommendationGroup:
    candidates = db.exec(
        select(RecommendationGroup).where(
            RecommendationGroup.project_id == project_id,
            RecommendationGroup.type == "claude_md",
        )
    ).all()

    best_match: RecommendationGroup | None = None
    best_score = 0.0
    for group in candidates:
        if group.representative_vector is None:
            continue
        group_vector = json.loads(group.representative_vector)
        score = cosine_similarity(vector, group_vector)
        if score > best_score:
            best_score = score
            best_match = group

    existing = best_match if best_score >= SIMILARITY_THRESHOLD else None
    group = _join_or_create_group(
        db, existing, project_id, "claude_md", suggested_text, user_id,
        session_id, suggested_text, reason, confidence,
    )
    if existing is None:
        group.representative_vector = json.dumps(vector)
        db.add(group)
        db.commit()
        db.refresh(group)
    return group


def _join_or_create_group(
    db: DBSession,
    existing: RecommendationGroup | None,
    project_id: str,
    type_: str,
    representative_text: str,
    user_id: int,
    session_id: str,
    original_text: str,
    reason: str,
    confidence: str,
) -> RecommendationGroup:
    if existing is None:
        group = RecommendationGroup(
            project_id=project_id, type=type_, representative_text=representative_text
        )
        db.add(group)
        db.commit()
        db.refresh(group)
    else:
        group = existing

    prior_membership = db.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group.id,
            GroupMembership.user_id == user_id,
        )
    ).first()
    if prior_membership is None:
        db.add(
            GroupMembership(
                group_id=group.id,
                user_id=user_id,
                session_id=session_id,
                original_text=original_text,
                reason=reason,
                confidence=confidence,
            )
        )
    else:
        prior_membership.session_id = session_id
        prior_membership.original_text = original_text
        prior_membership.reason = reason
        prior_membership.confidence = confidence
        db.add(prior_membership)
    db.commit()

    member_count = len(
        db.exec(
            select(GroupMembership).where(GroupMembership.group_id == group.id)
        ).all()
    )
    group.promoted = member_count >= PROMOTION_THRESHOLD
    db.add(group)
    db.commit()
    db.refresh(group)
    return group
