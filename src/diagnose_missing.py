"""Diagnose missing PressRoom transactions by cross-referencing squad purchases
against recorded transactions for a specific user."""

import sys
from src.supabase_client import get_client

MY_USER_ID = "610386f21a3e3f2c97060c03"


def diagnose():
    db = get_client()

    print("=== Diagnóstico: Transacciones faltantes para German Fdez ===\n")

    # 1. Get all squad players for the user
    squad = db.table("SquadPlayers").select("*").eq("IDUser", MY_USER_ID).execute().data or []
    print(f"[1] Jugadores en plantilla: {len(squad)}")
    for p in sorted(squad, key=lambda x: -(x.get("BuyPrice") or 0)):
        name = p.get("PlayerName", "?")
        buy = p.get("BuyPrice", 0) or 0
        val = p.get("CurrentValue", 0) or 0
        print(f"    {name:25s}  compra: {buy:>14,.0f}  valor: {val:>14,.0f}")
    print()

    # 2. Get all PressRoom purchases for the user
    purchases = db.table("PressRoom").select("*").eq("IDPurchaseUser", MY_USER_ID).execute().data or []
    print(f"[2] Compras registradas en PressRoom: {len(purchases)}")
    total_purchases = 0
    purchase_players = {}
    for tx in sorted(purchases, key=lambda x: x.get("TransactionDate", "")):
        player = tx.get("FootballPlayer", "?")
        amount = tx.get("PurchaseAmount", 0) or 0
        date = (tx.get("TransactionDate") or "?")[:10]
        tx_type = tx.get("TransactionType", "?")
        total_purchases += amount
        purchase_players[player] = purchase_players.get(player, 0) + amount
        print(f"    {date} | {player:25s} | {amount:>14,.0f} | {tx_type}")
    print(f"\n    Total compras: {total_purchases:,.0f}")
    print()

    # 3. Get all PressRoom sales for the user
    sales = db.table("PressRoom").select("*").eq("IDSalesUser", MY_USER_ID).execute().data or []
    print(f"[3] Ventas registradas en PressRoom: {len(sales)}")
    total_sales = 0
    for tx in sorted(sales, key=lambda x: x.get("TransactionDate", "")):
        player = tx.get("FootballPlayer", "?")
        amount = tx.get("SalesAmount", 0) or 0
        date = (tx.get("TransactionDate") or "?")[:10]
        total_sales += amount
        print(f"    {date} | {player:25s} | {amount:>14,.0f}")
    print(f"\n    Total ventas: {total_sales:,.0f}")
    print()

    # 4. MoneyEvents
    events = db.table("MoneyEvents").select("*").eq("IDUser", MY_USER_ID).execute().data or []
    total_money = sum(e.get("Amount", 0) or 0 for e in events)
    print(f"[4] MoneyEvents: {len(events)} → {total_money:,.0f}\n")

    # 5. Balance calculation
    balance = 200_000_000 + total_purchases + total_sales + total_money
    print(f"[5] Balance calculado: 200,000,000 + ({total_purchases:,.0f}) + ({total_sales:,.0f}) + ({total_money:,.0f})")
    print(f"    = {balance:,.0f}")
    print(f"    Balance esperado (user): ~18,341,729")
    print(f"    Diferencia: {balance - 18_341_729:,.0f}")
    print()

    # 6. Cross-reference: squad players NOT in purchase history
    squad_names = {p.get("PlayerName", "").lower().strip() for p in squad}
    purchased_names = {name.lower().strip() for name in purchase_players.keys()}

    missing_purchase = []
    for p in squad:
        pname = (p.get("PlayerName") or "").lower().strip()
        if pname and pname not in purchased_names:
            missing_purchase.append(p)

    print(f"[6] Jugadores en plantilla SIN compra registrada: {len(missing_purchase)}")
    for p in sorted(missing_purchase, key=lambda x: -(x.get("BuyPrice") or 0)):
        name = p.get("PlayerName", "?")
        buy = p.get("BuyPrice", 0) or 0
        print(f"    {name:25s}  BuyPrice: {buy:>14,.0f}")
    print()

    # 7. Players bought AND sold (no longer in squad) - can't cross-reference these
    sold_players = {tx.get("FootballPlayer", "").lower().strip() for tx in sales}
    bought_and_sold = purchased_names & sold_players
    if bought_and_sold:
        print(f"[7] Jugadores comprados Y vendidos (ya no en plantilla): {len(bought_and_sold)}")
        for name in sorted(bought_and_sold):
            buy_total = purchase_players.get(name, 0)
            print(f"    {name:25s}")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(diagnose())
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        sys.exit(1)
