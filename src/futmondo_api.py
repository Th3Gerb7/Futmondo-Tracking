import requests
from src.config import FUTMONDO_EMAIL, FUTMONDO_PASSWORD, CHAMPIONSHIP_ID

BASE_URL = "https://api.futmondo.com"
DEFAULT_HEADERS = {
    "Content-Type": "application/json",
    "Origin": "https://app.futmondo.com",
    "Referer": "https://app.futmondo.com/",
    "User-Agent": "Mozilla/5.0",
}


def _make_body(token: str | None, userid: str, query: dict) -> dict:
    return {
        "header": {"token": token or "null", "userid": userid},
        "query": query,
        "answer": {},
    }


def login() -> tuple[str, str]:
    url = f"{BASE_URL}/5/login/with_mail"
    body = _make_body(None, "", {
        "mail": FUTMONDO_EMAIL,
        "pwd": FUTMONDO_PASSWORD,
    })

    resp = requests.post(url, headers=DEFAULT_HEADERS, json=body, timeout=30)
    resp.raise_for_status()

    data = resp.json()
    mobile = data["answer"]["mobile"]
    token = mobile["token"]
    userid = mobile["userid"]

    if not token or not userid:
        raise ValueError("Login OK pero token/userid vacíos")

    return token, userid


def get_teams(token: str, userid: str) -> list[dict]:
    url = f"{BASE_URL}/2/championship/teams"
    body = _make_body(token, userid, {"championshipId": CHAMPIONSHIP_ID})

    resp = requests.post(url, headers=DEFAULT_HEADERS, json=body, timeout=30)
    resp.raise_for_status()

    return resp.json()["answer"]["teams"]


def get_pressroom(token: str, userid: str) -> list[dict]:
    url = f"{BASE_URL}/1/locker/pressroom"
    body = _make_body(token, userid, {
        "championshipId": CHAMPIONSHIP_ID,
        "from": "",
    })

    resp = requests.post(url, headers=DEFAULT_HEADERS, json=body, timeout=30)
    resp.raise_for_status()

    return resp.json()["answer"]["news"]
