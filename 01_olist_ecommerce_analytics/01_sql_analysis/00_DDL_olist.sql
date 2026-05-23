drop table if exists olist_sellers;
create table olist_sellers(
     seller_id varchar(32) primary key,
     seller_zip_code_prefix varchar(5) not null check (seller_zip_code_prefix ~ '^\d{5}$'),
     seller_city varchar(60) not null,
     seller_state varchar(2) not null check (seller_state ~ '^[A-Z]{2}$')
);

drop table if exists olist_product_category_name_translation;
create table olist_product_category_name_translation(
      product_category_name varchar(200) primary key,
      product_category_name_english varchar(200) not null
);

drop table if exists olist_geolocation;
create table olist_geolocation(
	geolocation_zip_code_prefix varchar(5) check (geolocation_zip_code_prefix ~ '^\d{5}$'),
	geolocation_lat decimal(10,8) not null,
	geolocation_lng decimal(11,8) not null ,
	geolocation_city varchar(60) not null,
	geolocation_state varchar(2) not null check (geolocation_state ~ '^[A-Z]{2}$'),
	PRIMARY KEY (geolocation_zip_code_prefix, geolocation_lat, geolocation_lng)
);


drop table if exists olist_customers;
create table olist_customers(
customer_id varchar(32) primary key,
customer_unique_id varchar(32) not null unique ,
customer_zip_code_prefix varchar(5) not null check (customer_zip_code_prefix ~ '^\d{5}$'),
customer_city varchar(60) not null,
customer_state varchar(2) not null check (customer_state ~ '^[A-Z]{2}$')
);



--Note to self Onloading with airflow rename the columns with pandas lenght to length then load 
drop table if exists olist_products;
create table olist_products(
	product_id varchar(32) primary key ,
	product_category_name varchar(200),
	product_name_length int,
	product_description_length int,
	product_photos_qty int,
	product_weight_g int,
	product_length_cm int,
	product_height_cm int,
	product_width_cm int
);

drop table if exists olist_orders;
create table olist_orders(
order_id varchar(32) primary key,
customer_id varchar(32) not null references olist_customers(customer_id),
order_status varchar(11) NOT NULL CHECK (order_status IN (
        'delivered', 
        'shipped', 
        'canceled', 
        'invoiced', 
        'unavailable'
    )),
order_purchase_timestamp timestamp not null,
order_approved_at timestamp,
order_delivered_carrier_date timestamp,
order_delivered_customer_date timestamp,
order_estimated_delivery_date timestamp
);

drop table if exists olist_order_items;
create table olist_order_items(
order_id varchar(32) not null,
order_item_id int not null,
product_id varchar(32) not null,
seller_id varchar(32) not null,
shipping_limit_date timestamp ,
price DECIMAL(10,2) CHECK (price >= 0),
freight_value DECIMAL(10,2) CHECK (freight_value >= 0),
PRIMARY KEY (order_id, order_item_id),
CONSTRAINT fk_order_items_order
        FOREIGN KEY (order_id) 
        REFERENCES olist_orders(order_id)
        on delete cascade,
CONSTRAINT fk_order_items_product
        FOREIGN KEY (product_id) 
        REFERENCES olist_products(product_id)
        on delete cascade, 
CONSTRAINT fk_order_items_seller
        FOREIGN KEY (seller_id) 
        REFERENCES olist_sellers(seller_id)
        on delete cascade
);


drop table if exists olist_order_payments;
create table olist_order_payments(
order_id varchar(32) not null,
payment_sequential int not null CHECK (payment_sequential > 0),
payment_type varchar(11) not null check (payment_type in (
'credit_card',
'boleto',
'voucher',
'debit_card',
'not_defined'

)),
payment_installments int not null CHECK (payment_installments >= 0),
payment_value decimal(10,2) not null CHECK (payment_value >= 0),
PRIMARY KEY (order_id, payment_sequential),
CONSTRAINT fk_payment_order
        FOREIGN KEY (order_id) 
        REFERENCES olist_orders(order_id)
        ON DELETE CASCADE
);

drop table if exists olist_order_reviews;
create table olist_order_reviews(
review_id varchar(32) primary key,
order_id varchar(32) not null,
review_score int not null,
review_comment_title varchar(200),
review_comment_message varchar(400),
review_creation_date timestamp,
review_answer_timestamp timestamp,
constraint fk_order_review_order
         foreign key (order_id)
         REFERENCES olist_orders(order_id)
         ON DELETE CASCADE
);


DROP INDEX IF EXISTS idx_customers_zip;
DROP INDEX IF EXISTS idx_customers_location;
DROP INDEX IF EXISTS idx_orders_customer;
DROP INDEX IF EXISTS idx_orders_purchase_date;
DROP INDEX IF EXISTS idx_orders_status;
DROP INDEX IF EXISTS idx_order_items_product;
DROP INDEX IF EXISTS idx_order_items_seller;
DROP INDEX IF EXISTS idx_payments_type;
DROP INDEX IF EXISTS idx_reviews_score;
DROP INDEX IF EXISTS idx_reviews_creation_date;


CREATE INDEX idx_customers_location ON olist_customers(customer_city, customer_state);
CREATE INDEX idx_customers_zip ON olist_customers(customer_zip_code_prefix);


CREATE INDEX idx_orders_customer ON olist_orders(customer_id);
CREATE INDEX idx_orders_purchase_date ON olist_orders(order_purchase_timestamp);
CREATE INDEX idx_orders_status ON olist_orders(order_status);


CREATE INDEX idx_order_items_product ON olist_order_items(product_id);
CREATE INDEX idx_order_items_seller ON olist_order_items(seller_id);


CREATE INDEX idx_payments_type ON olist_order_payments(payment_type);


CREATE INDEX idx_reviews_score ON olist_order_reviews(review_score);
CREATE INDEX idx_reviews_creation_date ON olist_order_reviews(review_creation_date);


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