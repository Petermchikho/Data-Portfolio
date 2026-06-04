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

WITH seller_orders AS (
    SELECT
        oi.seller_id,
        GREATEST(
            ROUND(
                EXTRACT(
                    EPOCH FROM (
                        o.order_delivered_customer_date -
                        o.order_estimated_delivery_date
                    )
                ) / 86400
            ),
            0
        ) AS delay_days
    FROM olist_orders o
    JOIN (
        SELECT DISTINCT order_id, seller_id
        FROM olist_order_items
    ) oi
        ON o.order_id = oi.order_id
    WHERE o.order_status = 'delivered'
)

SELECT
    seller_id,
    COUNT(*) AS delivered_orders,
    ROUND(AVG(delay_days), 2) AS avg_delay_days,
    PERCENTILE_CONT(0.50)
        WITHIN GROUP (ORDER BY delay_days) AS median_delay_days,
    PERCENTILE_CONT(0.90)
        WITHIN GROUP (ORDER BY delay_days) AS p90_delay_days,
    PERCENTILE_CONT(0.95)
        WITHIN GROUP (ORDER BY delay_days) AS p95_delay_days
FROM seller_orders
GROUP BY seller_id
HAVING COUNT(*) >= 20
ORDER BY avg_delay_days DESC;

--12. By monthly acquisition cohort, what percentage of customers placed a
-- second order within 90 days of their first purchase?

WITH orders_customers AS (
    SELECT
        oc.customer_unique_id,
        o.order_id,
        o.order_purchase_timestamp,
        ROW_NUMBER() OVER (
            PARTITION BY oc.customer_unique_id
            ORDER BY o.order_purchase_timestamp
        ) AS purchase_number
    FROM olist_orders o
    JOIN olist_customers oc
        ON o.customer_id = oc.customer_id
),
first_second_orders AS (
    SELECT
        customer_unique_id,
        MAX(CASE WHEN purchase_number = 1 THEN order_purchase_timestamp END) AS first_order_date,
        MAX(CASE WHEN purchase_number = 2 THEN order_purchase_timestamp END) AS second_order_date
    FROM orders_customers
    WHERE purchase_number IN (1, 2)
    GROUP BY customer_unique_id
)
SELECT
    customer_unique_id,
    first_order_date,
    second_order_date,
    second_order_date - first_order_date AS time_between_orders,
    EXTRACT(DAY FROM (second_order_date - first_order_date)) AS days_between_orders
FROM first_second_orders
WHERE second_order_date IS NOT NULL
ORDER BY days_between_orders;

--13. How does average review score vary across delivery delay buckets — very early
-- early, on time, slightly late, moderately late, and very late?

with delivery_delay as (
	select 
		oo.order_id ,
		oo.order_estimated_delivery_date,
		oo.order_delivered_customer_date,
		(date(oo.order_estimated_delivery_date) - date(oo.order_delivered_customer_date) ) as delivery_difference
	from olist_orders oo 
	where oo.order_status ='delivered'
),delivery_delay_buckets as(
select 
order_id ,
delivery_difference,
case 
	WHEN delivery_difference > 5 THEN 'very early'
    WHEN delivery_difference > 0 THEN 'early'
    WHEN delivery_difference = 0 THEN 'on time'
    WHEN delivery_difference >= -2 THEN 'slightly late'
    WHEN delivery_difference >= -5 THEN 'moderately late'
    ELSE 'very late'
end as delay_bucket

from delivery_delay 
),order_reviews as (
select 
ddb.order_id ,
ddb.delivery_difference,
ddb.delay_bucket,
oor.review_score 
from delivery_delay_buckets ddb  left join olist_order_reviews oor on oor.order_id = ddb.order_id 
)
select 
delay_bucket,
ROUND(AVG(review_score ),2) as average_review
from order_reviews
group by delay_bucket

-- late delivery negatively affects reviews


-- 14. For all qualifying sellers, assign a revenue rank, a review score rank, and classify each into revenue and
-- review quartiles

