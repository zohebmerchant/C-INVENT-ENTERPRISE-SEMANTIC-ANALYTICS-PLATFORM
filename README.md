# C INVENT — Enterprise Semantic Analytics Platform

## Production Product README — 2026

> **Discover. Understand. Govern. Publish. Analyze. Ask.**

C INVENT is a metadata-driven Enterprise Semantic Analytics Platform that takes enterprise data from onboarding and discovery through AI-assisted semantic modelling, quality validation, governed Databricks publication, analytics and natural-language AI consumption.

The platform is designed to work across business domains without creating a separate application for every domain.

---

# 1. What C INVENT Does

C INVENT brings the following capabilities into one application:

- Data Onboarding
- Databricks Discovery
- Unity Catalog discovery
- AI Analysis
- Semantic Intelligence
- Business Model
- QA Validation
- Governed Publication
- Analytics
- Ask AI
- Databricks Genie AI
- Security Center
- Connectors
- Audit & Policies
- Role-Based Access Control (RBAC)
- User identity and role visibility

The platform uses a metadata-driven approach so the same application experience can support domains such as:

- Retail
- Human Resources
- Travel
- Telecom
- Automotive
- Energy
- Insurance
- Healthcare
- Finance
- Other enterprise domains

---

# 2. Product Architecture

```text
                         C INVENT
                            │
              ┌─────────────┴─────────────┐
              │                           │
       DATA / DISCOVERY              AI / SEMANTIC
              │                           │
      ┌───────┴────────┐          ┌───────┴────────┐
      │                │          │                │
Data Onboarding   Databricks   AI Analysis   Semantic Intelligence
      │            Discovery        │                │
      │                │            └───────┬────────┘
      │                │                    │
      └────────────────┴──────────── Business Model
                                             │
                                             ▼
                                       QA Validation
                                             │
                                             ▼
                                          Publish
                                             │
                              ┌──────────────┴──────────────┐
                              │                             │
                           Analytics                    AI Consumption
                                                            │
                                                   ┌────────┴────────┐
                                                   │                 │
                                                Ask AI          Genie AI

                         Databricks / Unity Catalog
                                   │
                    ┌──────────────┼──────────────┐
                    │              │              │
               Delta Tables    Metric Views      Genie
```

---

# 3. End-to-End User Journey

The intended C INVENT flow is:

```text
Home
  ↓
Data Onboarding
  ↓
Databricks Discovery
  ↓
AI Analysis
  ↓
Semantic Intelligence
  ↓
Business Model
  ↓
QA Validation
  ↓
Publish
  ↓
Analytics
  ↓
Ask AI / Genie AI
```

The application also provides governance and administration capabilities through:

```text
Security Center
Connectors
Audit & Policies
Deployment Verification
```

---

# 4. Data Onboarding

Data Onboarding is the starting point for bringing a new business domain into C INVENT.

Supported file types include:

- CSV
- XLSX
- JSON
- Parquet
- XML

The intended experience is:

```text
Choose Domain
      ↓
Choose Source
      ↓
Upload / Connect Data
      ↓
Analyze Data
```

The platform then passes the discovered structures into the semantic intelligence workflow.

---

# 5. Databricks Discovery

Databricks Discovery provides a separate path for data that already exists in Databricks.

It is intended to discover:

- Unity Catalog catalogs
- Schemas
- Tables
- Columns
- Table metadata
- Relationships
- Published Metric Views
- Existing governed analytical assets

Example:

```text
invent_semantic_platform
        │
        ├── domain_hr
        │     ├── attendance
        │     ├── departments
        │     ├── employees
        │     ├── payroll
        │     └── mv_domain
        │
        ├── domain_retail
        │     ├── orders
        │     ├── order_items
        │     ├── products
        │     └── mv_domain
        │
        └── other domains
```

C INVENT is intended to use the actual Databricks/Unity Catalog metadata rather than relying only on hard-coded application assumptions.

---

# 6. AI Analysis

AI Analysis examines the onboarded data and helps identify the analytical structure.

The analysis can identify:

- Tables
- Columns
- Row counts
- Candidate fact tables
- Candidate dimension tables
- Relationships
- Relationship confidence
- Candidate measures
- Data-quality observations
- PII / PHI indicators
- Business terminology

Example:

```text
Tables Analyzed        6
Relationships Found    6
Fact Tables            2
Dimension Tables       4
```

---

# 7. Semantic Intelligence

Semantic Intelligence turns technical data structures into an understandable business semantic model.

It provides views for:

- Tables
- Relationships
- Metrics
- Glossary

Example:

```text
attendance.csv       FACT
departments.csv      DIMENSION
employees.csv        DIMENSION
locations.csv        DIMENSION
payroll.csv          FACT
```

Relationship evidence can include:

