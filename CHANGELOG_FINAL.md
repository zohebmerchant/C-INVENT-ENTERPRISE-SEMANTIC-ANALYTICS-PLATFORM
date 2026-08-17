# C INVENT Final Build — verification notes

## Important finding from v5.0 evidence

The v5 semantic analysis correctly detected the Travel topology as 3 facts:
`booking_services.csv`, `bookings.csv`, `payments.csv`.

However, the v5 `publish_engine.py` generated the Metric View from `fact_table` only. Therefore the UI could show `Fact Tables = 3` while the governed Metric View contained only the selected primary fact's measures. That is the defect fixed in this final build.

## Final fix

`publish_engine.py` now:

- writes every detected fact and dimension as Delta;
- creates an internal `_invent_mv_domain_source` union relation containing every fact;
- exposes one canonical `mv_domain` Metric View per domain;
- exposes measures from every fact through that single Metric View;
- preserves the primary fact's clean measure names and namespaces additional fact measures;
- exposes conformed dimension fields through safe FK→PK paths;
- removes legacy `mv_<fact>` Metric Views without dropping Delta tables.

## Genie fixes

- No stale `GENIE_SPACE_ID` is required when `GENIE_AUTO_CREATE=true`.
- Existing `INVENT — <domain>` Agent is recovered and reused.
- The Agent receives only the canonical `mv_domain` Metric View as its INVENT semantic source.
- HTTP 409 UpdateSpace conflicts are retried without a stale etag.
- Repeated publish does not intentionally create another Agent for the same domain.

## Discovery

`discovery_engine.py` uses real Databricks Unity Catalog metadata. Metric Views are discovered from the Databricks Tables API rather than inferred from the local registry.

## UI / routing

- C INVENT branding and logo.
- Stable button-based sidebar; no radio navigation.
- Home is always the first navigation item.
- Govern is visible and includes Databricks Discovery, Security Center, Connectors and Audit.
- Browser F5/reload is detected through `streamlit-js-eval` and returns the current session to Home once per reload.
- Normal button reruns retain the active page.
- New sessions start at Home.

## File formats

CSV, XLSX, XLS, JSON, Parquet and XML are enabled. `pyarrow` is pinned in requirements for Parquet.

## Local verification completed

- Python compilation: PASS
- 10 bundled domains semantic QA: PASS
- Travel topology regression: PASS
- Travel facts: 3
- Travel relationships: 4
- Generated canonical Metric View measures: 6
- All 3 Travel facts represented in the generated source relation: PASS
- XML ingestion: PASS
- Parquet ingestion test is deployment-dependent in the build container; `pyarrow` is included in requirements.

## Build fingerprint / deployment verification

The final package now displays `C-INVENT-2026.08.14-FINAL-02` on Home and exposes a Deployment Verification page. This prevents an old Streamlit Cloud repository build from being mistaken for the final package.

The sidebar explicitly contains:
- ONBOARD: Data Onboarding, Databricks Discovery
- MODEL: AI Analysis, Semantic Intelligence, Business Model, QA Validation
- ANALYZE: Analytics, Ask AI, Genie AI
- GOVERN: Security Center, Connectors, Audit & Policies, Deployment Verification
