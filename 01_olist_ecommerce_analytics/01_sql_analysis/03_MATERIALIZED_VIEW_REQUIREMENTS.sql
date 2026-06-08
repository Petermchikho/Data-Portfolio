-- MV1 — Daily Order Summary
-- PURPOSE:
-- Pre-aggregates order count, unique customer count, product revenue, freight
-- revenue, and total GMV by day and order status. Serves daily KPI dashboards
-- and Airflow sink tasks.

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


-- MV2 — Seller Performance Snapshot
-- PURPOSE:
-- Aggregates per-seller metrics including total orders fulfilled, total revenue,
-- average review score, review volume, average delivery delay in days, and count
-- of on-time deliveries. Filters to delivered orders with a non-null delivery date.

DROP MATERIALIZED VIEW IF EXISTS mv_seller_performance;
create materialized view mv_seller_performance as
with order_items_aggs as(
	select 
		ooi.order_id,
		ooi.seller_id,
		sum(ooi.price) as total_price,
		sum(ooi.freight_value ) as total_freight
	from olist_order_items ooi
	group by ooi.order_id,ooi.seller_id 
), reviews_aggregates as(
	select 
		order_id,
		sum(review_score) as total_review_score
	from olist_order_reviews oor 
	group by oor.order_id 
), order_aggregates_combined as (
	select 
		oo.order_id,
		oo.order_estimated_delivery_date,
		oo.order_delivered_customer_date,
		oia.seller_id,
		oia.total_price,
		oia.total_freight,
		ra.total_review_score 
	from olist_orders oo left join 
	order_items_aggs oia on  oo.order_id = oia.order_id 
	left join reviews_aggregates ra on oo.order_id = ra.order_id 
	where oo.order_status = 'delivered' and oo.order_delivered_customer_date is not null
), delivery_delay as (
	select 
		oac.*,
		(date(oac.order_estimated_delivery_date) - date(oac.order_delivered_customer_date) ) as delivery_difference
	from order_aggregates_combined oac
),delivery_delay_buckets as(
select 
dd.*,
case 
	WHEN delivery_difference > 5 THEN 'very early'
    WHEN delivery_difference > 0 THEN 'early'
    WHEN delivery_difference = 0 THEN 'on time'
    WHEN delivery_difference >= -2 THEN 'slightly late'
    WHEN delivery_difference >= -5 THEN 'moderately late'
    ELSE 'very late'
end as delay_bucket
from delivery_delay as dd
), on_time_deliveries as (
select 
ddb.*,
case 
	when ddb.delay_bucket ='on time' then 1
	else 0
end as on_time_delivery
from delivery_delay_buckets as ddb

)
select 
otd.seller_id,
count(otd.order_id) as total_orders_fulfilled, 
sum(otd.total_price) as total_revenue,
avg(otd.total_review_score) as average_review_score, 
count(otd.total_review_score) as review_volume, 
avg(otd.delivery_difference) as average_delivery_delay_in_days,
sum(otd.on_time_delivery) as count_of_on_time_deliveries
from on_time_deliveries as otd
group by seller_id; 

DROP INDEX IF EXISTS s_mv_seller_performance;
CREATE UNIQUE INDEX s_mv_seller_performance
ON mv_seller_performance(seller_id);

select * from mv_seller_performance;