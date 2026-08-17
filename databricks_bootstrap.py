"""
Enterprise Semantic Analytics Platform — One-Time Bootstrap (PAT / Free
Edition version).

Run this ONCE, by whoever owns the Databricks Free Edition workspace,
before the platform is used for the first time. This replaces an
earlier OAuth-M2M-based bootstrap approach, which relies on
account-level service-principal infrastructure that Free Edition does
not provide (confirmed: "No access to the account console or
account-level APIs" — Databricks Free Edition limitations).

Under PAT auth, the platform runs as YOUR OWN workspace identity, not a
separate service principal — so there is no separate "grant privileges
to a service principal" step. What this script still does, once:

  1. Creates the dedicated catalog for this platform (fully separate
     from any other project's catalog)
  2. Verifies the SQL warehouse is reachable using your PAT
  3. Prints exactly what to paste into Streamlit secrets

Generate your PAT first (one-time, in the Databricks UI):
  Settings -> Developer -> Access Tokens -> Generate new token

Run this script with:
    python databricks_bootstrap.py --catalog invent_semantic_platform \
        --host https://your-workspace.cloud.databricks.com \
        --token <your PAT> \
        --warehouse-id <warehouse-id>
"""

from __future__ import annotations

import argparse
import sys

from databricks.sdk import WorkspaceClient
from databricks.sdk.core import Config
from databricks import sql as dbsql


def bootstrap(catalog: str, host: str, token: str, warehouse_id: str):
    print("=== Enterprise Semantic Analytics Platform — Bootstrap (PAT) ===\n")

    cfg = Config(host=host, token=token)
    w = WorkspaceClient(config=cfg)

    print(f"[1/3] Checking catalog '{catalog}'...")
    try:
        existing = w.catalogs.get(catalog)
        print(f"      Catalog already exists (created {existing.created_at}). Reusing it.")
    except Exception:
        print(f"      Creating catalog '{catalog}'...")
        w.catalogs.create(name=catalog, comment="Enterprise Semantic Analytics Platform — dedicated Invent 2026 catalog")
        print("      Created.")

    print(f"\n[2/3] Verifying SQL warehouse '{warehouse_id}' is reachable...")
    hostname = host.replace("https://", "").replace("http://", "")
    try:
        with dbsql.connect(
            server_hostname=hostname,
            http_path=f"/sql/1.0/warehouses/{warehouse_id}",
            credentials_provider=lambda: cfg.authenticate,
            catalog=catalog,
        ) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT current_user()")
                who = cur.fetchone()
        print(f"      Warehouse reachable. Authenticated as: {who[0]}")
    except Exception as e:
        print(f"      WARNING: could not connect — {e}")
        sys.exit(1)

    print("\n[3/3] Bootstrap complete. Paste the following into the app's Streamlit secrets:\n")
    print(f'DATABRICKS_HOST = "{host}"')
    print('DATABRICKS_TOKEN = "<your PAT — the same one used to run this script>"')
    print(f'DATABRICKS_WAREHOUSE_ID = "{warehouse_id}"')
    print(f'DATABRICKS_CATALOG = "{catalog}"')
    print("\nUnder PAT auth, the running app operates as your own workspace")
    print("identity — the same identity that just created this catalog already")
    print("has full rights on it. No separate GRANT step is needed for this")
    print("catalog itself. New per-domain schemas created during publish are")
    print("owned by this same identity automatically.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="One-time bootstrap (PAT / Free Edition)")
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--host", required=True)
    parser.add_argument("--token", required=True, help="Your Databricks Personal Access Token")
    parser.add_argument("--warehouse-id", required=True)
    args = parser.parse_args()

    bootstrap(catalog=args.catalog, host=args.host, token=args.token, warehouse_id=args.warehouse_id)
