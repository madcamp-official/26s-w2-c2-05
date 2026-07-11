import base64
import os
import re
import httpx
from cryptography.fernet import Fernet

GITHUB_CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET", "")
GITHUB_OAUTH_REDIRECT_URI = os.environ.get(
    "GITHUB_OAUTH_REDIRECT_URI", "http://localhost:8000/auth/github/callback"
)
ENCRYPTION_KEY = os.environ.get("ENCRYPTION_KEY")
if not ENCRYPTION_KEY:
    raise RuntimeError("ENCRYPTION_KEY 환경변수가 설정되지 않았습니다 (.env 확인)")

_fernet = Fernet(ENCRYPTION_KEY.encode())


def encrypt_token(token: str) -> str:
    return _fernet.encrypt(token.encode()).decode()


def decrypt_token(token: str) -> str:
    return _fernet.decrypt(token.encode()).decode()


def normalize_repo(repo: str) -> str:
    repo = repo.strip()
    repo = re.sub(r"^(https?://)?(www\.)?github\.com/", "", repo)
    repo = repo.rstrip("/")
    if repo.endswith(".git"):
        repo = repo[: -len(".git")]
    return repo


def build_authorize_url(state: str) -> str:
    return (
        "https://github.com/login/oauth/authorize"
        f"?client_id={GITHUB_CLIENT_ID}"
        f"&redirect_uri={GITHUB_OAUTH_REDIRECT_URI}"
        "&scope=repo"
        f"&state={state}"
    )


def exchange_code_for_token(code: str) -> str:
    resp = httpx.post(
        "https://github.com/login/oauth/access_token",
        headers={"Accept": "application/json"},
        data={
            "client_id": GITHUB_CLIENT_ID,
            "client_secret": GITHUB_CLIENT_SECRET,
            "code": code,
            "redirect_uri": GITHUB_OAUTH_REDIRECT_URI,
        },
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    if "access_token" not in data:
        raise ValueError(data.get("error_description", "GitHub 토큰 교환에 실패했습니다"))
    return data["access_token"]


def push_file(token: str, repo: str, path: str, content: str, message: str) -> None:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    url = f"https://api.github.com/repos/{repo}/contents/{path}"

    get_resp = httpx.get(url, headers=headers, timeout=10)
    sha = get_resp.json().get("sha") if get_resp.status_code == 200 else None

    payload = {
        "message": message,
        "content": base64.b64encode(content.encode()).decode(),
    }
    if sha:
        payload["sha"] = sha

    put_resp = httpx.put(url, headers=headers, json=payload, timeout=10)
    if put_resp.status_code not in (200, 201):
        raise ValueError(put_resp.json().get("message", "GitHub push에 실패했습니다"))
