# Futmondo Tracking

Sistema de tracking para una liga de fantasy football en Futmondo (plataforma española).
Sincroniza datos de la API de Futmondo a Supabase y muestra un dashboard web.

## Restricciones de seguridad

- Las credenciales viven SOLO en GitHub Secrets: `SUPABASE_URL`, `SUPABASE_KEY`, `FUTMONDO_EMAIL`, `FUTMONDO_PASSWORD`, `CHAMPIONSHIP_ID`.
- NUNCA pasar credenciales por chat ni guardarlas en variables de entorno de sesiones remotas.
- El proxy de Claude Code Remote bloquea HTTPS directo a Supabase. Toda consulta de datos debe ejecutarse via GitHub Actions (workflows).
- La `SUPABASE_KEY` en GitHub Secrets es la **service_role** (ignora RLS, lectura+escritura). La key en `docs/index.html` es la **anon** (solo lectura vía RLS).

## Arquitectura general

```
Futmondo API ──→ GitHub Actions (sync) ──→ Supabase (PostgreSQL)
                                               ↓
                                          docs/index.html (dashboard, lee con anon key)
```

- **Fuente de datos**: API REST de Futmondo (`api.futmondo.com`), autenticación por email/password.
- **Base de datos**: Supabase (PostgreSQL con API REST).
- **Orquestación**: GitHub Actions — cron cada 12h + manual via workflow_dispatch.
- **Frontend**: HTML estático en `docs/index.html`, consulta Supabase directamente con anon key.

## Estructura del código

```
src/
├── config.py              # Carga env vars, valida que existan
├── supabase_client.py     # Singleton del cliente Supabase (service_role)
├── futmondo_api.py        # Cliente API Futmondo (login, teams, pressroom, news, roster)
├── main.py                # Orquestador del sync (6 pasos secuenciales)
├── sync_teams.py          # Sync equipos → LeagueUsers
├── sync_squads.py         # Sync plantillas → SquadPlayers
├── sync_pressroom.py      # Sync transacciones → PressRoom
├── sync_money_events.py   # Sync repartos de dinero → MoneyEvents
├── verify_pressroom.py    # Verificación API vs Supabase
├── audit_balance.py       # Auditoría de balances (calculado vs vista SQL)
├── auto_recover.py        # Auto-recuperación de compras faltantes (cross-ref SquadPlayers vs PressRoom)
├── diagnose_pujas.py      # Análisis de pujas máximas y capacidad de puja
├── diagnose_*.py          # Otros diagnósticos (news, balance, matching, pagination, championship)
```

## Flujo del sync (`src/main.py`)

Se ejecuta como `python -m src.main`. Pasos secuenciales:

1. **Login** → `futmondo_api.login()` → obtiene `(token, userid)`
2. **Token → Supabase** → Guarda el token de sesión en tabla `AccessToken`
3. **Equipos** → `futmondo_api.get_teams()` → `sync_teams.sync()` → upsert en `LeagueUsers`
4. **Plantillas** → Por cada equipo, `futmondo_api.get_roster()` → `sync_squads.sync()` → upsert en `SquadPlayers`
5. **Transacciones** → `futmondo_api.get_pressroom()` → `sync_pressroom.sync()` → upsert en `PressRoom`
6. **Repartos dinero** → `futmondo_api.get_news()` → `sync_money_events.sync()` → insert en `MoneyEvents`
7. **Auto-recuperación** → `auto_recover.recover()` → cross-ref SquadPlayers vs PressRoom, inserta compras faltantes

Todos los syncs hacen upsert de datos actuales (PressRoom nunca elimina registros existentes, MoneyEvents solo inserta nuevos). El paso 7 detecta automáticamente jugadores en plantilla sin transacción de compra y los recupera usando el BuyPrice de SquadPlayers.

## API de Futmondo (`src/futmondo_api.py`)

Base URL: `https://api.futmondo.com`

Todas las llamadas son POST con esta estructura:
```json
{
  "header": {"token": "<session_token>", "userid": "<user_id>"},
  "query": { ... },
  "answer": {}
}
```

### Endpoints

| Endpoint | Función | Retorna |
|----------|---------|---------|
| `/5/login/with_mail` | Login con email/password | `answer.mobile.{token, userid}` |
| `/2/championship/teams` | Equipos de la liga | `answer.teams[]` con `{userid, _id (teamid), teamname, name, teamValue}` |
| `/1/locker/pressroom` | Transacciones del mercado | `answer.news[]` con `{_id, _player.name, _buyer.{_id, name}, _seller.{_id, name}, price, created}` |
| `/2/locker/news` | Noticias (incluye repartos dinero) | `answer.news[]` — se filtra `styp == "customize"` para MoneyEvents |
| `/1/userteam/roster` | Plantilla de un equipo | `answer[]` con `{id, name, role, team, value, buyPrice}` |

