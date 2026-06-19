# Delivery Time Estimation — Olist Brazilian E-Commerce Dataset

A regression project predicting e-commerce delivery times from order, product, seller, and geographic data, benchmarked against the platform's own published delivery estimate.

**Dataset:** [Olist Brazilian E-Commerce Public Dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) (100k+ orders, 2016–2018)
**Author:** Peter Mchikho — Quantify Analytics Labs
**Stack:** Python, pandas, scikit-learn, matplotlib

---

## Problem

Given an order's product, seller, customer, and timing attributes, predict `delivery_time_days` — the number of days between purchase and actual delivery.

**Framing:** this model estimates delivery time *from the point a seller dispatches the order to the carrier*, not at checkout. The top predictor (seller handling time) is only known post-dispatch — see [Leakage & Feature Validity](#leakage--feature-validity) below for why this matters and what it means for how the model can be used.

## Headline Result

| Metric | Value |
|---|---|
| MAE | 3.69 days |
| RMSE | 7.05 days |
| R² | 0.478 |
| Within ±5 days of actual | 77.8% of predictions |

**Benchmark against Olist's own published delivery estimate**, on the same held-out orders:

| Threshold | This model | Olist's estimate | Improvement |
|---|---|---|---|
| ±2 days | 47.6% | 6.6% | 7.2x |
| ±3 days | 61.1% | 9.0% | 6.8x |
| ±5 days | 77.8% | 15.3% | 5.1x |

Olist's published estimate is intentionally conservative (wide windows reduce the risk of promising a date the platform might miss), so this isn't a claim that their logistics team underperforms — it's evidence that **there's real headroom to tighten customer-facing delivery estimates** using signals already present in the data.

## Approach

1. **Data engineering** — merged six raw tables (orders, order_items, products, sellers, customers, geolocation) into a single order-item-level dataframe. Geolocation data was aggregated to one centroid per zip-code prefix before joining, to avoid duplicate-row fan-out from the raw table's multiple addresses per prefix.
2. **Feature engineering** — derived `distance_km` (Haversine, seller↔customer), `product_volume_cm3`, `seller_handling_days`, `order_item_count`, `same_state`, `purchase_dow`/`purchase_month`, and `is_peak_season`.
3. **Leakage review** — explicitly excluded `order_delivered_customer_date` (the target's source) and `order_estimated_delivery_date` (Olist's own estimate) from the feature set; the latter is used only as a post-hoc benchmark.
4. **Model comparison** — Linear Regression, Ridge, Lasso, and Random Forest, trained on an identical 80/20 split with one-hot encoding (fit on training data only) and numeric scaling.
5. **Evaluation** — MAE/RMSE/R², ±N-day accuracy bands, feature importance, and the Olist benchmark above.

## Model Comparison

| Model | MAE (days) | RMSE (days) | R² |
|---|---|---|---|
| Linear Regression | 4.34 | 7.62 | 0.390 |
| Ridge (α=1.0) | 4.34 | 7.62 | 0.390 |
| Lasso (α=1.0) | 5.01 | 8.29 | 0.278 |
| **Random Forest (selected)** | **3.69** | **7.05** | **0.478** |
| Random Forest (tuned via RandomizedSearchCV) | 3.84 | 7.20 | 0.456 |

Ridge matching the unregularized baseline almost exactly ruled out overfitting/multicollinearity as the limiting factor. Lasso underperforming at default alpha indicated over-aggressive feature elimination, not a useful signal. Random Forest's consistent improvement across every metric pointed to genuine non-linear structure — confirmed by feature importance results showing strong interaction-driven predictors like `same_state` outranking raw `distance_km`.

Notably, the hyperparameter-tuned Random Forest *underperformed* the untuned default on the held-out test set, despite a higher cross-validated score during the search — flagged here as an honest finding rather than smoothed over. See [Limitations](#limitations).

## What Drives the Predictions

| Feature | Importance |
|---|---|
| `seller_handling_days` | 0.172 |
| `same_state` | 0.133 |
| `customer_lat` | 0.099 |
| `distance_km` | 0.066 |
| `purchase_month` | 0.061 |
| `customer_lng` | 0.052 |
| `freight_value` | 0.039 |
| `price` | 0.037 |
| `seller_lng` / `seller_lat` | 0.031 each |

Two findings worth calling out: (1) seller dispatch speed is the dominant signal — see the framing note above; (2) absolute location (`same_state` + raw lat/lng, ~34.5% combined) outweighs relative distance (`distance_km`, 6.6%) by a wide margin, suggesting state-border/carrier-network effects matter more than straight-line distance.

## Leakage & Feature Validity

This model is built for a **post-dispatch** use case — re-estimating delivery time once a seller has shipped an order — not a checkout-time prediction. This distinction matters because:

- `seller_handling_days` (the top feature) is only known after carrier pickup
- `order_delivered_customer_date` and `order_estimated_delivery_date` are excluded from the feature set entirely (the former is the target's source; the latter is used only as a benchmark, never as a model input)
- `order_status` is filtered on (delivered orders only) rather than used as a feature

A checkout-time-only variant of this model is listed under Next Steps and would need to be trained and evaluated separately.

## Limitations

- Post-dispatch framing only (see above) — not validated for checkout-time prediction
- R²=0.478 leaves over half the variance unexplained, likely including irreducible operational randomness (carrier delays, weather, holidays) not represented in the dataset
- Hyperparameter tuning did not improve test-set performance in this run; the search space is a likely culprit, not a final answer
- ~0.5% of rows dropped due to missing geolocation matches, rather than imputed
- Distance is straight-line (Haversine), not actual road/carrier-route distance

## Next Steps

- Re-run hyperparameter search with a wider/different parameter space
- Build a checkout-time-only variant (drop post-dispatch features) for a fair "predict at the moment of purchase" comparison
- Test gradient boosting (XGBoost/LightGBM) against the current Random Forest
- Incorporate `order_payments` (boleto vs. card, installment count)
- Replace Haversine distance with real road-distance/drive-time from a routing API
- Validate whether tightening the delivery estimate (per the Olist benchmark) would increase the late-delivery rate, before treating it as a deployment recommendation

## Repository Structure

```
.
├── python_eda/
│   └── 01_data_loading_and_cleaning.ipynb   # raw CSV → cleaned parquet (run this first)
├── Delivery_Time_Estimation.ipynb            # full analysis notebook (this project)
├── README.md                                 # this file
└── data/                                      # Olist parquet files (generated, not committed — see Data Source)
```

## Data Source

This notebook does not read the raw Olist CSVs directly. It loads pre-cleaned `.parquet` files produced by **`python_eda/01_data_loading_and_cleaning.ipynb`**, which is the single upstream source for every dataset in this project (Delivery Time and Freight Value alike).

That notebook, run once against the raw [Olist Brazilian E-Commerce Public Dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce):

- Loads all nine raw CSVs (customers, geolocation, order_items, order_payments, order_reviews, orders, products, sellers, product_category_name_translation)
- Profiles each one (shape, dtypes, null counts, categorical value counts, duplicate checks)
- **Removes 261,831 duplicate rows from `geolocation`** — a separate cleaning step from the centroid-aggregation done later in this notebook; the upstream step removes exact full-row duplicates, while this notebook's `groupby().mean()` step handles legitimate multiple-address rows sharing a zip prefix
- **Pads zip-code prefixes to 5 digits** (`customers`, `geolocation`, `sellers`) — without this, prefixes with leading zeros get silently truncated when read as strings/ints, which would corrupt every downstream zip-based join
- Strips whitespace from all string columns
- Fills missing `product_category_name` with `'unknown'` rather than dropping those rows
- Exports each cleaned table to `.parquet` (and combines all of them into a single `olist.xlsx` workbook for ad hoc inspection)

**To reproduce this project from scratch:**
1. Download the raw CSVs from Kaggle into the same directory as `01_data_loading_and_cleaning.ipynb`
2. Run that notebook fully — it produces `customers.parquet`, `geolocation.parquet`, `order_items.parquet`, `order_payments.parquet`, `order_reviews.parquet`, `orders.parquet`, `products.parquet`, `sellers.parquet`, and `product_category_name_translation.parquet`
3. Place those parquet files alongside `Delivery_Time_Estimation.ipynb` (or adjust the load paths) and run this notebook
