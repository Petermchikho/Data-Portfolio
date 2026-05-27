--9. What is the lifetime value of each customer, total orders placed, 
--   and are they a one-time or repeat purchaser? Aggregate to show averages by customer type.

with order_order_item as(
    select 
    oo.order_id,
    ooi.price,
    ooi.freight_value,
    oo.customer_id 
    from olist_orders oo left join  olist_order_items ooi on oo.order_id = ooi.order_id 
),order_customer as(
    select * from order_order_item ooi left join olist_customers oc on ooi.customer_id = oc.customer_id 
),customer_metrics as(
	select 
	customer_unique_id,
	SUM(price + freight_value ) as total_value,
	count(distinct order_customer.order_id ) as total_orders_placed,
	case 
		when count(distinct order_customer.order_id ) > 1 then 'repeat'
		else 'one time'
	end as customer_type
	from order_customer 
	group by customer_unique_id 
)
select 
	customer_type ,
	avg(total_value) as average_total_value,
	avg(total_orders_placed ) as average_total_orders_placed 
from customer_metrics 
group by customer_type 

-- 10. What is the running total GMV by month, and what is the month-over-month percentage growth rate?
--select * from olist_order_items ooi limit 5;
--select * from olist_orders oo limit 5;

with total_month_gmv as(
select 
date_trunc('month',oo.order_purchase_timestamp ) as month,
sum(ooi.price + ooi.freight_value ) as gmv
from olist_orders oo left join olist_order_items ooi on oo.order_id = ooi.order_id
WHERE oo.order_status = 'delivered'
group by "month" 
)
select 
"month",
gmv,
sum(gmv) over(order by "month") as running_total,
lag(gmv,1,0) over(order by "month" ) as previous_month_gmv,
round(
        (
            (gmv - lag(gmv) over (order by  month))
            /
            nullif(lag(gmv) over  (order by month), 0)
        ) * 100,
        2
    ) as month_over_month_growth_percentage
from total_month_gmv;


--select 
--*
--from olist_orders oo left join olist_order_items ooi on oo.order_id = ooi.order_id
--where oo.order_purchase_timestamp > '2018-10-01 00:00:00.000'
--
--select 
--distinct(oo.order_status )
--from olist_orders oo left join olist_order_items ooi on oo.order_id = ooi.order_id

-- 11. For each seller with at least 20 delivered orders, what is the average, median, 90th and 95th 
--percentile delivery delay in days relative to the estimated delivery date?

WITH order_items_sellers AS (

SELECT DISTINCT(order_id) as order_id,seller_id FROM olist_order_items

),twenty_above_orders_sellers as(
select 
	oo.order_delivered_customer_date,
	oo.order_estimated_delivery_date,
	oo.order_id,ois.seller_id,
	round((extract(epoch from oo.order_estimated_delivery_date) 
	- extract(epoch from oo.order_delivered_customer_date)) 
	/ (60*60*24)) as delivery_diff_days,
	count(oo.order_id) over(partition by ois.seller_id) as total_orders,
	CASE 
	        WHEN round((extract(epoch from oo.order_estimated_delivery_date) 
	- extract(epoch from oo.order_delivered_customer_date)) 
	/ (60*60*24)) < 0 THEN ABS(round((extract(epoch from oo.order_estimated_delivery_date) 
	- extract(epoch from oo.order_delivered_customer_date)) 
	/ (60*60*24)))
	        ELSE 0
	END AS delayed_days
from olist_orders oo left join order_items_sellers ois on oo.order_id = ois.order_id
where oo.order_status = 'delivered'
),with_averages as(
SELECT 
seller_id,
total_orders,
delivery_diff_days,
order_id,
delayed_days,
avg(delayed_days) over() as average_delay_days,
avg(delayed_days) over(partition by seller_id) as average_delay_days_for_seller
FROM twenty_above_orders_sellers
where total_orders>=20
), with_percentiles as(
select 
PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY delayed_days) AS p25,
PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY delayed_days) AS p50_median,
PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY delayed_days) AS p75,
PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY delayed_days) AS p90
from with_averages
WHERE delayed_days > 0
)
SELECT
    wa.seller_id,
    wa.total_orders,
    wa.delivery_diff_days,
    wa.order_id,
    wa.delayed_days,
    wa.average_delay_days,
    wa.average_delay_days_for_seller,
    wp.p25,
    wp.p50_median,
    wp.p75,
    wp.p90
FROM with_averages wa
CROSS JOIN with_percentiles wp
where wa.delayed_days > 0
;

