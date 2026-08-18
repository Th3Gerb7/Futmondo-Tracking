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


def _build_user_lookup(users: list[dict]) -> dict[str, str]:
    return {_normalize(u["NameInGame"]): u["IDUser"] for u in users if u.get("NameInGame")}


def sync(news: list[dict]) -> None:
    db = get_client()
    now = datetime.now(MADRID).strftime("%Y-%m-%d %H:%M:%S")

    users = db.table("LeagueUsers").select("IDUser, NameInGame").execute().data or []
    lookup = _build_user_lookup(users)

    api_ids = set()
    rows = []

    for item in news:
        tx_id = item.get("_id")
        if not tx_id:
            continue

        api_ids.add(tx_id)

        player = item.get("_player", {}).get("name")
        buyer_name = item.get("_buyer", {}).get("name")
        seller_name = item.get("_seller", {}).get("name")
        price = item.get("price", 0)

        buyer_id = lookup.get(_normalize(buyer_name))
        seller_id = lookup.get(_normalize(seller_name))

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
