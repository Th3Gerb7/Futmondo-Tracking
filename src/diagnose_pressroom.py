import sys
import json
from collections import Counter
from src import futmondo_api


def diagnose():
    print("=== Diagnóstico de PressRoom (campos API) ===\n")

    print("[1] Login...")
    token, userid = futmondo_api.login()
    print("    OK\n")

    print("[2] Descargando pressroom de la API...")
    news = futmondo_api.get_pressroom(token, userid)
    print(f"    Total transacciones: {len(news)}\n")

    all_keys = Counter()
    for item in news:
        for k in item.keys():
            all_keys[k] += 1

    print("[3] Campos presentes en las transacciones:")
    for key, count in all_keys.most_common():
        print(f"    {key:30s} → {count:5d}/{len(news)}")

    print(f"\n[4] Primeras 5 transacciones (JSON completo):")
    for i, item in enumerate(news[:5]):
        safe = {}
        for k, v in item.items():
            if isinstance(v, dict):
                safe[k] = {sk: sv for sk, sv in v.items() if sk != "img"}
            else:
                safe[k] = v
        print(f"\n  --- Transacción {i+1} ---")
        print(f"  {json.dumps(safe, indent=4, ensure_ascii=False, default=str)}")

    print(f"\n[5] Análisis de campos monetarios:")
    price_fields = set()
    for item in news:
        for k, v in item.items():
            if isinstance(v, (int, float)) and v != 0 and k not in ("__v",):
                price_fields.add(k)
        if isinstance(item.get("_buyer"), dict):
            for k, v in item["_buyer"].items():
                if isinstance(v, (int, float)) and v != 0:
                    price_fields.add(f"_buyer.{k}")
        if isinstance(item.get("_seller"), dict):
            for k, v in item["_seller"].items():
                if isinstance(v, (int, float)) and v != 0:
                    price_fields.add(f"_seller.{k}")

    print(f"    Campos con valores numéricos: {sorted(price_fields)}")

    has_both = [item for item in news if item.get("_buyer") and item.get("_seller")]
    print(f"\n[6] Transacciones Compra-Venta (buyer + seller): {len(has_both)}")
    for item in has_both[:10]:
        player = item.get("_player", {}).get("name", "?")
        price = item.get("price", 0)
        buyer = item.get("_buyer", {}).get("name", "?")
        seller = item.get("_seller", {}).get("name", "?")
        clause = item.get("clause", item.get("clausePrice", item.get("clauseAmount", "N/A")))
        extra_fields = {k: v for k, v in item.items()
                        if k not in ("_id", "created", "_player", "_buyer", "_seller",
                                     "price", "__v", "t", "typ", "styp")}
        print(f"    {player:25s} | price={price:>12,} | buyer={buyer[:15]:15s} | seller={seller[:15]:15s} | clause={clause} | extra={list(extra_fields.keys())}")

    only_buyer = [item for item in news if item.get("_buyer") and not item.get("_seller")]
    only_seller = [item for item in news if item.get("_seller") and not item.get("_buyer")]
    print(f"\n[7] Compras (solo buyer): {len(only_buyer)}")
    print(f"    Ventas (solo seller): {len(only_seller)}")

    for item in only_seller[:5]:
        player = item.get("_player", {}).get("name", "?")
        price = item.get("price", 0)
        seller = item.get("_seller", {}).get("name", "?")
        extra = {k: v for k, v in item.items()
                 if k not in ("_id", "created", "_player", "_buyer", "_seller",
                              "price", "__v", "t", "typ", "styp")}
        print(f"    VENTA: {player:25s} | price={price:>12,} | seller={seller[:20]:20s} | extra_keys={list(extra.keys())}")

    print(f"\n[8] Verificar si hay campo 'clause' o similar:")
    clause_fields = set()
    for item in news:
        for k in item.keys():
            kl = k.lower()
            if any(term in kl for term in ("clause", "comis", "tax", "fee", "cost", "sell", "buy", "amount")):
                clause_fields.add(k)
    print(f"    Campos encontrados: {sorted(clause_fields) if clause_fields else 'Ninguno'}")

    print("\n=== Fin diagnóstico pressroom ===")


if __name__ == "__main__":
    try:
        diagnose()
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        sys.exit(1)
