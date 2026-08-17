# Manufacturing demo dataset

## Intended semantic model

- **Fact table(s):** production_runs.csv; defects.csv; maintenance.csv
- **Dimensions:** plants.csv, machines.csv, products.csv
- **Measures:** Units produced, downtime, defect quantity/cost, maintenance cost
- **Relationships:** ProductionRuns → Plants, Machines, Products; Defects → ProductionRuns; Maintenance → Machines
- **Bridge table(s):** No mandatory bridge; machines and products are independently related through production runs

## Intentional edge cases

Multiple fact grains; units_planned vs units_produced supports yield KPI; machine_id and maintenance_id look like IDs and must not be measures.

All values are synthetic and fictional. IDs are deliberately consistent for valid joins. Rows with blank foreign keys, duplicate business attributes, and similar-looking identifiers are intentional: the platform should surface them as quality or semantic-review signals, not silently treat them as clean model relationships.
