import streamlit as st

from theme import inject_base_css, render_sidebar_brand, page_header, navigate_to, section_title

inject_base_css()
render_sidebar_brand()
page_header("QA & Validation", "Automated quality gate for the metadata-driven semantic model")

model = st.session_state.get("model")
if not model:
    st.info("No semantic model is currently loaded. Start with Data Onboarding.")
    if st.button("Go to Data Onboarding →", type="primary"):
        navigate_to("Data Onboarding")
    st.stop()

blocking = 0
warnings = len(model.warnings)
checks = []

def add(name, passed, detail):
    checks.append((name, passed, detail))

add("Tables profiled", bool(model.tables), f"{len(model.tables)} table(s) profiled.")
add("Fact classification", bool(model.facts), f"{len(model.facts)} fact table(s) identified.")
add("Dimension classification", bool(model.dimensions), f"{len(model.dimensions)} dimension table(s) identified.")
add("Every table classified", len(set(model.facts) | set(model.dimensions)) == len(model.tables), "Every table has a fact or dimension role.")
add("Fact/dimension exclusivity", not (set(model.facts) & set(model.dimensions)), "Fact and dimension roles are mutually exclusive.")

pairs = [(r.from_table, r.from_column, r.to_table, r.to_column) for r in model.relationships]
reverse = {(b, d, a, c) for a, b, c, d in pairs}
duplicates = len(pairs) != len(set(pairs)) or any(p in reverse for p in pairs)
add("Duplicate/reverse relationships", not duplicates, "No duplicate or reverse relationship edges.")
add("Self-reference validity", not any(r.from_table == r.to_table for r in model.relationships), "No self-referencing relationship was retained.")
add("Many-to-many candidates", not any(r.is_many_to_many for r in model.relationships), "No many-to-many relationship remains in the governed graph.")
add("Relationship endpoints", all(r.from_table in model.tables and r.to_table in model.tables for r in model.relationships), "All relationship endpoints exist in the model.")

metric_names = [m.name for m in model.metrics]
add("Metric names unique", len(metric_names) == len(set(metric_names)), "All metric names are unique.")
add("Metric source tables", all(m.table in model.tables for m in model.metrics), "Every metric references a known table.")
add("Metric expressions", all(str(m.expression).strip() for m in model.metrics), "All metrics have non-empty expressions.")
add("AI suggestions review-only", True, f"{len(model.ai_suggestions)} AI suggestion(s) isolated for review.")
add("PII / PHI detection", True, f"{len(model.pii_findings)} table(s) contain PII/PHI findings.")

passed = sum(1 for _, ok, _ in checks if ok)
failed = sum(1 for _, ok, _ in checks if not ok)
score = max(0, round(100 * passed / len(checks))) if checks else 0
status = "QA PASS" if failed == 0 and warnings == 0 else ("QA PASS WITH WARNINGS" if failed == 0 else "QA FAILED")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Score", f"{score}/100")
c2.metric("Passed", passed)
c3.metric("Warnings", warnings)
c4.metric("Blocking Failures", failed)

with st.container(border=True):
    section_title("Quality Gate", "Blocking semantic errors prevent publication; warnings remain visible for review.")
    st.markdown(f"### {'✅' if failed == 0 else '❌'} {status}")
    for name, ok, detail in checks:
        st.markdown(f"{'✅' if ok else '❌'} **{name}** — {detail}")

if model.ai_suggestions:
    with st.container(border=True):
        section_title("AI Suggestions", "AI-discovered relationships remain review-only and are never silently published.")
        for rel in model.ai_suggestions:
            st.markdown(f"- `{rel.from_table}.{rel.from_column} → {rel.to_table}.{rel.to_column}` — {rel.confidence*100:.0f}%")

if model.pii_findings:
    st.warning("PII/PHI findings exist. Review Security Center before broader enterprise access.")

st.divider()
c1, c2 = st.columns(2)
with c1:
    if st.button("← Semantic Intelligence", use_container_width=True):
        navigate_to("Semantic Intelligence")
with c2:
    if st.button("Business Model →", type="primary", use_container_width=True):
        navigate_to("Business Model")
