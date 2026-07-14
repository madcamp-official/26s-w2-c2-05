const API_BASE = "/api";

export async function getQuota(): Promise<{ remaining_rpd: number }> {
  const token = localStorage.getItem("access_token");
  const res = await fetch(`${API_BASE}/quota`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error("남은 요청 수를 불러오지 못했습니다");
  return res.json();
}
