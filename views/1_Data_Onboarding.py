import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path

from theme import navigate_to, inject_base_css, render_sidebar_brand, page_header
from data_engine import load_uploaded_files, prepare_files, source_capabilities


inject_base_css()
render_sidebar_brand()

page_header(
    "Data Onboarding",
    "Upload files, or try a sample domain — no Databricks knowledge required",
)


# =============================================================================
# SESSION STATE
# =============================================================================

if "domain_name" not in st.session_state:
    st.session_state.domain_name = ""

if "uploaded_files" not in st.session_state:
    st.session_state.uploaded_files = {}

if "model" not in st.session_state:
    st.session_state.model = None

if "stage" not in st.session_state:
    st.session_state.stage = "upload"

if "llm_suggestion_count" not in st.session_state:
    st.session_state.llm_suggestion_count = 0

# Stable widget state. These must NOT be overwritten during rendering.
if "onboarding_source" not in st.session_state:
    st.session_state.onboarding_source = "Upload files"

# The sample selector is driven only by the checked-in demo-domain inventory.
# Never hard-code Healthcare as the default.

if "onboarding_upload_domain" not in st.session_state:
    st.session_state.onboarding_upload_domain = ""


# =============================================================================
# SAMPLE DATA
# =============================================================================


DEMO_DATA_DIR = (
    Path(__file__).resolve().parent.parent
    / "demo_datasets"
)


@st.cache_data(show_spinner=False)
def available_demo_domains() -> list[str]:
    if not DEMO_DATA_DIR.exists():
        return []

    return sorted(
        p.name
        for p in DEMO_DATA_DIR.iterdir()
        if p.is_dir()
        and not p.name.startswith(".")
        and any(
            f.is_file()
            and f.suffix.lower() == ".csv"
            for f in p.iterdir()
        )
    )


@st.cache_data(show_spinner=False)
def load_sample_domain(choice: str) -> dict[str, pd.DataFrame]:
    """
    Load the checked-in demo dataset for the selected domain.

    The selected domain is the sole source of truth. There is no
    domain-specific Python model and no previous-domain fallback.
    """
    domain_dir = DEMO_DATA_DIR / choice.lower()

    if not domain_dir.exists():
        raise ValueError(
            f"Demo domain '{choice}' is not available."
        )

    files = {}

    for path in sorted(
        domain_dir.iterdir()
    ):
        if (
            path.is_file()
            and path.suffix.lower() == ".csv"
        ):
            files[path.name] = pd.read_csv(
                path
            )

    if not files:
        raise ValueError(
            f"Demo domain '{choice}' contains no CSV files."
        )

    return files


# =============================================================================
# RESET CURRENT MODEL
# =============================================================================

def reset_current_model():
    """
    Clear only the current in-progress semantic model.

    This does NOT delete anything from Databricks or the published registry.
    Previously published domains remain available for Analytics.
    """

    st.session_state.model = None
    st.session_state.uploaded_files = {}
    st.session_state.llm_suggestion_count = 0
    st.session_state.stage = "upload"


# =============================================================================
# DATA ONBOARDING
# =============================================================================

with st.container(border=True):

    st.markdown("**Domain name**")

    # IMPORTANT:
    # Do not mutate st.session_state.domain_name while the text_input is
    # rendering. Streamlit reruns the script on every widget interaction,
    # and changing another widget's state during that rerun can make the
    # visible selection appear to jump/reset.
    #
    # The onboarding widgets have stable keys, and the selected values are
    # committed to session state only when the user clicks Analyze.

    source = st.radio(
        "Source",
        [
            "Upload files",
            "Try a sample domain",
        ],
        key="onboarding_source",
        label_visibility="collapsed",
        horizontal=True,
    )

    files = {}
    selected_domain = ""

    # -------------------------------------------------------------------------
    # SAMPLE DOMAIN
    # -------------------------------------------------------------------------

    if source == "Try a sample domain":

        demo_domains = available_demo_domains()
        if not demo_domains:
            st.error("No sample domains are available in this deployment.")
            st.stop()

        # Repair stale session state from older builds (including the old
        # hard-coded Healthcare value) before creating the selectbox.
        current_sample = st.session_state.get("onboarding_sample_domain")
        if current_sample not in demo_domains:
            st.session_state["onboarding_sample_domain"] = demo_domains[0]

        sample_choice = st.selectbox(
            "Sample domain",
            demo_domains,
            key="onboarding_sample_domain",
        )

        # The selectbox is the source of truth for sample mode.
        selected_domain = sample_choice

        files = load_sample_domain(
            sample_choice
        )

        st.caption(
            f"{len(files)} sample tables ready: "
            f"{', '.join(files.keys())}"
        )

        st.info(
            f"Sample domain selected: **{sample_choice}**"
        )

    # -------------------------------------------------------------------------
    # USER UPLOAD
    # -------------------------------------------------------------------------

    else:

        domain_input = st.text_input(
            "Domain name",
            value=st.session_state.get(
                "onboarding_upload_domain",
                "",
            ),
            key="onboarding_upload_domain",
            placeholder="e.g. Healthcare, Finance, Retail — any name",
            label_visibility="collapsed",
        )

        selected_domain = domain_input.strip()

        uploaded = st.file_uploader(
            "Upload tabular data",
            type=[
                "csv",
                "xlsx",
                "xls",
                "json",
                "parquet",
                "xml",
            ],
            accept_multiple_files=True,
            key="onboarding_uploaded_files",
        )

        if uploaded:
            try:
                files = prepare_files(
                    load_uploaded_files(uploaded)
                )
                st.caption(
                    f"{len(files)} file(s) loaded. "
                    "Supported: CSV, Excel, JSON, Parquet, XML."
                )
            except Exception as exc:
                st.error(
                    f"Couldn't load the selected files: {exc}"
                )

    st.markdown(
        "<br>",
        unsafe_allow_html=True,
    )

    can_analyze = bool(
        files
        and selected_domain
    )

    go = st.button(
        "Analyze My Data →",
        type="primary",
        disabled=not can_analyze,
        key="analyze_current_onboarding",
    )

    if (
        not selected_domain
        and files
    ):
        st.caption(
            "Enter a domain name above to continue."
        )


# =============================================================================
# START ANALYSIS
# =============================================================================

if go:

    # Commit the selected domain ONLY when Analyze is clicked.
    st.session_state.domain_name = selected_domain.strip()

    # CRITICAL:
    # Completely replace the current in-memory model with this run's data.
    # No previous Healthcare/Finance/Retail model can leak into the next run.
    st.session_state.model = None
    st.session_state.llm_suggestion_count = 0

    # Store only this run's files.
    st.session_state.uploaded_files = {
        name: dataframe.copy()
        for name, dataframe in files.items()
    }

    st.session_state.stage = "processing"

    navigate_to("AI Analysis")



