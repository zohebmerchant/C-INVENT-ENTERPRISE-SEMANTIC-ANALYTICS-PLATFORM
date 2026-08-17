# Telecom demo dataset

## Intended semantic model

- **Fact table(s):** usage.csv; tickets.csv
- **Dimensions:** customers.csv, plans.csv, devices.csv, towers.csv
- **Measures:** Total data MB, avg call minutes, SMS count, usage count, resolution hours
- **Relationships:** Usage → Customer, Plan, Device, Tower; Devices → Customer; Tickets → Customer, Tower
- **Bridge table(s):** usage.csv has a multi-dimension event grain rather than a bridge

## Intentional edge cases

customer_id appears in both event tables; IMEI is sensitive identifier; usage records are intentionally high cardinality and time-series.

All values are synthetic and fictional. IDs are deliberately consistent for valid joins. Rows with blank foreign keys, duplicate business attributes, and similar-looking identifiers are intentional: the platform should surface them as quality or semantic-review signals, not silently treat them as clean model relationships.
