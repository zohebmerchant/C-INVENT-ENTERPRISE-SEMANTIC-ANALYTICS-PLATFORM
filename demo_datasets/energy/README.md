# Energy demo dataset

## Intended semantic model

- **Fact table(s):** readings.csv; bills.csv
- **Dimensions:** customers.csv, sites.csv, meters.csv, tariffs.csv
- **Measures:** kWh consumed, peak kW, billing/due amount, reading count
- **Relationships:** Meters → Customers, Sites; Readings → Meters; Bills → Customers, Meters, Tariffs
- **Bridge table(s):** No mandatory bridge; tariff is time-effective and may require an as-of date join

## Intentional edge cases

Blank meter/tariff FKs; estimated readings; meter_number is sensitive identifier; customer details and billing data are sensitive.

All values are synthetic and fictional. IDs are deliberately consistent for valid joins. Rows with blank foreign keys, duplicate business attributes, and similar-looking identifiers are intentional: the platform should surface them as quality or semantic-review signals, not silently treat them as clean model relationships.
