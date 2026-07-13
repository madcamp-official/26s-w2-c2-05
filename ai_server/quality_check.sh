#!/bin/bash
# /analyze 수동 품질 확인용 스크립트 (T-08, 2026-07-13).
# hook 유형(도구별로 다르게)과 claude_md 유형을 섞어서 event/matcher 정확도
# 및 reason 문장 품질이 안정적인지 확인한다. 프롬프트(gemini_client.py의
# SYSTEM_INSTRUCTION)나 모델을 바꿀 때마다 재사용 — 서버가 localhost:8001에
# 떠 있어야 함 (`/usr/bin/python3 -m uvicorn ai_server.main:app --reload
# --port 8001`, repo 루트에서). RPD를 5건 소비하니 남은 한도 확인 후 실행.
# 패턴을 추가/변경하려면 아래 patterns 배열만 수정하면 됨.

set -e

patterns=(
  ".ts 파일 수정 후 항상 npm test를 5번 반복 실행함"
  "빌드 스크립트 실행 후 항상 dist 폴더를 rm -rf로 정리하는 패턴이 4회 반복됨"
  "새 React 컴포넌트 파일을 만들 때마다 항상 대응하는 테스트 파일도 같이 생성하는 패턴이 5회 반복됨"
  "탭 대신 스페이스로 들여쓰기를 써달라고 사용자가 3번 이상 정정함"
  "커밋 메시지를 항상 한국어로 써달라고 여러 번 요청함"
)

i=1
for p in "${patterns[@]}"; do
  echo "=== 케이스 $i: $p ==="
  curl -s -X POST http://localhost:8001/analyze \
    -H "Content-Type: application/json" \
    -d "{\"pattern_summary\": \"$p\"}"
  echo ""
  echo ""
  i=$((i+1))
done
