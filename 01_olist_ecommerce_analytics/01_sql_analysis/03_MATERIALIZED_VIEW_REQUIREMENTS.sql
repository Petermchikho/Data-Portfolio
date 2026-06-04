-- MV1 — Daily Order Summary

DROP MATERIALIZED VIEW IF EXISTS mv_daily_order_summary;
create materialized view mv_daily_order_summary as
SELECT
    date_trunc('day', oo.order_purchase_timestamp) AS order_date,
    oo.order_status,

    COUNT(DISTINCT oo.order_id) AS order_count,
    COUNT(DISTINCT oc.customer_unique_id) AS unique_customers,

    SUM(ooi.price) AS product_revenue,
    SUM(ooi.freight_value) AS freight_revenue,

    SUM(ooi.price + ooi.freight_value) AS gmv

FROM olist_orders oo
JOIN olist_order_items ooi
    ON oo.order_id = ooi.order_id
JOIN olist_customers oc
    ON oo.customer_id = oc.customer_id

GROUP BY
    date_trunc('day', oo.order_purchase_timestamp),
    oo.order_status
ORDER BY order_date, order_status;

DROP INDEX IF EXISTS osm_mv_daily_order_summary;
CREATE UNIQUE INDEX osm_mv_daily_order_summary
ON mv_daily_order_summary(order_status, order_date);


select * from mv_daily_order_summary