```text
Column names match
Referential coverage
Key uniqueness
Relationship confidence
N:1 classification
```

The platform also surfaces PII/PHI findings where detected.

---

# 8. Business Model

The Business Model presents the semantic graph before publication.

Example:

```text
order_items
     │
     ├── products
     │
     └── orders
           ├── stores
           └── customers
```

The Business Model allows users to review:

- Fact tables
- Dimension tables
- Direct relationships
- Indirect relationships
- Relationship confidence
- Many-to-many relationships
- Semantic warnings

The model is reviewed before publication.

---

# 9. QA Validation

QA Validation provides a checkpoint before the model is published.

The QA stage is intended to identify:

- Relationship problems
- Semantic inconsistencies
- Missing information
- Data-quality warnings
- Metric issues
- Publication-readiness problems
- Sensitive-data considerations

The intended flow is:

```text
Semantic Model
      ↓
QA Validation
      ↓
Pass / Warnings / Failure
      ↓
Publish when ready
```

---

# 10. Governed Publication

C INVENT publishes the semantic model into Databricks.

The publication pattern is:

```text
Source Data
     ↓
Governed Delta Tables
     ↓
Canonical Domain Metric View
     ↓
Analytics / AI Consumption
```

A published domain exposes a canonical Metric View.

Example:

```text
Catalog:
invent_semantic_platform

Schema:
domain_hr

Metric View:
invent_semantic_platform.domain_hr.mv_domain
```

For another domain:

```text
invent_semantic_platform.domain_retail.mv_domain
```

The exact measures and source tables are domain-specific.

---

# 11. Metric View Architecture

The Metric View is the governed analytical entry point for a published domain.

The design principle is:

> **The domain owns one canonical governed semantic entry point rather than creating an unrelated Metric View for every detected fact table.**

Multiple fact tables can contribute to the domain's governed semantic model.

For example:

```text
Domain: HR

Fact Tables:
2

Dimensions:
4

Canonical Metric View:
invent_semantic_platform.domain_hr.mv_domain
```

The Metric View exposes the governed measures required by the domain.

---

# 12. Analytics

Analytics is generated from the published semantic metadata.

The same rendering approach can support multiple domains.

Example:

```text
Active Domain:
travel

Fact Tables:
3

Metric View:
invent_semantic_platform.domain_travel.mv_domain
```

Analytics can expose:

- Key metrics
- Published measures
- Domain information
- Source statistics
- Governed semantic model information

The objective is to avoid building separate hard-coded analytics applications for every domain.

---

# 13. Ask AI

Ask AI provides the C INVENT application-level natural-language analytics experience.

Users can ask questions against the selected published semantic model.

Examples:

```text
What are the main business metrics?

Show the top customers by total revenue.

Which stores are performing best?

Give me the key business insight from this domain.
```

Ask AI is intended for users who want conversational analytics inside the C INVENT experience.

---

# 14. Genie AI

Genie AI provides the Databricks-native conversational analytics channel.

The relationship is:

```text
C INVENT
   │
   ▼
Governed Semantic Model
   │
   ▼
Canonical Metric View
   │
   ▼
Databricks Genie
   │
   ▼
Natural-language Analytics
```

A published domain can have a connected Genie Agent.

Example:

```text
Domain:
HR

Metric View:
invent_semantic_platform.domain_hr.mv_domain

Genie Agent:
<environment-specific Agent ID>
```

The Agent ID is environment-specific and should not be hard-coded into documentation.

---

# 15. Ask AI vs Genie AI

These capabilities are complementary.

| Capability | Ask AI | Genie AI |
|---|---:|---:|
| C INVENT user experience | ✓ | |
| Application-controlled context | ✓ | |
| Natural-language analytics | ✓ | ✓ |
| Governed Metric View | ✓ | ✓ |
| Databricks-native Genie experience | | ✓ |
| Databricks Genie Agent | | ✓ |
| Business-user consumption | ✓ | ✓ |

### Simple explanation

**Ask AI**

> Conversational analytics inside C INVENT.

**Genie AI**

> Databricks-native conversational analytics over the governed semantic model.

C INVENT remains the semantic-model and governance experience, while Databricks provides the governed data and AI execution capabilities.

---

# 16. Role-Based Access Control

C INVENT provides five intended application roles.

| Role | Primary Purpose |
|---|---|
| **Admin** | Full platform administration |
| **Data Engineer** | Build and validate semantic models |
| **Analyst** | Analytics and Ask AI |
| **Business User** | Analytics and Genie |
| **Viewer** | Published Analytics only |

---

## Admin

The Admin has the broadest C INVENT access.

### Admin capabilities

- Home
- Data Onboarding
- Databricks Discovery
- AI Analysis
- Semantic Intelligence
- Business Model
- QA Validation
- Analytics
- Ask AI
- Genie AI
- Security Center
- Connectors
- Audit & Policies
- Deployment Verification
- Publishing
- Platform administration

