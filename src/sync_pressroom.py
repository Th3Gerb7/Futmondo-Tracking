import unicodedata
from datetime import datetime
import pytz
from src.supabase_client import get_client


def _normalize(name: str | None) -> str:
    if not name:
        return ""
    nfkd = unicodedata.normalize("NFKD", name)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()


def _match_user(name: str, users: list[dict]) -> str | None:
    norm = _normalize(name)
    for u in users:
        if _normalize(u["NameInGame"]) == norm:
            return u["IDUser"]
    return None


def sync(news: list[dict]) -> None:
    db = get_client()
    now = datetime.now(pytz.timezone("Europe/Madrid")).strftime("%Y-%m-%d %H:%M:%S")

    users = db.table("LeagueUsers").select("IDUser, NameInGame").execute().data or []

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
        created = item.get("created")

        buyer_id = _match_user(buyer_name, users)
        seller_id = _match_user(seller_name, users)

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
            "TransactionDate": created,
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

    existing = db.table("PressRoom").select("IDTransaction").execute().data or []
    db_ids = {r["IDTransaction"] for r in existing}
    removed = db_ids - api_ids

    if removed:
        for tid in removed:
            db.table("PressRoom").delete().eq("IDTransaction", tid).execute()

    print(f"  PressRoom: {len(rows)} upserted, {len(removed)} eliminadas")
