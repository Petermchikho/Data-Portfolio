# Olist E-Commerce — Python Analysis Notebook
**Project:** Olist E-Commerce Dataset | Quantify Analytics Labs  
**Author:** Peter Mchikho  
**Dataset Period:** September 2016 – August 2018 (99,441 orders)

> This document is a living analytical record. Each section answers one business
> question using Python, with findings, visualisations, and methodology documented
> as they are completed.

---

## Table of Contents

| # | Business Question | Status |
|---|---|---|
| [Q1](#q1-month-on-month-trend-in-total-orders-and-gmv) | What is the month-on-month trend in total orders and GMV over the full dataset period? |  Complete |

---

## Q1: Month-on-Month Trend in Total Orders and GMV

**Date Completed:** June 2026  
**Query Reference:** `ql_olist_query_02_monthly_gmv.sql`

### Objective

Understand how order volume and Gross Merchandise Value (GMV) evolved month by month
across the full dataset period, decomposed into product revenue and freight revenue,
to establish the platform's growth trajectory and identify key inflection points.

---

### Dashboard

![Monthly Business Performance Dashboard](./results/monthly_business_dashboard.png)

---

### Key Findings

**Overall Growth**  
The platform scaled from just 3 orders and R$355 GMV in September 2016 to a sustained
monthly run rate of 6,000–7,500 orders generating over R$1M GMV by early 2018 — roughly
a 3,000x increase in GMV across the two-year window.

**Peak Month — November 2017 (Black Friday)**  
The single highest-volume month was November 2017, driven by Brazil's Black Friday
campaign. It recorded 7,451 orders and R$1,179,144 GMV — the only month to breach the
R$1M ceiling before 2018, and clearly visible as an outlier spike in both the Orders
Trend and GMV Trend charts.

**Sustained Scale in 2018**  
From January through August 2018, monthly GMV consistently exceeded R$1M, confirming
that the November 2017 spike translated into durable platform growth rather than a
one-off event. The range across this period was R$987K (June 2018) to R$1,160K
(March 2018).

**Freight as a Stable Share of GMV**  
Freight revenue tracked product revenue closely throughout, averaging approximately
14–16% of GMV each month. This consistency indicates a stable cost-pass-through
structure — freight pricing scales proportionally with order value rather than being
compressed or inflated by volume changes.

**Data Cutoff Artefact**  
September 2018 shows a single order (R$166 GMV), and December 2016 shows only 1 order.
These are dataset boundary artefacts, not business events, and are excluded from
trend modelling.



*Next: [Q2 — add next business question here]*

---

*Quantify Analytics Labs — Olist E-Commerce Dataset Project*
