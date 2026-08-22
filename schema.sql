-- =====================================================
-- FUTMONDO TRACKING - Schema Supabase
-- Ejecutar en: Supabase Dashboard > SQL Editor > Run
-- =====================================================

-- Usuarios de la liga
CREATE TABLE IF NOT EXISTS "LeagueUsers" (
    "IDUser" VARCHAR(50) PRIMARY KEY,
    "UserName" VARCHAR(100),
    "NameInGame" VARCHAR(100),
    "ActualValueTeam" NUMERIC(15,2) DEFAULT 0,
    "UpdatedAt" TIMESTAMPTZ DEFAULT NOW()
);

-- Transacciones (compras del mercado + compra-ventas entre usuarios)
CREATE TABLE IF NOT EXISTS "PressRoom" (
    "IDTransaction" VARCHAR(50) PRIMARY KEY,
    "TransactionDate" TIMESTAMPTZ,
    "FootballPlayer" VARCHAR(100),
    "IDPurchaseUser" VARCHAR(50) REFERENCES "LeagueUsers"("IDUser"),
    "IDSalesUser" VARCHAR(50) REFERENCES "LeagueUsers"("IDUser"),
    "PurchaseAmount" NUMERIC(15,2) DEFAULT 0,
    "SalesAmount" NUMERIC(15,2) DEFAULT 0,
    "TransactionType" VARCHAR(30),
    "UpdatedAt" TIMESTAMPTZ DEFAULT NOW()
);

-- Repartos de dinero (por jornada, ranking, MVP, dream team, etc.)
CREATE TABLE IF NOT EXISTS "MoneyEvents" (
    "IDEvent" VARCHAR(50) PRIMARY KEY,
    "EventDate" TIMESTAMPTZ,
    "IDUser" VARCHAR(50) REFERENCES "LeagueUsers"("IDUser"),
    "Amount" NUMERIC(15,2) DEFAULT 0,
    "EventType" VARCHAR(50),
    "Description" TEXT,
    "UpdatedAt" TIMESTAMPTZ DEFAULT NOW()
);

-- Token de acceso a la API de Futmondo
CREATE TABLE IF NOT EXISTS "AccessToken" (
    "ID" VARCHAR(100) PRIMARY KEY,
    "AccessToken" TEXT,
    "UpdatedAt" TIMESTAMPTZ DEFAULT NOW()
);

-- Indices
CREATE INDEX IF NOT EXISTS idx_pressroom_buyer ON "PressRoom"("IDPurchaseUser");
CREATE INDEX IF NOT EXISTS idx_pressroom_seller ON "PressRoom"("IDSalesUser");
CREATE INDEX IF NOT EXISTS idx_pressroom_date ON "PressRoom"("TransactionDate");
CREATE INDEX IF NOT EXISTS idx_money_events_user ON "MoneyEvents"("IDUser");
CREATE INDEX IF NOT EXISTS idx_money_events_date ON "MoneyEvents"("EventDate");

-- Habilitar Row Level Security
ALTER TABLE "LeagueUsers" ENABLE ROW LEVEL SECURITY;
ALTER TABLE "PressRoom" ENABLE ROW LEVEL SECURITY;
ALTER TABLE "MoneyEvents" ENABLE ROW LEVEL SECURITY;
ALTER TABLE "AccessToken" ENABLE ROW LEVEL SECURITY;

-- Politicas RLS: anon solo lectura en tablas de datos, AccessToken bloqueado
-- (service_role key ignora RLS automaticamente, no necesita politica)
CREATE POLICY "anon_read" ON "LeagueUsers" FOR SELECT USING (true);
CREATE POLICY "anon_read" ON "PressRoom" FOR SELECT USING (true);
CREATE POLICY "anon_read" ON "MoneyEvents" FOR SELECT USING (true);
-- AccessToken: sin politica = acceso bloqueado para anon

-- Vista: Dashboard de usuarios (Balance, Valor Equipo, Puja Maxima)
-- Balance = 200M - compras + ventas + repartos de dinero
-- Puja Maxima = Balance + 50% del valor del equipo (config liga)
-- NOTA: usa UNION ALL para generar una fila por comprador y otra por vendedor,
-- evitando que COALESCE pierda las ventas en transacciones Compra-Venta.
CREATE OR REPLACE VIEW "UserDashboard" AS
SELECT
    u."IDUser",
    u."UserName",
    u."NameInGame",
    200000000
        + COALESCE(tx.total_purchases, 0)
        + COALESCE(tx.total_sales, 0)
        + COALESCE(me.total_money, 0) AS "Balance",
    u."ActualValueTeam" AS "ValorEquipo",
    CEIL(200000000
        + COALESCE(tx.total_purchases, 0)
        + COALESCE(tx.total_sales, 0)
        + COALESCE(me.total_money, 0)
        + (u."ActualValueTeam" * 0.50)) AS "PujaMaxima"
FROM "LeagueUsers" u
LEFT JOIN (
    SELECT uid,
        SUM(purchases) AS total_purchases,
        SUM(sales) AS total_sales
    FROM (
        SELECT "IDPurchaseUser" AS uid, "PurchaseAmount" AS purchases, 0 AS sales
        FROM "PressRoom"
        WHERE "IDPurchaseUser" IS NOT NULL
        UNION ALL
        SELECT "IDSalesUser" AS uid, 0 AS purchases, "SalesAmount" AS sales
        FROM "PressRoom"
        WHERE "IDSalesUser" IS NOT NULL
    ) sub
    GROUP BY uid
) tx ON tx.uid = u."IDUser"
LEFT JOIN (
    SELECT "IDUser", SUM("Amount") AS total_money
    FROM "MoneyEvents"
    GROUP BY "IDUser"
) me ON me."IDUser" = u."IDUser"
ORDER BY "Balance" ASC;
