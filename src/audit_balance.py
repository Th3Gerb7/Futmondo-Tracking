import sys
from src.supabase_client import get_client


def audit():
    db = get_client()

    print("=== Auditoría de Balance ===\n")

    users = db.table("LeagueUsers").select("IDUser, UserName, NameInGame, ActualValueTeam").execute().data or []
    user_map = {u["IDUser"]: u["UserName"] for u in users}

    txs = db.table("PressRoom").select("*").execute().data or []
    money = db.table("MoneyEvents").select("*").execute().data or []
    dashboard = db.table("UserDashboard").select("*").execute().data or []
    dash_map = {d["IDUser"]: d for d in dashboard}

    print(f"Total transacciones PressRoom: {len(txs)}")
    print(f"Total MoneyEvents: {len(money)}")
    print(f"Total usuarios: {len(users)}")
    if money:
        unique_users = {m["IDUser"] for m in money}
        print(f"MoneyEvents IDUser distintos: {unique_users}")
        for m in money[:3]:
            print(f"  Sample: {m}")
    else:
        print("MoneyEvents está VACÍO en la query")
    user_ids_set = {u["IDUser"] for u in users}
    print(f"LeagueUsers IDs: {user_ids_set}\n")

    print("=" * 100)
    for u in users:
        uid = u["IDUser"]
        name = u["UserName"]
        print(f"\n--- {name} ({uid}) ---")

        purchases = [t for t in txs if t.get("IDPurchaseUser") == uid]
        sales = [t for t in txs if t.get("IDSalesUser") == uid]
        my_money = [m for m in money if m.get("IDUser") == uid]

        total_purchase = sum(t.get("PurchaseAmount", 0) or 0 for t in purchases)
        total_sales = sum(t.get("SalesAmount", 0) or 0 for t in sales)
        total_money = sum(m.get("Amount", 0) or 0 for m in my_money)

        calculated_balance = 200_000_000 + total_purchase + total_sales + total_money

        dash = dash_map.get(uid, {})
        view_balance = dash.get("Balance", "N/A")

        print(f"  Compras (como comprador): {len(purchases)} txs → {total_purchase:>15,.0f}")
        print(f"  Ventas  (como vendedor):  {len(sales)} txs → {total_sales:>15,.0f}")
        print(f"  MoneyEvents:              {len(my_money)} evt → {total_money:>15,.0f}")
        print(f"  ---")
        print(f"  Balance calculado: 200.000.000 + ({total_purchase:,.0f}) + ({total_sales:,.0f}) + ({total_money:,.0f})")
        print(f"                   = {calculated_balance:>15,.0f}")
        print(f"  Balance vista SQL: {view_balance:>15,.0f}" if isinstance(view_balance, (int, float)) else f"  Balance vista SQL: {view_balance}")

        if isinstance(view_balance, (int, float)) and abs(calculated_balance - view_balance) > 1:
            print(f"  *** DISCREPANCIA: diferencia de {calculated_balance - view_balance:,.0f} ***")
        else:
            print(f"  OK - coinciden")

        # Detail: Compra-Venta transactions
        cv_as_buyer = [t for t in purchases if t.get("TransactionType") == "Compra-Venta"]
        cv_as_seller = [t for t in sales if t.get("TransactionType") == "Compra-Venta"]
        if cv_as_buyer or cv_as_seller:
            print(f"  Compra-Venta como comprador: {len(cv_as_buyer)}")
            for t in cv_as_buyer:
                print(f"    {t.get('FootballPlayer'):20s} → {t.get('PurchaseAmount', 0):>12,.0f}")
            print(f"  Compra-Venta como vendedor:  {len(cv_as_seller)}")
            for t in cv_as_seller:
                print(f"    {t.get('FootballPlayer'):20s} → {t.get('SalesAmount', 0):>12,.0f}")

    print("\n" + "=" * 100)
    print("\nResumen de discrepancias:")
    discrepancies = 0
    for u in users:
        uid = u["IDUser"]
        purchases = [t for t in txs if t.get("IDPurchaseUser") == uid]
        sales = [t for t in txs if t.get("IDSalesUser") == uid]
        my_money = [m for m in money if m.get("IDUser") == uid]

        total_purchase = sum(t.get("PurchaseAmount", 0) or 0 for t in purchases)
        total_sales = sum(t.get("SalesAmount", 0) or 0 for t in sales)
        total_money = sum(m.get("Amount", 0) or 0 for m in my_money)
        calculated = 200_000_000 + total_purchase + total_sales + total_money

        dash = dash_map.get(uid, {})
        view_bal = dash.get("Balance", 0)

        if isinstance(view_bal, (int, float)) and abs(calculated - view_bal) > 1:
            print(f"  {u['UserName']:30s} | Calculado: {calculated:>15,.0f} | Vista: {view_bal:>15,.0f} | Diff: {calculated - view_bal:>12,.0f}")
            discrepancies += 1

    if discrepancies == 0:
        print("  Ninguna discrepancia encontrada.")
    else:
        print(f"\n  Total: {discrepancies} usuarios con discrepancia.")
        print("  Probable causa: la vista UserDashboard agrupa por COALESCE(IDPurchaseUser, IDSalesUser),")
        print("  lo que pierde las ventas en transacciones Compra-Venta (user-to-user).")


if __name__ == "__main__":
    try:
        audit()
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        sys.exit(1)
