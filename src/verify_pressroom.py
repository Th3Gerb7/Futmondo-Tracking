import sys
from datetime import datetime
import pytz
from src.supabase_client import get_client
from src import futmondo_api

MADRID = pytz.timezone("Europe/Madrid")


def verify():
    print("=== Verificación PressRoom ===\n")
    db = get_client()

    # 1. Login y obtener datos de la API
    print("[1] Login en Futmondo...")
    token, userid = futmondo_api.login()
    print("    OK\n")

    print("[2] Descargando pressroom de la API...")
    api_news = futmondo_api.get_pressroom(token, userid)
    api_ids = {item["_id"] for item in api_news if item.get("_id")}
    print(f"    Transacciones en API: {len(api_ids)}\n")

    # 2. Datos en Supabase
    print("[3] Consultando PressRoom en Supabase...")
    db_rows = db.table("PressRoom").select("*").execute().data or []
    db_ids = {r["IDTransaction"] for r in db_rows}
    print(f"    Registros en Supabase: {len(db_rows)}\n")

    # 3. Comparar API vs DB
    print("[4] Comparación API vs Supabase:")
    missing_in_db = api_ids - db_ids
    extra_in_db = db_ids - api_ids
    print(f"    Coinciden: {len(api_ids & db_ids)}")
    print(f"    Faltan en Supabase: {len(missing_in_db)}")
    print(f"    Sobrantes en Supabase: {len(extra_in_db)}")
    if missing_in_db:
        print(f"    IDs faltantes: {list(missing_in_db)[:10]}")
    if extra_in_db:
        print(f"    IDs sobrantes: {list(extra_in_db)[:10]}")
    print()

    # 4. Verificar tipos de transacción
    print("[5] Distribución por tipo de transacción:")
    types = {}
    for r in db_rows:
        t = r.get("TransactionType", "Sin tipo")
        types[t] = types.get(t, 0) + 1
    for t, count in sorted(types.items(), key=lambda x: -x[1]):
        print(f"    {t}: {count}")
    print()

    # 5. Verificar campos nulos
    print("[6] Calidad de datos:")
    no_player = sum(1 for r in db_rows if not r.get("FootballPlayer"))
    no_buyer = sum(1 for r in db_rows if not r.get("IDPurchaseUser"))
    no_seller = sum(1 for r in db_rows if not r.get("IDSalesUser"))
    no_date = sum(1 for r in db_rows if not r.get("TransactionDate"))
    print(f"    Sin jugador: {no_player}")
    print(f"    Sin comprador (IDPurchaseUser): {no_buyer}")
    print(f"    Sin vendedor (IDSalesUser): {no_seller}")
    print(f"    Sin fecha: {no_date}")
    print()

    # 6. Usuarios de la liga
    print("[7] LeagueUsers:")
    users = db.table("LeagueUsers").select("IDUser, NameInGame").execute().data or []
    print(f"    Total usuarios: {len(users)}")
    user_names = [u.get("NameInGame", "?") for u in users]
    print(f"    Nombres: {', '.join(user_names)}")
    print()

    # 7. Últimas 5 transacciones
    print("[8] Últimas 5 transacciones:")
    recent = db.table("PressRoom").select(
        "IDTransaction, TransactionDate, FootballPlayer, TransactionType, PurchaseAmount, SalesAmount"
    ).order("TransactionDate", desc=True).limit(5).execute().data or []
    for r in recent:
        date = r.get("TransactionDate", "?")[:10] if r.get("TransactionDate") else "?"
        player = r.get("FootballPlayer", "?")
        tx_type = r.get("TransactionType", "?")
        amount = r.get("PurchaseAmount") or r.get("SalesAmount") or 0
        print(f"    {date} | {player:20s} | {tx_type:15s} | {amount:>12,.0f}")
    print()

    # 8. Último sync
    print("[9] Último sync (AccessToken):")
    token_row = db.table("AccessToken").select("UpdatedAt").eq("ID", "futmondo_session").execute().data
    if token_row:
        print(f"    Última actualización: {token_row[0].get('UpdatedAt', '?')}")
    else:
        print("    No hay registro de AccessToken")
    print()

    # Resultado final
    ok = len(missing_in_db) == 0 and len(extra_in_db) == 0
    if ok:
        print("RESULTADO: OK - Todos los datos de la API están en Supabase")
    else:
        print("RESULTADO: DESINCRONIZADO - Hay diferencias entre API y Supabase")
        print("  Ejecuta el sync para corregir: python -m src.main")

    return 0 if ok else 1


if __name__ == "__main__":
    try:
        sys.exit(verify())
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        sys.exit(1)
