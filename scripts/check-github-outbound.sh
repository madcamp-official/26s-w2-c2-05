#!/usr/bin/env bash
# KAIST VM에서 실행: web-server가 실제로 호출하는 GitHub 호스트 2개에 대한
# 아웃바운드 연결(DNS + TCP + TLS)이 방화벽에서 허용되는지 확인한다.
# HTTP 상태 코드가 찍히면 연결 자체는 성공(인증 실패인 401/404 등도 OK).
# curl이 타임아웃/에러로 죽으면 그 지점에서 아웃바운드가 막힌 것.

set -u

check() {
  local url="$1"
  echo -n "  $url -> "
  code=$(curl -sS -o /dev/null -w "%{http_code}" --max-time 5 "$url" 2>&1)
  if [[ "$code" =~ ^[0-9]{3}$ ]]; then
    echo "OK (HTTP $code, 도달함)"
  else
    echo "FAIL: $code"
  fi
}

echo "1) OAuth 토큰 교환 엔드포인트 (github_client.py:48)"
check "https://github.com/login/oauth/access_token"

echo "2) GitHub REST API (github_client.py:67, 80)"
check "https://api.github.com/user"

echo
echo "둘 다 OK면 web-server -> GitHub 아웃바운드는 문제 없음."
echo "FAIL이 있으면 KCLOUD 방화벽/보안그룹에서 해당 호스트로의 outbound 443을 열어야 함."
