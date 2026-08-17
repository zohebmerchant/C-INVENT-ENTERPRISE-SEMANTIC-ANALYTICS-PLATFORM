# C INVENT — Discovery + Navigation Fix

## Fixed

- Removed dependence on `GET /api/2.1/unity-catalog/tables` for catalog discovery. The prior implementation could fail with HTTP 400 on Databricks Free Edition/workspace variants.
- Databricks Discovery now uses Unity Catalog `INFORMATION_SCHEMA` through the configured Databricks SQL warehouse for catalogs, schemas, relations, and columns.
- Metric View identification is authoritative: candidate views are inspected with `DESCRIBE TABLE EXTENDED ... AS JSON`, which exposes `type: METRIC_VIEW`, measures (`is_measure`), YAML/view text, owner and comment.
- Added live declared foreign-key discovery from Unity Catalog `KEY_COLUMN_USAGE`, `TABLE_CONSTRAINTS`, and `REFERENTIAL_CONSTRAINTS` when the workspace exposes those metadata views.
- Discovery UI now shows schemas, relations, Metric Views, columns and declared relationships.
- Sidebar compressed to keep the full C INVENT navigation visible without a scrollbar at normal desktop height.
- C INVENT logo/brand moved to the top of the sidebar and spacing between Home, groups, and navigation items was reduced.

## Important behavior

C INVENT does not invent relationships in the live Databricks Discovery screen. If Unity Catalog has no declared foreign keys, the screen explicitly says no declared FK relationships are exposed. The C INVENT semantic-analysis screen can still show inferred relationships for onboarded files.
