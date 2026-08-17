# Travel demo dataset

## Intended semantic model

- **Fact table(s):** bookings.csv; payments.csv; booking_services.csv
- **Dimensions:** customers.csv, airports.csv, flights.csv
- **Measures:** Fare, payment, ancillary revenue, booking count
- **Relationships:** Bookings → Customers, Flights; Flights has two role-playing Airport FKs; Payments/Services → Bookings
- **Bridge table(s):** booking_services.csv is a booking-to-service line bridge

## Intentional edge cases

origin_airport_id and destination_airport_id need role-playing dimension handling; cancelled/refunded records challenge revenue definitions; customer PII and payments are sensitive.

All values are synthetic and fictional. IDs are deliberately consistent for valid joins. Rows with blank foreign keys, duplicate business attributes, and similar-looking identifiers are intentional: the platform should surface them as quality or semantic-review signals, not silently treat them as clean model relationships.
