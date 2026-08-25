import unicodedata
from datetime import datetime
import pytz
from src.supabase_client import get_client

MADRID = pytz.timezone("Europe/Madrid")


def _normalize(name: str | None) -> str:
    if not name:
        return ""
    nfkd = unicodedata.normalize("NFKD", name)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()


def _build_name_lookup(users: list[dict]) -> dict[str, str]:
    return {_normalize(u["NameInGame"]): u["IDUser"] for u in users if u.get("NameInGame")}


def _build_teamid_lookup(teams: list[dict]) -> dict[str, str]:
    """Map team _id (userteam) → userid from the API teams list."""
    return {t["_id"]: t["userid"] for t in teams if t.get("_id") and t.get("userid")}


def sync(news: list[dict], teams: list[dict] | None = None) -> None:
    db = get_client()
    now = datetime.now(MADRID).strftime("%Y-%m-%d %H:%M:%S")

    users = db.table("LeagueUsers").select("IDUser, NameInGame").execute().data or []
    name_lookup = _build_name_lookup(users)
    teamid_lookup = _build_teamid_lookup(teams) if teams else {}

    api_ids = set()
    rows = []

    for item in news:
        tx_id = item.get("_id")
        if not tx_id:
            continue

        api_ids.add(tx_id)

        player = item.get("_player", {}).get("name")
        buyer_obj = item.get("_buyer", {})
        seller_obj = item.get("_seller", {})
        buyer_name = buyer_obj.get("name")
        seller_name = seller_obj.get("name")
        price = item.get("price", 0)

        buyer_id = teamid_lookup.get(buyer_obj.get("_id", ""))
        if not buyer_id:
            buyer_id = name_lookup.get(_normalize(buyer_name))
        seller_id = teamid_lookup.get(seller_obj.get("_id", ""))
        if not seller_id:
            seller_id = name_lookup.get(_normalize(seller_name))

        if buyer_id and seller_id:
            tx_type = "Compra-Venta"
        elif buyer_id:
            tx_type = "Compra"
        elif seller_id:
            tx_type = "Venta"
        else:
            tx_type = "Desconocida"

        rows.append({
            "IDTransaction": tx_id,
            "TransactionDate": item.get("created"),
            "FootballPlayer": player,
            "IDPurchaseUser": buyer_id,
            "IDSalesUser": seller_id,
            "PurchaseAmount": -price if buyer_id else 0,
            "SalesAmount": price if seller_id else 0,
            "TransactionType": tx_type,
            "UpdatedAt": now,
        })

    if rows:
        db.table("PressRoom").upsert(rows).execute()

    print(f"{len(rows)} upserted")
