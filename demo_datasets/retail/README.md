# Retail demo dataset

## Intended semantic model

- **Fact table(s):** order_items.csv (primary); orders.csv header fact
- **Dimensions:** customers.csv, products.csv, stores.csv, promotions.csv
- **Measures:** Sales amount; quantity; order count; average order value; discount
- **Relationships:** OrderItems → Orders, Products; Orders → Customers, Stores; Promotions → Products
- **Bridge table(s):** order_items.csv bridges Orders and Products

## Intentional edge cases

Blank product FK; duplicate customer email; orders and order_items have separate grain; promotion date range needs temporal join logic; customer contact fields are PII.

All values are synthetic and fictional. IDs are deliberately consistent for valid joins. Rows with blank foreign keys, duplicate business attributes, and similar-looking identifiers are intentional: the platform should surface them as quality or semantic-review signals, not silently treat them as clean model relationships.
