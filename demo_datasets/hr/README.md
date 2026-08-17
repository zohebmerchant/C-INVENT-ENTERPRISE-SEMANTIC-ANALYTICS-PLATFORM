# HR demo dataset

## Intended semantic model

- **Fact table(s):** attendance.csv; payroll.csv
- **Dimensions:** employees.csv, departments.csv, locations.csv
- **Measures:** Hours, overtime, gross salary, bonus, tax, headcount
- **Relationships:** Employees → Departments, Locations, self-manager; Attendance/Payroll → Employees
- **Bridge table(s):** employee_benefits.csv is an Employee–Benefit bridge; benefit master is intentionally absent

## Intentional edge cases

Self-referencing manager hierarchy; missing manager IDs for executives; salaries, tax, DOB, contact details are highly sensitive PII/financial data.

All values are synthetic and fictional. IDs are deliberately consistent for valid joins. Rows with blank foreign keys, duplicate business attributes, and similar-looking identifiers are intentional: the platform should surface them as quality or semantic-review signals, not silently treat them as clean model relationships.
