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


def _names_match(a: str, b: str) -> bool:
    """Fuzzy match two player names. Handles API inconsistencies like
    'Mario Soriano' vs 'M. Soriano', 'Bellerin' vs 'Héctor Bellerín'."""
    na = _normalize(a)
    nb = _normalize(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    ta = set(na.replace(".", "").split())
    tb = set(nb.replace(".", "").split())
    if ta and tb and (ta <= tb or tb <= ta):
        return True
    if len(na) > 3 and len(nb) > 3 and (na in nb or nb in na):
        return True
    # Last-token match: surnames are the most reliable part
    la = na.split()[-1]
    lb = nb.split()[-1]
    if len(la) > 3 and len(lb) > 3 and la == lb:
        # Same surname — check first token isn't contradictory
        fa = na.split()[0]
        fb = nb.split()[0]
        if fa == fb or fa[0] == fb[0]:
            return True
    return False


def _has_purchase(player_name: str, purchase_names: list[str]) -> bool:
    for pn in purchase_names:
        if _names_match(player_name, pn):
            return True
    return False


def cleanup_duplicates() -> int:
    """Remove auto-recovered transactions that duplicate real API transactions."""
    db = get_client()

    all_tx = (
        db.table("PressRoom")
        .select("IDTransaction, FootballPlayer, IDPurchaseUser, PurchaseAmount")
        .not_.is_("IDPurchaseUser", "null")
        .execute()
        .data
        or []
    )

    auto_txs = [t for t in all_tx if t["IDTransaction"].startswith("auto_")]
    real_txs = [t for t in all_tx if not t["IDTransaction"].startswith("auto_")]

    if not auto_txs:
        return 0

    real_by_user: dict[str, list[str]] = {}
    for tx in real_txs:
        uid = tx.get("IDPurchaseUser", "")
        pname = tx.get("FootballPlayer", "")
        if uid and pname:
            real_by_user.setdefault(uid, []).append(pname)

    duplicates = []
    for atx in auto_txs:
        uid = atx.get("IDPurchaseUser", "")
        pname = atx.get("FootballPlayer", "")
        if uid and pname and _has_purchase(pname, real_by_user.get(uid, [])):
            duplicates.append(atx)

    if duplicates:
        for d in duplicates:
            db.table("PressRoom").delete().eq("IDTransaction", d["IDTransaction"]).execute()
            print(f"  [CLEANUP] Duplicado eliminado: {d['FootballPlayer']} ({d['IDTransaction']}, {d['PurchaseAmount']:,.0f})")

    return len(duplicates)


def recover() -> int:
    """Detect and insert missing purchase transactions. Returns count inserted."""
    db = get_client()
    now = datetime.now(MADRID).strftime("%Y-%m-%d %H:%M:%S")

    cleaned = cleanup_duplicates()
    if cleaned:
        print(f"  {cleaned} duplicados auto-recuperados eliminados")

    squad = db.table("SquadPlayers").select("*").execute().data or []
    purchases = (
        db.table("PressRoom")
        .select("IDTransaction, FootballPlayer, IDPurchaseUser, PurchaseAmount")
        .not_.is_("IDPurchaseUser", "null")
        .execute()
        .data
        or []
    )

    purchases_by_user: dict[str, list[str]] = {}
    for tx in purchases:
        uid = tx.get("IDPurchaseUser", "")
        pname = tx.get("FootballPlayer", "")
        if uid and pname:
            purchases_by_user.setdefault(uid, []).append(pname)

    rows = []
    for player in squad:
        uid = player.get("IDUser", "")
        player_name = player.get("PlayerName", "")
        buy_price = player.get("BuyPrice") or 0

        if not uid or not player_name or buy_price == 0:
            continue

        if _has_purchase(player_name, purchases_by_user.get(uid, [])):
            continue

        player_id = player.get("PlayerId", "unknown")
        tx_id = f"auto_{player_id}_{uid}"

        rows.append({
            "IDTransaction": tx_id,
            "TransactionDate": now,
            "FootballPlayer": player_name,
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
