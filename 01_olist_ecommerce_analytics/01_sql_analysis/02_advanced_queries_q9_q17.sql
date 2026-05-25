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