### Paginación

Pressroom y News usan paginación por cursor: `query.from = last_id`. Se itera hasta que no hay más resultados o se repite el cursor. Se usa `seen_ids` para deduplicar.

## Tablas en Supabase

### `LeagueUsers`
Usuarios/managers de la liga.

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `IDUser` | VARCHAR(50) PK | ID del usuario en Futmondo (estable, nunca cambia) |
| `UserName` | VARCHAR(100) | Nombre real del usuario (`team.name` de la API) |
| `NameInGame` | VARCHAR(100) | Nombre del equipo en el juego (`team.teamname`). PUEDE CAMBIAR |
| `ActualValueTeam` | NUMERIC(15,2) | Valor total del equipo según la API |
| `UpdatedAt` | TIMESTAMPTZ | Timestamp del último sync |

**Importante**: `NameInGame` cambia cuando un usuario renombra su equipo. `IDUser` es el identificador estable para trazabilidad.

### `PressRoom`
Transacciones del mercado (compras a Futmondo, ventas a Futmondo, y compra-ventas entre usuarios).

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `IDTransaction` | VARCHAR(50) PK | `_id` de la transacción en la API |
| `TransactionDate` | TIMESTAMPTZ | Fecha de la transacción (`created`) |
| `FootballPlayer` | VARCHAR(100) | Nombre del jugador |
| `IDPurchaseUser` | VARCHAR(50) FK | ID del comprador (NULL si compra Futmondo) |
| `IDSalesUser` | VARCHAR(50) FK | ID del vendedor (NULL si vende a Futmondo) |
| `PurchaseAmount` | NUMERIC(15,2) | Precio como negativo (lo que paga el comprador) |
| `SalesAmount` | NUMERIC(15,2) | Precio como positivo (lo que recibe el vendedor) |
| `TransactionType` | VARCHAR(30) | `Compra`, `Venta`, `Compra-Venta`, o `Desconocida` |
| `UpdatedAt` | TIMESTAMPTZ | Timestamp del último sync |

**Tipos de transacción**:
- `Compra-Venta`: Entre dos usuarios (ambos IDPurchaseUser e IDSalesUser presentes)
- `Compra`: Usuario compra del mercado de Futmondo (solo IDPurchaseUser)
- `Venta`: Usuario vende al mercado de Futmondo (solo IDSalesUser)
- `Desconocida`: No se pudo identificar ningún usuario

**Matching de usuarios en PressRoom** (`sync_pressroom.py`):
- Prioridad 1: Team ID → se mapea `_buyer._id` / `_seller._id` (team ID de la API) al `userid` via la tabla de equipos. Este método es ESTABLE y fiable.
- Prioridad 2 (fallback): Name matching → normalización Unicode + casefold del nombre. Solo se usa si el team ID no resuelve.

### `MoneyEvents`
Repartos de dinero por jornada, ranking, MVP, dream team, etc.

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `IDEvent` | VARCHAR(50) PK | `_id` del evento |
| `EventDate` | TIMESTAMPTZ | Fecha del evento |
| `IDUser` | VARCHAR(50) FK | ID del usuario que recibe el dinero |
| `Amount` | NUMERIC(15,2) | Cantidad recibida (siempre positiva) |
| `EventType` | VARCHAR(50) | Siempre `customize` (filtrado de `styp`) |
| `Description` | TEXT | Texto descriptivo del evento |
| `UpdatedAt` | TIMESTAMPTZ | Timestamp del último sync |

**Matching de usuarios en MoneyEvents** (`sync_money_events.py`):
- La API de news (`/2/locker/news`) NO proporciona IDs de usuario/equipo para eventos customize.
- Se usa SOLO name matching: `data.name` (nombre del equipo) se normaliza y busca en `LeagueUsers.NameInGame`.
- Hay un matching parcial (startswith) como fallback.
- `HISTORICAL_NAMES` es un dict hardcodeado para usuarios que cambiaron de nombre y no hacen match.
- Solo inserta eventos NUEVOS (no hace upsert ni elimina existentes).

### `SquadPlayers`
Plantillas de todos los equipos de la liga.

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `IDUser` | VARCHAR(50) | ID del dueño del jugador |
| `PlayerId` | VARCHAR(50) | ID del jugador en Futmondo |
| `PlayerName` | VARCHAR(100) | Nombre del jugador |
| `Position` | VARCHAR(10) | Posición (por/def/cen/del) |
| `RealTeam` | VARCHAR(50) | Equipo real de LaLiga |
| `CurrentValue` | NUMERIC(15,2) | Valor actual de mercado |
| `BuyPrice` | NUMERIC(15,2) | Precio al que se compró |
| `UpdatedAt` | TIMESTAMPTZ | Timestamp del último sync |

PK compuesta: `(IDUser, PlayerId)`.

