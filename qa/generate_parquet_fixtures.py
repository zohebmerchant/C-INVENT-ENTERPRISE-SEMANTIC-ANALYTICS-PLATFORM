"""Generate real Parquet fixtures for INVENT ingestion QA.

Requires pyarrow (already pinned in requirements.txt).
"""
from pathlib import Path
import pandas as pd

out = Path(__file__).parent / "fixtures" / "parquet"
out.mkdir(parents=True, exist_ok=True)

fixtures = {
    "customers": pd.DataFrame({"customer_id": [1, 2, 3], "customer_name": ["A", "B", "C"]}),
    "orders": pd.DataFrame({"order_id": [101, 102, 103], "customer_id": [1, 2, 1], "amount": [100.0, 250.0, 75.0]}),
    "products": pd.DataFrame({"product_id": [10, 20], "product_name": ["Widget", "Gadget"]}),
}

for name, df in fixtures.items():
    df.to_parquet(out / f"{name}.parquet", index=False)

print(f"Generated {len(fixtures)} Parquet fixtures in {out}")
