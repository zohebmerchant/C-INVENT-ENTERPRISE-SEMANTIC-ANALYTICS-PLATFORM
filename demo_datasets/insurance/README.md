# Insurance demo dataset

## Intended semantic model

- **Fact table(s):** claims.csv
- **Dimensions:** customers.csv, agents.csv, vehicles.csv, policies.csv
- **Measures:** Claim amount; approved amount; claim count; premium amount
- **Relationships:** Claims → Policies → Customers, Agents, Vehicles
- **Bridge table(s):** claim_parties.csv is a Claims–Party bridge candidate; party master intentionally absent

## Intentional edge cases

Similar policy_id/claim_id names should not be cross-joined; duplicate claim-party pairs; sensitive PII and financial fields are included.

All values are synthetic and fictional. IDs are deliberately consistent for valid joins. Rows with blank foreign keys, duplicate business attributes, and similar-looking identifiers are intentional: the platform should surface them as quality or semantic-review signals, not silently treat them as clean model relationships.
