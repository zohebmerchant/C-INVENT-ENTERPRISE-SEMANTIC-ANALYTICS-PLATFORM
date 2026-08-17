# Enterprise Semantic Analytics Platform — Invent 2026 Demo Datasets

This pack contains fictional, deterministic CSV datasets for ten business domains. It is designed to exercise the Streamlit platform's metadata profiling, relationship discovery, fact/dimension and measure inference, quality checks, security classification, semantic graph and analytics workflows.

## Domains

Healthcare, Banking, Insurance, Retail, Telecom, Manufacturing, Automotive, Travel, HR, and Energy. Each folder contains 5–6 CSV files and a domain README/data dictionary with its intended semantic model.

## Using in the Streamlit demo

1. Choose a domain in the demo selector, or upload every CSV from one domain folder together.
2. Run **Analyze Data** to profile metadata and produce relationship candidates.
3. Compare the result with that domain's `README.md` during validation or rehearsal.
4. Use the security panel to review deliberately included PII/PHI/financial examples.

## Design notes

- Valid PK/FK values are internally consistent for ordinary joins.
- A few intentional blanks, duplicate business attributes, unresolved IDs, role-playing dates/keys and multiple fact grains are included.
- Do not treat every same-named ID column as a valid relationship: domain READMEs identify expected edge cases.
- All names, contact details, identifiers and values are fictional synthetic data; they must not be used to make real decisions.

## Packaging

The ZIP retains this root folder and can be extracted directly into a Streamlit project as `demo_datasets/`.
