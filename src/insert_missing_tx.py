"""Insert recovered transactions that were deleted by the old sync_pressroom
delete logic and cannot be recovered from the API.

Idempotent: checks for existing transactions before inserting."""

import sys
from datetime import datetime
import pytz
from src.supabase_client import get_client

MADRID = pytz.timezone("Europe/Madrid")

RECOVERED_TRANSACTIONS = [
    {
        "IDTransaction": "recovered_mario_soriano_purchase",
        "TransactionDate": "2026-08-09T12:00:00.000Z",
        "FootballPlayer": "Mario Soriano",
        "IDPurchaseUser": "610386f21a3e3f2c97060c03",  # German Fdez
        "IDSalesUser": None,
        "PurchaseAmount": -30999777,
        "SalesAmount": 0,
        "TransactionType": "Compra",
    },
    {
        "IDTransaction": "recovered_mourino_purchase_albert",
        "TransactionDate": "2026-08-09T12:00:00.000Z",
        "FootballPlayer": "Mouriño",
        "IDPurchaseUser": "693fe892f495ac343647406e",  # Albert Viladegut
        "IDSalesUser": None,
        "PurchaseAmount": -23406406,
        "SalesAmount": 0,
        "TransactionType": "Compra",
    },
    {
        "IDTransaction": "recovered_bellerin_purchase_ivan",
        "TransactionDate": "2026-08-09T12:00:00.000Z",
        "FootballPlayer": "Bellerin",
        "IDPurchaseUser": "684b04144e95775f1fce5faa",  # Ivan burkiewicz
        "IDSalesUser": None,
        "PurchaseAmount": -13200000,
        "SalesAmount": 0,
        "TransactionType": "Compra",
    },
]


def main():
    db = get_client()
    now = datetime.now(MADRID).strftime("%Y-%m-%d %H:%M:%S")
    inserted = 0

    for tx in RECOVERED_TRANSACTIONS:
        player = tx["FootballPlayer"]
        user_id = tx["IDPurchaseUser"]
        tx_id = tx["IDTransaction"]

        existing = (
            db.table("PressRoom")
            .select("IDTransaction")
            .eq("IDTransaction", tx_id)
            .execute()
            .data
        )
        if existing:
            print(f"[SKIP] {player} ({tx_id}) — already exists")
            continue

        already_purchased = (
            db.table("PressRoom")
            .select("IDTransaction, FootballPlayer, PurchaseAmount")
            .eq("IDPurchaseUser", user_id)
            .ilike("FootballPlayer", f"%{player}%")
            .execute()
            .data
            or []
        )
        if already_purchased:
            print(f"[SKIP] {player} for user {user_id} — purchase already exists:")
            for r in already_purchased:
                print(f"  {r['IDTransaction']} | {r['FootballPlayer']} | {r['PurchaseAmount']}")
            continue

        row = {**tx, "UpdatedAt": now}
        print(f"[INSERT] {player} for user {user_id}: {tx['PurchaseAmount']:,}")
        db.table("PressRoom").insert(row).execute()
        inserted += 1

    print(f"\nInserted {inserted} recovered transaction(s).")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        sys.exit(1)
