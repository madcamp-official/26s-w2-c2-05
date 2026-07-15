#!/usr/bin/env bash
# KAIST VM에서 cron으로 주기 실행: origin/main에 새 커밋이 있으면 pull 후
# 의존성 재설치 + 서비스 재시작. GitHub Actions가 이 VM의 SSH(22)로 접근하지
# 못해서(방화벽) push 기반 배포 대신 VM이 직접 당겨오는 방식으로 전환함.
set -euo pipefail

REPO_DIR="$HOME/week2"
LOG_FILE="$REPO_DIR/deploy.log"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >>"$LOG_FILE"; }

cd "$REPO_DIR"

git fetch origin main

LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)

if [[ "$LOCAL" == "$REMOTE" ]]; then
  exit 0
fi

log "새 커밋 감지: $LOCAL -> $REMOTE"

git pull origin main

source ai_server/.venv/bin/activate
pip install -r ai_server/requirements.txt
deactivate

source web-server/.venv/bin/activate
pip install -r web-server/requirements.txt
deactivate

(cd frontend && npm ci && npm run build)

sudo systemctl restart ai-server web-server frontend

log "배포 완료: $REMOTE"
