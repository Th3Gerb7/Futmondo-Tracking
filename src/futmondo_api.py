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
        retry = Retry(total=2, backoff_factor=1, status_forcelist=[502, 503, 504])
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


def get_pressroom(token: str, userid: str) -> list[dict]:
    answer = _post("/1/locker/pressroom", token, userid, {
        "championshipId": CHAMPIONSHIP_ID,
        "from": "",
    })
    news = answer.get("news")
    if news is None:
        raise RuntimeError(f"No se obtuvieron transacciones: {answer.get('code', 'unknown')}")
    return news
