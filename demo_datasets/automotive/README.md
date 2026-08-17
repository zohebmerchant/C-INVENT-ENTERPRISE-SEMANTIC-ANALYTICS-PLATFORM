# Automotive demo dataset

## Intended semantic model

- **Fact table(s):** service_orders.csv; service_parts.csv
- **Dimensions:** customers.csv, dealers.csv, vehicles.csv, parts.csv
- **Measures:** Labor cost, total service cost, part cost, service count
- **Relationships:** ServiceOrders → Vehicles, Dealers; Vehicles → Customers, Dealers; ServiceParts → ServiceOrders, Parts
- **Bridge table(s):** service_parts.csv bridges Service Orders and Parts

## Intentional edge cases

VIN is a sensitive unique identifier; service header/line grain needs aggregation awareness; duplicate customer city/name patterns are intentional.

All values are synthetic and fictional. IDs are deliberately consistent for valid joins. Rows with blank foreign keys, duplicate business attributes, and similar-looking identifiers are intentional: the platform should surface them as quality or semantic-review signals, not silently treat them as clean model relationships.
