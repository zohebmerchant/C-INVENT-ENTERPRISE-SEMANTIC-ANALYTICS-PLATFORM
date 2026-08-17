# Healthcare demo dataset

## Intended semantic model

- **Fact table(s):** encounters.csv; treatments.csv
- **Dimensions:** patients.csv, investigators.csv, sites.csv
- **Measures:** Average heart rate/BP; encounter count; average duration; treatment count
- **Relationships:** Encounters → Patients, Investigators; Investigators → Sites; Patients → Sites
- **Bridge table(s):** treatments.csv is a Patient–Drug bridge candidate; Drug dimension is intentionally absent

## Intentional edge cases

Duplicate patient display name; blank investigator FK; blank clinical measure; treatment has an unresolved drug_id; PHI/PII includes name, email, phone, date_of_birth and clinical readings.

All values are synthetic and fictional. IDs are deliberately consistent for valid joins. Rows with blank foreign keys, duplicate business attributes, and similar-looking identifiers are intentional: the platform should surface them as quality or semantic-review signals, not silently treat them as clean model relationships.