### Purpose

> Own and operate the C INVENT platform.

---

## Data Engineer

The Data Engineer works on the build and validation side.

### Data Engineer capabilities

- Data Onboarding
- Databricks Discovery
- AI Analysis
- Semantic Intelligence
- Business Model
- QA Validation

### Purpose

> Build, review and validate governed semantic models.

---

## Analyst

The Analyst is a consumer of governed data.

### Analyst capabilities

- Analytics
- Ask AI

### Purpose

> Analyze governed information and ask business questions.

---

## Business User

The Business User is focused on business consumption.

### Business User capabilities

- Analytics
- Genie AI

### Purpose

> Consume governed analytics and interact with Databricks Genie.

---

## Viewer

The Viewer has read-only analytical access.

### Viewer capabilities

- Analytics

### Purpose

> View approved published analytics.

---

# 17. User Identity in the UI

After authentication, C INVENT displays the signed-in user and role in the navigation area.

Example:

```text
┌──────────────────────────────┐
│  Z  Zoheb Merchant            │
│     Admin                     │
│     zoheb.amir-merchant@...   │
└──────────────────────────────┘
```

Other examples:

```text
Ruchika Gusain
Data Engineer
```

```text
Mohit B. Chauhan
Analyst
```

```text
Shilpi Aggarwal
Business User
```

```text
Soyal Kakkar
Viewer
```

The role is derived from the authenticated session and is used for application-level access control.

---

# 18. Authentication Configuration

Authentication can be enabled through Streamlit Secrets:

```toml
CINVENT_AUTH_ENABLED = true
```

The user records contain:

```toml
[CINVENT_USER_ADMIN]
email = "..."
name = "Zoheb Merchant"
role = "Admin"
enabled = true
must_change_password = false
salt = "..."
password_hash = "..."
```

The current authentication loader also supports the existing plural section convention:

```toml
[CINVENT_USERS_ENGINEER]
```

However, the recommended production convention is:

```text
CINVENT_USER_ADMIN
CINVENT_USER_ENGINEER
CINVENT_USER_ANALYST
CINVENT_USER_BUSINESS
CINVENT_USER_VIEWER
```

Passwords are represented through salted hashes rather than being stored as plain-text passwords.

---

# 19. Navigation

C INVENT uses a consistent navigation structure.

```text
C INVENT
│
├── Home
│
├── ONBOARD
│   ├── Data Onboarding
│   └── Databricks Discovery
│
├── MODEL
│   ├── AI Analysis
│   ├── Semantic Intelligence
│   ├── Business Model
│   └── QA Validation
│
├── ANALYZE
│   ├── Analytics
│   ├── Ask AI
│   └── Genie AI
│
└── GOVERN
    ├── Security Center
    ├── Connectors
    ├── Audit & Policies
    └── Deployment Verification
```

The navigation is role-aware.

Users should see only the capabilities assigned to their role.

---

# 20. Security and Governance

C INVENT surfaces security considerations as part of the semantic workflow.

The platform can identify PII/PHI-sensitive columns and recommend security review.

Example:

```text
PII / PHI detected

Masking and access review are recommended
before broader access is granted.
```

C INVENT should be used together with enterprise Databricks governance.

Application RBAC does **not** replace:

- Unity Catalog permissions
- Databricks access controls
- Enterprise identity
- Data masking
- Row-level security
- Column-level security
- Network controls
- Audit requirements

---

# 21. Databricks Foundation

The intended platform architecture uses Databricks capabilities including:

- Unity Catalog
- Delta tables
- Metric Views
- Databricks SQL
- Genie

Conceptually:

```text
              C INVENT
                  │
                  ▼
        Semantic / Metadata Layer
                  │
                  ▼
           Unity Catalog
                  │
        ┌─────────┼─────────┐
        ▼         ▼         ▼
      Delta    Metric      Genie
     Tables     Views       AI
        │         │          │
        └─────────┴──────────┘
                  │
             Business Users
```

---

# 22. Multi-Domain Model

Each business domain can have its own governed schema.

Example:

```text
invent_semantic_platform
│
├── domain_hr
│     └── mv_domain
│
├── domain_retail
│     └── mv_domain
│
├── domain_travel
│     └── mv_domain
│
├── domain_telecome
│     └── mv_domain
│
└── other domains
      └── mv_domain
```

The semantic content varies by domain while the application framework remains reusable.

---

# 23. Example — HR Domain

Example source tables:

```text
attendance
departments
employee_benefits
employees
locations
payroll
```

Example semantic result:

```text
Tables Analyzed:       6
Relationships Found:   6
Fact Tables:           2
Dimension Tables:      4
```

Published Metric View:

