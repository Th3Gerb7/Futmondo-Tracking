"""Insert the missing Mario Soriano purchase transaction that was deleted
by the old sync_pressroom delete logic and cannot be recovered from the API."""

import sys
from datetime import datetime
import pytz
from src.supabase_client import get_client

MADRID = pytz.timezone("Europe/Madrid")

GERMAN_FDEZ_ID = "610386f21a3e3f2c97060c03"

MISSING_TX = {
    "IDTransaction": "recovered_mario_soriano_purchase",
    "TransactionDate": "2026-08-09T12:00:00.000Z",
    "FootballPlayer": "Mario Soriano",
    "IDPurchaseUser": GERMAN_FDEZ_ID,
    "IDSalesUser": None,
    "PurchaseAmount": -30999777,
    "SalesAmount": 0,
    "TransactionType": "Compra",
    "UpdatedAt": datetime.now(MADRID).strftime("%Y-%m-%d %H:%M:%S"),
}


def main():
    db = get_client()

    existing = (
        db.table("PressRoom")
        .select("IDTransaction")
        .eq("IDTransaction", MISSING_TX["IDTransaction"])
        .execute()
        .data
    )
    if existing:
        print("Transaction already exists — skipping insert.")
        return 0

    german_purchases = (
        db.table("PressRoom")
        .select("IDTransaction, FootballPlayer, PurchaseAmount")
        .eq("IDPurchaseUser", GERMAN_FDEZ_ID)
        .ilike("FootballPlayer", "%Mario Soriano%")
        .execute()
        .data
        or []
    )
    if german_purchases:
        print("A Mario Soriano purchase for German Fdez already exists:")
        for r in german_purchases:
            print(f"  {r['IDTransaction']} | {r['FootballPlayer']} | {r['PurchaseAmount']}")
        print("Skipping insert to avoid duplicate.")
        return 0

    print("Inserting missing transaction:")
    for k, v in MISSING_TX.items():
        print(f"  {k}: {v}")

    db.table("PressRoom").insert(MISSING_TX).execute()
    print("\nInsert OK.")

    balance_check = (
        db.table("PressRoom")
        .select("PurchaseAmount")
        .eq("IDPurchaseUser", GERMAN_FDEZ_ID)
        .execute()
        .data
        or []
    )
    total_purchases = sum(r["PurchaseAmount"] or 0 for r in balance_check)

    sales_check = (
        db.table("PressRoom")
        .select("SalesAmount")
        .eq("IDSalesUser", GERMAN_FDEZ_ID)
        .execute()
        .data
        or []
    )
    total_sales = sum(r["SalesAmount"] or 0 for r in sales_check)

    money = (
        db.table("MoneyEvents")
        .select("Amount")
        .eq("IDUser", GERMAN_FDEZ_ID)
        .execute()
        .data
        or []
    )
    total_money = sum(e["Amount"] or 0 for e in money)

    balance = 200_000_000 + total_purchases + total_sales + total_money
    print(f"\nBalance after fix: {balance:,.0f}")
    print(f"Expected:          ~18,341,729")
    print(f"Difference:        {balance - 18_341_729:,.0f}")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        sys.exit(1)
