-- 1. What is the total number of orders broken down by order status, 
-- and what percentage of total orders does each status represent?

create materialized view mv_order_status_summary as
with status_count as (
	select 
		order_status,
		count(*) as number_of_orders
	from olist_orders
	group by order_status
)
select 
	order_status,
	number_of_orders,
	sum(number_of_orders) over() as total_orders,
	round(number_of_orders * 100 / sum(number_of_orders) over(),6) AS percentage_of_total
from status_count
order by number_of_orders desc;

CREATE UNIQUE INDEX idx_mv_order_status_summary
ON mv_order_status_summary(order_status);

REFRESH MATERIALIZED VIEW CONCURRENTLY mv_order_status_summary;

SELECT * FROM mv_order_status_summary;

-- 2.What is the monthly order volume and total GMV,
-- split between product revenue and freight revenue?

with order_order_items as (
	select 
	        oo.order_id,
	        oo.order_purchase_timestamp,
	        ooi.price,
	        ooi.freight_value,
	        DATE_TRUNC('month', order_purchase_timestamp) AS month
	from olist_orders oo left join olist_order_items ooi on oo.order_id = ooi.order_id 
) 
SELECT 
    COUNT(DISTINCT order_id) AS order_count,
    month,
    SUM(coalesce(price,0)) as total_sales,
    SUM(coalesce(freight_value,0)) as total_freight_value,
    SUM(coalesce(price,0) + coalesce(freight_value,0)) as total_gmv
FROM order_order_items
GROUP BY month
ORDER BY month;

-- 3.Which are the top ten product categories by total revenue, and what is the average item price per category? 
--  English category names must be used where available.


SELECT 
    COALESCE(
        opcnt.product_category_name_english,
        op.product_category_name,
        'unknown'
    ) AS category_name,
    SUM(ooi.price) AS total_revenue,
    AVG(ooi.price) AS average_price
FROM olist_order_items ooi 
LEFT JOIN olist_products op 
    ON ooi.product_id = op.product_id 
LEFT JOIN olist_product_category_name_translation opcnt 
    ON op.product_category_name = opcnt.product_category_name
group  by  
    COALESCE(
        opcnt.product_category_name_english,
        op.product_category_name,
        'unknown'
    )
order by total_revenue desc limit 10;

-- 4. What is the breakdown of payment methods by count, total value, and average number of installments?

select 
	oop.payment_type,
	count(*) as payment_type_count,
	sum(oop.payment_value ) as total_value,
	round(avg(oop.payment_installments),2) as average_number_of_installments
from olist_order_payments oop 
group by oop.payment_type 
order by total_value  desc;

-- 5. What is the average review score per product category, limited to categories with more than 50 reviews?

WITH reviews AS (
    SELECT DISTINCT
        review_id,
        order_id,
        review_score
    FROM olist_order_reviews
)
select 
	op.product_category_name ,
	count(DISTINCT r.review_id) as number_of_reviews,
	avg(r.review_score) as average_review_score
from olist_order_items ooi 
left join olist_products op on ooi.product_id = op.product_id 
left join reviews r on ooi.order_id = r.order_id 
group by op.product_category_name 
having count(DISTINCT r.review_id)>50
order by average_review_score desc

-- 6. How are customers distributed across Brazilian states, and how many distinct cities are represented per state?

select 
	oc.customer_state,
	count(distinct oc.customer_unique_id ) as number_of_customers,
	count(distinct oc.customer_city ) as number_of_distinct_cities
from olist_customers oc 
group by oc.customer_state 
order by number_of_customers desc;

--7. Of all delivered orders, what proportion were delivered on time versus late versus missing a delivery date?

select 
case
	when order_delivered_customer_date is null then 'missing'
	when order_delivered_customer_date > order_estimated_delivery_date then 'Late'
	else 'On Time'
end as delivery_category,
count(*) as count_orders_category,
round(count(*) / sum(count(*)) over(),6 ) as proportion
from olist_orders
where order_status = 'delivered'
group by delivery_category;
select distinct order_status from olist_orders oo 

--8. Who are the top ten sellers by total revenue, and how many distinct orders did each fulfil?

select 
	ooi.seller_id,
	sum(price) as total_revenue,
count(distinct ooi.order_id ) as distinct_order_count
from olist_orders oo left join olist_order_items ooi on oo.order_id = ooi.order_id 
where oo.order_status ='delivered'
group by ooi.seller_id
order by distinct_order_count desc
limit 10;

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

