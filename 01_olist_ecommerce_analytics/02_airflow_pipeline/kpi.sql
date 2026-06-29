CREATE TABLE IF NOT EXISTS agg_daily_kpis (
    kpi_date       DATE PRIMARY KEY,
    total_orders   INTEGER NOT NULL DEFAULT 0,
    gmv            NUMERIC(14, 2) NOT NULL DEFAULT 0,
    new_customers  INTEGER NOT NULL DEFAULT 0,
    updated_at     TIMESTAMP NOT NULL DEFAULT now()
);