import os
import sys
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
FUTMONDO_EMAIL = os.environ.get("FUTMONDO_EMAIL")
FUTMONDO_PASSWORD = os.environ.get("FUTMONDO_PASSWORD")
CHAMPIONSHIP_ID = os.environ.get("CHAMPIONSHIP_ID")

REQUIRED = {
    "SUPABASE_URL": SUPABASE_URL,
    "SUPABASE_KEY": SUPABASE_KEY,
    "FUTMONDO_EMAIL": FUTMONDO_EMAIL,
    "FUTMONDO_PASSWORD": FUTMONDO_PASSWORD,
    "CHAMPIONSHIP_ID": CHAMPIONSHIP_ID,
}

missing = [k for k, v in REQUIRED.items() if not v]
if missing:
    print(f"ERROR: faltan variables de entorno: {', '.join(missing)}")
    print("Copia .env.example a .env y rellena los valores.")
    sys.exit(1)
