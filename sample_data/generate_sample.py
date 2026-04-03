"""
Sample Data Generator
=====================
Generates a synthetic sales dataset (1,000 rows, ~15 columns)
with intentional data quality issues for demo purposes.
"""

import os
import random
from datetime import datetime, timedelta

import numpy as np
import pandas as pd


def generate_sample_sales(n_rows: int = 1000, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    random.seed(seed)

    regions = ["North", "South", "East", "West", "Central"]
    categories = ["Electronics", "Clothing", "Food & Beverage", "Home & Garden", "Sports"]
    sales_reps = [f"Rep_{i:03d}" for i in range(1, 31)]
    channels = ["Online", "Retail Store", "Wholesale", "Direct Sales"]
    statuses = ["Completed", "Completed", "Completed", "Pending", "Refunded"]

    start_date = datetime(2023, 1, 1)

    data = {
        "Order_ID": [f"ORD-{100000 + i}" for i in range(n_rows)],
        "Order_Date": [
            (start_date + timedelta(days=int(rng.integers(0, 365)))).strftime("%Y-%m-%d")
            for _ in range(n_rows)
        ],
        "Region": rng.choice(regions, n_rows),
        "Category": rng.choice(categories, n_rows),
        "Product_Name": [f"Product_{rng.integers(1, 200):03d}" for _ in range(n_rows)],
        "Sales_Rep": rng.choice(sales_reps, n_rows),
        "Channel": rng.choice(channels, n_rows),
        "Units_Sold": rng.integers(1, 500, n_rows),
        "Unit_Price": np.round(rng.uniform(5.0, 2000.0, n_rows), 2),
        "Discount_Pct": np.round(rng.uniform(0, 0.35, n_rows), 3),
        "Status": rng.choice(statuses, n_rows),
        "Customer_Rating": np.round(rng.uniform(1.0, 5.0, n_rows), 1),
        "Return_Flag": rng.choice([True, False], n_rows, p=[0.08, 0.92]),
        "Delivery_Days": rng.integers(1, 30, n_rows),
        "Notes": [None] * n_rows,  # intentionally empty column for quality testing
    }

    df = pd.DataFrame(data)

    # Derived columns
    df["Revenue"] = np.round(df["Units_Sold"] * df["Unit_Price"] * (1 - df["Discount_Pct"]), 2)
    df["Cost"] = np.round(df["Revenue"] * rng.uniform(0.45, 0.75, n_rows), 2)
    df["Profit"] = np.round(df["Revenue"] - df["Cost"], 2)

    # Intentional data quality issues
    # 1. Inject ~8% nulls in Unit_Price and Customer_Rating
    null_idx_price = rng.choice(n_rows, size=int(n_rows * 0.08), replace=False)
    null_idx_rating = rng.choice(n_rows, size=int(n_rows * 0.07), replace=False)
    df.loc[null_idx_price, "Unit_Price"] = np.nan
    df.loc[null_idx_rating, "Customer_Rating"] = np.nan

    # 2. A few extreme Revenue outliers
    df.loc[rng.choice(n_rows, 5, replace=False), "Revenue"] = rng.uniform(500_000, 2_000_000, 5)

    # 3. Duplicate rows (10 rows)
    dup_idx = rng.choice(n_rows, 10, replace=False)
    df = pd.concat([df, df.iloc[dup_idx]], ignore_index=True)

    return df


if __name__ == "__main__":
    out_dir = os.path.dirname(__file__)
    out_path = os.path.join(out_dir, "sample_sales.xlsx")
    df = generate_sample_sales()
    df.to_excel(out_path, index=False, engine="openpyxl")
    print(f"✅ Generated {len(df):,} rows → {out_path}")
    print(df.describe(include="all").T[["count", "unique", "top", "freq"]].head(20))