```text
invent_semantic_platform.domain_hr.mv_domain
```

Example governed measures:

```text
total_hours_worked
total_overtime_hours
attendance_count
payroll_total_gross_salary
payroll_total_bonus_amount
payroll_total_tax_deducted
payroll_count
```

The domain can then be consumed through:

```text
Analytics
Ask AI
Genie AI
```

according to the user's role.

---

# 24. Example — Retail Domain

Example entities:

```text
order_items
orders
products
stores
customers
promotions
```

The semantic model can identify:

```text
order_items → products
order_items → orders
orders → stores
orders → customers
```

The final domain is published through its canonical Metric View:

```text
invent_semantic_platform.domain_retail.mv_domain
```

---

# 25. Event Demonstration Script

For a product showcase, use this sequence.

### 1. Start at Home

Show:

- C INVENT branding
- Platform overview
- Navigation
- Signed-in user and role

### 2. Data Onboarding

Upload or select a sample domain.

### 3. AI Analysis

Show automatic discovery of:

- Tables
- Facts
- Dimensions
- Relationships
- Metrics
- PII/PHI

### 4. Semantic Intelligence

Show:

```text
Tables
Relationships
Metrics
Glossary
```

### 5. Business Model

Show the semantic graph.

### 6. QA Validation

Show the quality and readiness checks.

### 7. Publish

Show:

```text
Delta Tables
+
Canonical Metric View
+
Genie Agent
```

### 8. Databricks Discovery

Open the Databricks Discovery experience and demonstrate the corresponding governed assets.

### 9. Analytics

Show domain analytics generated from the published semantic metadata.

### 10. Ask AI

Ask a natural-language business question.

### 11. Genie AI

Demonstrate the Databricks-native Genie experience.

### 12. RBAC

Show different users:

```text
Zoheb      → Admin
Ruchika    → Data Engineer
Mohit      → Analyst
Shilpi     → Business User
Soyal      → Viewer
```

and demonstrate how the navigation changes according to role.

---

# 26. Enterprise Value Proposition

C INVENT addresses the gap between raw enterprise data and trusted business insight.

Traditional workflow:

```text
Data
 ↓
Manual discovery
 ↓
Manual modelling
 ↓
Engineering
 ↓
Separate dashboards
 ↓
Separate AI implementation
```

C INVENT workflow:

```text
Data
 ↓
AI-assisted discovery
 ↓
Semantic Intelligence
 ↓
Business Model
 ↓
QA
 ↓
Governed Metric View
 ↓
Analytics
 ↓
Ask AI / Genie
```

The key value is the reusable semantic foundation.

---

# 27. Design Principles

### Metadata-driven

Domain behaviour should be driven by metadata rather than hard-coded domain-specific logic.

### Governed

The analytical model should be represented through governed Databricks assets.

### Reusable

The same C INVENT application should support multiple domains.

### AI-assisted

AI should accelerate discovery and semantic interpretation rather than replace governance review.

### Role-aware

Different users should receive only the capabilities appropriate to their responsibilities.

### Business-friendly

Technical data structures should be presented in understandable business concepts.

### Databricks-aligned

C INVENT complements Databricks rather than replacing Unity Catalog, Delta Lake, Metric Views or Genie.

---

# 28. Production Readiness Checklist

Before an enterprise production rollout, verify:

- [ ] Authentication enabled
- [ ] All user roles tested
- [ ] User identity visible after login
- [ ] RBAC navigation tested
- [ ] Unity Catalog permissions configured
- [ ] Databricks credentials rotated and stored securely
- [ ] Capgemini LLM credentials stored securely
- [ ] Data connectors tested
- [ ] CSV tested
- [ ] XLSX tested
- [ ] JSON tested
- [ ] Parquet tested
- [ ] XML tested
- [ ] Databricks Discovery tested
- [ ] AI Analysis tested
- [ ] Semantic Intelligence tested
- [ ] Business Model tested
- [ ] QA Validation tested
- [ ] Delta publication tested
- [ ] Canonical Metric View verified in Unity Catalog
- [ ] Analytics tested
- [ ] Ask AI tested
- [ ] Genie Agent tested
- [ ] PII/PHI governance reviewed
- [ ] Audit requirements reviewed
- [ ] Production monitoring configured

---

# 29. Final Product Statement

## C INVENT

> **A metadata-driven enterprise semantic analytics platform that transforms raw and existing enterprise data into governed semantic models, Databricks Metric Views, analytics and AI-powered business insight.**

```text
DISCOVER
    ↓
UNDERSTAND
    ↓
MODEL
    ↓
VALIDATE
    ↓
GOVERN
    ↓
PUBLISH
    ↓
ANALYZE
    ↓
ASK
```

### One platform.
### Multiple business domains.
### One governed semantic foundation.
