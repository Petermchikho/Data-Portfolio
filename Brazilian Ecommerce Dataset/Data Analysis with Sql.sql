-- What is the total number of orders broken down by order status, 
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
