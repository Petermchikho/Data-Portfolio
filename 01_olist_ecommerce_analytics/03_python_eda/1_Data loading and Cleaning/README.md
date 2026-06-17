# 01 — Data Loading and Cleaning

**Project:** Olist E-Commerce Dataset | Quantify Analytics Labs  
**Author:** Peter Mchikho  
**Notebook:** `01_data_loading_and_cleaning.ipynb`

---

## Overview

This notebook is the entry point of the Olist analytical pipeline. It loads all 9 raw
CSV files from the Brazilian Olist E-Commerce dataset, performs profiling and cleaning
on each, and exports every table to Parquet for downstream use. An Excel workbook
consolidating all cleaned tables is also produced as a reference artefact.

---

## Dataset Source

```bash
kaggle datasets download -d olistbr/brazilian-ecommerce
unzip brazilian-ecommerce.zip
```

---

## Tables Processed

| Table | Source File | Key Cleaning Actions | Output |
|---|---|---|---|
| `customers` | `olist_customers_dataset.csv` | Zero-pad zip codes, strip whitespace, assert no duplicates | `customers.parquet` |
| `geolocation` | `olist_geolocation_dataset.csv` | Drop 261,831 duplicate rows, zero-pad zip codes, strip whitespace | `geolocation.parquet` |
| `order_items` | `olist_order_items_dataset.csv` | Parse `shipping_limit_date`, assert no duplicates | `order_items.parquet` |
| `order_payments` | `olist_order_payments_dataset.csv` | Strip whitespace, assert no duplicates | `order_payments.parquet` |
| `order_reviews` | `olist_order_reviews_dataset.csv` | Parse date columns, strip whitespace, assert no duplicates | `order_reviews.parquet` |
| `orders` | `olist_orders_dataset.csv` | Parse 5 timestamp columns, strip whitespace, assert no duplicates | `orders.parquet` |
| `products` | `olist_products_dataset.csv` | Fill null `product_category_name` with `'unknown'`, strip whitespace | `products.parquet` |
| `sellers` | `olist_sellers_dataset.csv` | Zero-pad zip codes, strip whitespace, assert no duplicates | `sellers.parquet` |
| `product_category_name_translation` | `product_category_name_translation.csv` | Strip whitespace | `product_category_name_translation.parquet` |

---

## Helper Functions

Four reusable utility functions are defined at the top of the notebook and applied
consistently across all tables:

**`value_counts_for_categorical_columns(df, drop_cols)`**  
Profiles all object-type columns, printing total records, unique values, missing value
counts, and a value counts table with cumulative percentages. ID columns are excluded
via `drop_cols`.

**`remove_white_spaces(df)`**  
Strips leading and trailing whitespace from all string columns in-place. Applied to
every table before export.

**`padding_zip_codes(df, cols)`**  
Zero-pads zip code columns to 5 characters using `str.zfill(5)`. Applied to
`customers`, `geolocation`, and `sellers`. Validated with an `assert` after padding.

**`plot_value_counts(df, col)`**  
Renders a bar chart of value counts for a given column. Used for visual profiling of
key categorical fields (`customer_state`, `order_status`, `payment_type`, `review_score`,
`product_category_name`, `seller_state`, `geolocation_state`).

---

## Cleaning Decisions

**Geolocation duplicates**  
The geolocation table contained 261,831 duplicate rows — the only table with meaningful
duplication. These were dropped with `drop_duplicates(inplace=True)` and verified with
an assertion.

**Product category nulls**  
`product_category_name` had null values filled with the string `'unknown'` rather than
dropping rows, preserving product records for downstream joins.

**Zip code standardisation**  
Zip code prefix columns across customers, geolocation, and sellers were cast to string
and zero-padded to exactly 5 characters. This ensures consistent join behaviour when
these columns are used as keys.

**Timestamp parsing**  
`order_items.shipping_limit_date` and all 5 timestamp columns in `orders` are parsed at
load time using `parse_dates=` in `pd.read_csv()`, avoiding downstream type conversion.

**No cleaning required**  
`order_items`, `order_payments`, `order_reviews`, and `orders` had zero duplicate rows.
These were verified with `assert df.duplicated().sum() == 0` before export.

---

## Outputs

```
customers.parquet
geolocation.parquet
order_items.parquet
order_payments.parquet
order_reviews.parquet
orders.parquet
products.parquet
sellers.parquet
product_category_name_translation.parquet
olist.xlsx                          ← all 9 tables in a single workbook
```

Parquet is used as the primary output format for performance and type fidelity in
downstream notebooks. The Excel workbook (`olist.xlsx`) is produced as a reference
artefact for non-programmatic inspection.

---

## Dependencies

```python
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import pyarrow   # required by df.to_parquet(engine='pyarrow')
```

---

*Quantify Analytics Labs — Olist E-Commerce Dataset Project*
