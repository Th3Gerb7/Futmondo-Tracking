import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from src.config import FUTMONDO_EMAIL, FUTMONDO_PASSWORD, CHAMPIONSHIP_ID

BASE_URL = "https://api.futmondo.com"

_session: requests.Session | None = None


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({
            "Content-Type": "application/json",
            "Origin": "https://app.futmondo.com",
            "Referer": "https://app.futmondo.com/",
            "User-Agent": "Mozilla/5.0",
        })
        retry = Retry(
            total=3, backoff_factor=1,
            status_forcelist=[502, 503, 504],
            allowed_methods=frozenset(["POST"]),
        )
        _session.mount("https://", HTTPAdapter(max_retries=retry))
    return _session


def _post(path: str, token: str | None, userid: str, query: dict) -> dict:
    body = {
        "header": {"token": token or "null", "userid": userid},
        "query": query,
        "answer": {},
    }
    resp = _get_session().post(f"{BASE_URL}{path}", json=body, timeout=30)
    resp.raise_for_status()
    answer = resp.json().get("answer", {})
    if answer.get("error"):
        raise RuntimeError(f"API error: {answer.get('code', 'unknown')}")
    return answer


def login() -> tuple[str, str]:
    answer = _post("/5/login/with_mail", None, "", {
        "mail": FUTMONDO_EMAIL,
        "pwd": FUTMONDO_PASSWORD,
    })

    mobile = answer.get("mobile")
    if not mobile:
        raise RuntimeError(
            f"Login fallido — la API no devolvió datos de sesión. "
            f"Código: {answer.get('code', 'sin código')}. "
            f"Verifica FUTMONDO_EMAIL y FUTMONDO_PASSWORD en los secrets de GitHub."
        )

    token = mobile.get("token")
    userid = mobile.get("userid")
    if not token or not userid:
        raise RuntimeError("Login OK pero token/userid vacíos en la respuesta")

    return token, userid


def get_teams(token: str, userid: str) -> list[dict]:
    answer = _post("/2/championship/teams", token, userid, {
        "championshipId": CHAMPIONSHIP_ID,
    })
    teams = answer.get("teams")
    if teams is None:
        raise RuntimeError(f"No se obtuvieron equipos: {answer.get('code', 'unknown')}")
    return teams


def _paginate_pressroom(token: str, userid: str) -> list[dict]:
    """Single pagination pass through the pressroom API."""
    all_news = []
    seen_ids: set[str] = set()
    cursor = ""

    while True:
        answer = _post("/1/locker/pressroom", token, userid, {
            "championshipId": CHAMPIONSHIP_ID,
            "from": cursor,
        })
        news = answer.get("news")
        if news is None:
            raise RuntimeError(f"No se obtuvieron transacciones: {answer.get('code', 'unknown')}")
        if not news:
            break

        new_count = 0
        for item in news:
            tx_id = item.get("_id", "")
            if tx_id and tx_id not in seen_ids:
                seen_ids.add(tx_id)
                all_news.append(item)
                new_count += 1

        last_id = news[-1].get("_id", "")
        if new_count == 0 or not last_id or last_id == cursor:
            break
        cursor = last_id

    return all_news


def get_pressroom(token: str, userid: str, passes: int = 5) -> list[dict]:
    """Fetch pressroom with multiple passes to maximize coverage.

    The API's cursor pagination is non-deterministic and may return
    different subsets on each call. Multiple passes with a union of
    results reduces the chance of missing transactions.
    """
    import time

    merged: dict[str, dict] = {}

    for i in range(passes):
        batch = _paginate_pressroom(token, userid)
        new = 0
        for item in batch:
            tx_id = item.get("_id", "")
            if tx_id and tx_id not in merged:
                merged[tx_id] = item
                new += 1
        if i > 0 and new > 0:
            print(f"  [pressroom pass {i+1}] {new} transacciones nuevas encontradas")
        if i < passes - 1:
            time.sleep(2)

    return list(merged.values())


def get_news(token: str, userid: str) -> list[dict]:
    all_news = []
    seen_ids: set[str] = set()
    cursor = ""

    while True:
        answer = _post("/2/locker/news", token, userid, {
            "championshipId": CHAMPIONSHIP_ID,
            "from": cursor,
        })
        news = answer.get("news")
        if news is None:
            raise RuntimeError(f"No se obtuvieron news: {answer.get('code', 'unknown')}")
        if not news:
            break

        new_count = 0
        for item in news:
            nid = item.get("_id", "")
            if nid and nid not in seen_ids:
                seen_ids.add(nid)
                all_news.append(item)
                new_count += 1

        last_id = news[-1].get("_id", "")
        if new_count == 0 or not last_id or last_id == cursor:
            break
        cursor = last_id

    return all_news


def get_roster(token: str, userid: str, userteam_id: str) -> list[dict]:
    body = {
        "header": {"token": token, "userid": userid},
        "query": {
            "userteamId": userteam_id,
            "championshipId": CHAMPIONSHIP_ID,
        },
        "answer": {},
    }
    resp = _get_session().post(f"{BASE_URL}/1/userteam/roster", json=body, timeout=30)
    resp.raise_for_status()
    answer = resp.json().get("answer", [])
    if not isinstance(answer, list):
        raise RuntimeError(f"Roster inesperado para {userteam_id}")
    return answer
