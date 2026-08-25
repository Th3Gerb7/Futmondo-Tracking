"""Automatic recovery of missing PressRoom transactions.

Cross-references SquadPlayers against PressRoom: if a player is in a user's
squad but has no purchase transaction, creates one automatically using the
BuyPrice from SquadPlayers. This handles the case where the Futmondo API's
non-deterministic pagination drops old transactions.
"""

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


def recover() -> int:
    """Detect and insert missing purchase transactions. Returns count inserted."""
    db = get_client()
    now = datetime.now(MADRID).strftime("%Y-%m-%d %H:%M:%S")

    squad = db.table("SquadPlayers").select("*").execute().data or []
    purchases = (
        db.table("PressRoom")
        .select("IDTransaction, FootballPlayer, IDPurchaseUser, PurchaseAmount")
        .not_.is_("IDPurchaseUser", "null")
        .execute()
        .data
        or []
    )

    purchases_by_user: dict[str, set[str]] = {}
    for tx in purchases:
        uid = tx.get("IDPurchaseUser", "")
        pname = _normalize(tx.get("FootballPlayer"))
        if uid and pname:
            purchases_by_user.setdefault(uid, set()).add(pname)

    rows = []
    for player in squad:
        uid = player.get("IDUser", "")
        pname = _normalize(player.get("PlayerName"))
        buy_price = player.get("BuyPrice") or 0

        if not uid or not pname or buy_price == 0:
            continue

        user_purchases = purchases_by_user.get(uid, set())
        if pname in user_purchases:
            continue

        player_id = player.get("PlayerId", "unknown")
        tx_id = f"auto_{player_id}_{uid}"

        rows.append({
            "IDTransaction": tx_id,
            "TransactionDate": now,
            "FootballPlayer": player.get("PlayerName", ""),
            "IDPurchaseUser": uid,
            "IDSalesUser": None,
            "PurchaseAmount": -abs(buy_price),
            "SalesAmount": 0,
            "TransactionType": "Compra",
            "UpdatedAt": now,
        })

    if not rows:
        print("0 faltantes")
        return 0

    existing = db.table("PressRoom").select("IDTransaction").execute().data or []
    existing_ids = {r["IDTransaction"] for r in existing}
    new_rows = [r for r in rows if r["IDTransaction"] not in existing_ids]

    if new_rows:
        db.table("PressRoom").insert(new_rows).execute()
        for r in new_rows:
            print(f"  [AUTO] {r['FootballPlayer']} → {r['IDPurchaseUser']} ({r['PurchaseAmount']:,.0f})")

    print(f"{len(new_rows)} recuperados automáticamente" + (f" ({len(rows) - len(new_rows)} ya existían)" if len(rows) > len(new_rows) else ""))
    return len(new_rows)


if __name__ == "__main__":
    import sys
    try:
        count = recover()
        print(f"\nTotal: {count} transacciones recuperadas.")
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
