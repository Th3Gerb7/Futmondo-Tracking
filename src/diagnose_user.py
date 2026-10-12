"""Diagnose a specific user's recent transactions."""

import sys
from src.supabase_client import get_client


def diagnose_user(user_id: str):
    db = get_client()

    user = db.table("LeagueUsers").select("*").eq("IDUser", user_id).execute().data
    if not user:
        print(f"Usuario {user_id} no encontrado")
        return 1
    u = user[0]
    print(f"=== {u['UserName']} ({u['NameInGame']}) — {user_id} ===")
    print(f"ValorEquipo: {u.get('ActualValueTeam', 0):,.0f}\n")

    buys = (db.table("PressRoom")
            .select("*")
            .eq("IDPurchaseUser", user_id)
            .order("TransactionDate", desc=True)
            .execute().data or [])

    sells = (db.table("PressRoom")
             .select("*")
             .eq("IDSalesUser", user_id)
             .order("TransactionDate", desc=True)
             .execute().data or [])

    print(f"--- ÚLTIMAS 15 VENTAS (de {len(sells)} totales) ---")
    for t in sells[:15]:
        date = (t.get("TransactionDate") or "")[:10]
        player = t.get("FootballPlayer", "???")
        amount = t.get("SalesAmount", 0) or 0
        ttype = t.get("TransactionType", "")
        buyer_id = t.get("IDPurchaseUser", "")
        buyer_label = f" → comprador: {buyer_id}" if buyer_id else " → vendido a Futmondo"
        print(f"  {date} | {player:25s} | {amount:>15,.0f} | {ttype}{buyer_label}")

    print(f"\n--- ÚLTIMAS 15 COMPRAS (de {len(buys)} totales) ---")
    for t in buys[:15]:
        date = (t.get("TransactionDate") or "")[:10]
        player = t.get("FootballPlayer", "???")
        amount = t.get("PurchaseAmount", 0) or 0
        ttype = t.get("TransactionType", "")
        seller_id = t.get("IDSalesUser", "")
        seller_label = f" → vendedor: {seller_id}" if seller_id else " → comprado a Futmondo"
        print(f"  {date} | {player:25s} | {amount:>15,.0f} | {ttype}{seller_label}")

    money = (db.table("MoneyEvents")
             .select("*")
             .eq("IDUser", user_id)
             .order("EventDate", desc=True)
             .execute().data or [])

    total_money = sum((m.get("Amount") or 0) for m in money)
    total_buys = sum((t.get("PurchaseAmount") or 0) for t in buys)
    total_sells = sum((t.get("SalesAmount") or 0) for t in sells)
    balance = 200_000_000 + total_buys + total_sells + total_money

    print(f"\n--- RESUMEN ---")
    print(f"  Compras totales:  {len(buys):3d} txs → {total_buys:>15,.0f}")
    print(f"  Ventas totales:   {len(sells):3d} txs → {total_sells:>15,.0f}")
    print(f"  MoneyEvents:      {len(money):3d} evt → {total_money:>15,.0f}")
    print(f"  Balance:          {balance:>15,.0f}")
    print(f"  ValorEquipo:      {u.get('ActualValueTeam', 0):>15,.0f}")

    team_val = float(u.get("ActualValueTeam", 0) or 0)
    puja_max = balance + team_val * 0.50
    print(f"  PujaMaxima:       {puja_max:>15,.0f}")

    return 0


if __name__ == "__main__":
    uid = sys.argv[1] if len(sys.argv) > 1 else "5751f75a476eb299232a7a8f"
    try:
        sys.exit(diagnose_user(uid))
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
