ALTER TABLE olist_customers
DROP CONSTRAINT olist_customers_customer_unique_id_key;

ALTER TABLE olist_products
    ALTER COLUMN product_weight_g       TYPE DECIMAL(10,2),
    ALTER COLUMN product_length_cm      TYPE DECIMAL(10,2),
    ALTER COLUMN product_height_cm      TYPE DECIMAL(10,2),
    ALTER COLUMN product_width_cm       TYPE DECIMAL(10,2),
    ALTER COLUMN product_name_length       TYPE DECIMAL(10,2),
    ALTER COLUMN product_description_length TYPE DECIMAL(10,2),
    ALTER column product_photos_qty TYPE DECIMAL(10,2);
	
ALTER TABLE olist_products 
DROP CONSTRAINT fk_products_category_name;

ALTER TABLE olist_orders 
DROP CONSTRAINT orders_order_status_check;