with order_items_reviews as(
select  *
    from  olist_order_items ooi
    left  join  olist_order_reviews oor
        on  ooi.order_id = oor.order_id
     where oor.review_score is not null
) ,seller_aggregates as (
select 
	seller_id,
	avg(review_score ) as average_review_score,
	sum(price) as total_revenue
from order_items_reviews 
group by seller_id 
)
select 
seller_id,
average_review_score,
dense_rank() over(order by average_review_score desc) as review_score_rank,
ntile(4) over(order by average_review_score desc ) as review_score_quartile,
total_revenue,
dense_rank() over(order by total_revenue desc) as total_revenue_rank,
ntile(4) over(order by total_revenue desc) as total_revenue_quartile
from seller_aggregates

-- 15.Which pairs of products are most frequently purchased within the same
-- order, and how often does each pairing occur?

select * from olist_order_items ooi limit 5;

with together_products as(
	SELECT
	    oi1.product_id AS product_1,
	    oi2.product_id AS product_2,
	    COUNT(*) AS times_together
	FROM olist_order_items oi1
	JOIN olist_order_items oi2
	    ON oi1.order_id = oi2.order_id
	   AND oi1.product_id < oi2.product_id
	GROUP BY
	    oi1.product_id,
	    oi2.product_id
	ORDER BY times_together DESC
)SELECT
    tp.product_1,
    p1.product_category_name  AS product_1_name,
    tp.product_2,
    p2.product_category_name  AS product_2_name,
    tp.times_together
FROM together_products tp
LEFT JOIN olist_products p1
    ON tp.product_1 = p1.product_id
LEFT JOIN olist_products p2
    ON tp.product_2 = p2.product_id
ORDER BY tp.times_together DESC;

-- 16. Which orders used more than one payment method, and what is the
-- combined payment string, total value paid, and maximum installment count for each?

with  distinct_payments as  (
    select  distinct 
        order_id,
        payment_type
    from  olist_order_payments oop 
),payment_counts as  (
    select 
        order_id,
        COUNT(payment_type) as  payment_methods_count
    from  distinct_payments
    group  by order_id
)
select 
    oop.order_id,
    STRING_AGG(payment_type, ', ') AS payment_types,
    count(oop.payment_installments) AS maximum_installment_count,
    sum(payment_value) AS total_payment_value,
    count(*) over() total_orders   
from  olist_order_payments oop 
join  payment_counts pc on  pc.order_id = oop.order_id
where pc.payment_methods_count > 1
group  by  oop.order_id
order  by oop.order_id;

-- OR 
with  payment_counts as  (
    select 
        order_id,
        COUNT(distinct payment_type) as payment_methods_count
    from olist_order_payments
    group by  order_id
)
select
    oop.order_id,
    STRING_AGG(distinct oop.payment_type, ', ') as payment_types,
    SUM(oop.payment_value) as total_payment_value,
    MAX(oop.payment_installments) as maximum_installment_count,
    count(*) over() total_orders   
from olist_order_payments oop
join payment_counts pc
    on oop.order_id = pc.order_id
where pc.payment_methods_count > 1
group by oop.order_id
order by oop.order_id;


-- 17. By product category and customer state, what is the average freight
-- value as a percentage of product price for orders with sufficient volume?

with order_items_categories_customer as (
	select 
		ooi.order_id,
		ooi.product_id,
		op.product_category_name,
		ooi.price,
		ooi.freight_value,
		oo.customer_id,
		oc.customer_state 
	from olist_order_items ooi 
	left join olist_products op 
	on ooi.product_id = op.product_id 
	left join olist_orders oo 
	on ooi.order_id = oo.order_id
	left join olist_customers oc on oo.customer_id =oc.customer_id 
	where oo.order_status in ('delivered','shipped','invoiced')
), freight_as_percentage_of_price as(
select oicc.* , ((oicc.freight_value * 100)/nullif(oicc.price,0)) as freight_as_percentage from order_items_categories_customer oicc
)
select 
	product_category_name,
	customer_state,
	round(AVG(freight_as_percentage),2) as average_freight_as_percentage_of_price,
	COUNT(DISTINCT order_id) AS total_orders
from freight_as_percentage_of_price
group by product_category_name,customer_state
HAVING COUNT(DISTINCT order_id) >= 30
ORDER BY average_freight_as_percentage_of_price DESC;


