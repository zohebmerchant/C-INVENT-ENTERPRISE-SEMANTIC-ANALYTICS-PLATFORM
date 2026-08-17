# Banking demo dataset

## Intended semantic model

- **Fact table(s):** transactions.csv
- **Dimensions:** customers.csv, accounts.csv, branches.csv, products.csv
- **Measures:** Total/average transaction amount; transaction count; current balance
- **Relationships:** Transactions → Accounts → Customers, Branches; AccountProducts → Accounts, Products
- **Bridge table(s):** account_products.csv represents Account–Product many-to-many membership

## Intentional edge cases

Blank account FK and amount; duplicate merchant/reference patterns; account_number and reference_number are identifier-like but not join keys; PII/financial fields include customer contact data, tax_id, balances and amounts.

All values are synthetic and fictional. IDs are deliberately consistent for valid joins. Rows with blank foreign keys, duplicate business attributes, and similar-looking identifiers are intentional: the platform should surface them as quality or semantic-review signals, not silently treat them as clean model relationships.
