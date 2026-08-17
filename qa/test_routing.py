from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text()
THEME = (ROOT / "theme.py").read_text()
VIEWS = ROOT / "views"

assert not (ROOT / "pages").exists(), "Reserved Streamlit pages/ directory must not exist"
assert '"views"' in APP
assert "runpy.run_path" in APP
assert '"_invent_current_page"' in APP
assert '"Home"' in APP
assert "st.navigation(" not in APP
assert "st.Page(" not in APP
assert "st.switch_page(" not in APP
assert "st.sidebar.radio(" not in THEME
assert "st.button(" in THEME
assert "def navigate_to(" in THEME

required = [
    "0_Home.py", "1_Data_Onboarding.py", "2_AI_Analysis.py",
    "3_Semantic_Intelligence.py", "4_Business_Model.py", "5_Analytics.py",
    "6_Ask_AI.py", "7_Security_Center.py", "8_Genie.py", "9_QA_Validation.py",
]
for name in required:
    assert (VIEWS / name).exists(), f"Missing view: {name}"

for view in VIEWS.glob("*.py"):
    text = view.read_text()
    assert "st.switch_page(" not in text, view.name

onboarding = (VIEWS / "1_Data_Onboarding.py").read_text()
assert '"xml"' in onboarding
assert 'demo_domains = available_demo_domains()' in onboarding
assert 'st.session_state["onboarding_sample_domain"] = demo_domains[0]' in onboarding
assert 'st.session_state.onboarding_sample_domain = "Healthcare"' not in onboarding

print("INVENT v4.9 ROUTING/UI QA: PASS")