### `AccessToken`
Token de sesión de Futmondo (para uso interno).

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `ID` | VARCHAR(100) PK | Siempre `futmondo_session` |
| `AccessToken` | TEXT | Token de sesión actual |
| `UpdatedAt` | TIMESTAMPTZ | Cuándo se renovó |

### Vista `UserDashboard`
Vista SQL calculada (no es tabla). Muestra el estado financiero de cada usuario.

| Columna | Cálculo |
|---------|---------|
| `Balance` | `200,000,000 + total_purchases + total_sales + total_money` |
| `ValorEquipo` | `ActualValueTeam` (de LeagueUsers) |
| `PujaMaxima` | `CEIL(Balance + ValorEquipo * 0.50)` |

**Fórmulas clave**:
- `INITIAL_BUDGET = 200,000,000` (presupuesto inicial de la liga)
- `PurchaseAmount` es NEGATIVO (resta del balance)
- `SalesAmount` es POSITIVO (suma al balance)
- `MoneyEvents.Amount` es POSITIVO (siempre suma)
- La vista usa `UNION ALL` para manejar correctamente transacciones `Compra-Venta` donde un usuario es comprador Y otro es vendedor

**Impacto de vender un jugador a su CurrentValue**:
- Balance sube en CurrentValue
- ValorEquipo baja en CurrentValue
- Ganancia neta en PujaMaxima = +50% del CurrentValue

## RLS (Row Level Security)

- `LeagueUsers`, `PressRoom`, `MoneyEvents`: anon tiene SELECT (lectura pública para el dashboard).
- `AccessToken`: sin policy → bloqueado para anon (solo service_role).
- service_role (usada en GitHub Actions) ignora RLS automáticamente.

## GitHub Actions Workflows

### `sync.yml` — Sync principal
- **Cron**: 06:30 y 21:30 UTC (08:30 y 23:30 Madrid en verano)
- **Manual**: workflow_dispatch
- **Ejecuta**: `python -m src.main` (los 6 pasos)
- **Timeout**: 5 minutos

### `pujas.yml` — Análisis de pujas
- **Solo manual**: workflow_dispatch
- **Ejecuta**: `python -m src.diagnose_pujas`
- **Output**: Ranking de pujas máximas, detalle por usuario con impacto de venta de cada jugador
- **Timeout**: 3 minutos

### `verify.yml` — Verificación + Auditoría
- **Solo manual**: workflow_dispatch (con opción de ejecutar sync primero)
- **Ejecuta**: `verify_pressroom` + `audit_balance`
- **Output**: Comparación API vs DB, verificación de balances calculados vs vista SQL

### `diagnose.yml` — Diagnósticos completos
- **Solo manual**: workflow_dispatch
- **Ejecuta**: Todos los scripts `diagnose_*.py` secuencialmente
- **Timeout**: 5 minutos

## Dashboard web (`docs/index.html`)

HTML estático que consulta Supabase directamente con la anon key (solo lectura).

Constantes embebidas:
- `SUPABASE_URL`: URL del proyecto Supabase
- `SUPABASE_KEY`: Anon key (publishable, solo lectura vía RLS)
- `MY_USER_ID = '610386f21a3e3f2c97060c03'`: ID del dueño del proyecto
- `INITIAL_BUDGET = 200000000`: Presupuesto inicial

Funcionalidades:
- Stat cards: Balance personal, Puja Máxima, Posición en ranking
- Tabla de clasificación por balance con plantilla expandible (click en fila)
- Últimas 15 operaciones del mercado
- Dark/light theme toggle
- Auto-refresh cada 5 minutos

## Dependencias (`requirements.txt`)

```
supabase>=2.0.0
requests>=2.31.0
python-dotenv>=1.0.0
pytz>=2024.1
```

## Cómo ejecutar workflows desde Claude Code

Dado que el proxy bloquea conexiones directas a Supabase, para obtener datos frescos:

1. **Lanzar sync**: Trigger `sync.yml` via GitHub Actions API/MCP
2. **Lanzar análisis**: Trigger `pujas.yml`, `verify.yml`, o `diagnose.yml`
3. **Leer resultados**: Obtener job logs del workflow completado via GitHub Actions API/MCP
4. **Logs largos**: Los logs de pujas/diagnose pueden ser >50KB. Guardar en archivo y usar grep/python para extraer secciones relevantes. Usar `html.unescape()` para decodificar entities.

## Convenciones del código

- Timezone: `Europe/Madrid` para timestamps
- Todos los imports de Supabase van via `src.supabase_client.get_client()`
- Los scripts diagnóstico se ejecutan como `python -m src.diagnose_<nombre>`
- Cada sync module tiene una función `sync()` que recibe datos de la API y hace upsert/delete en Supabase
- Todos los syncs imprimen resumen: `"X upserted, Y eliminados"`
