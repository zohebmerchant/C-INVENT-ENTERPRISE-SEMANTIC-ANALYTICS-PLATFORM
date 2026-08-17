"""C INVENT role-based access control for Streamlit Cloud.

Authentication is intentionally server-side: credentials live in Streamlit
Secrets and are never committed to the repository or exposed to the browser.
This is a small-team access gate. For enterprise SSO, replace authenticate()
with the organization's OIDC/Entra/Okta integration while keeping the same
role/page authorization contract.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any

import streamlit as st

ROLES = ("Admin", "Data Engineer", "Analyst", "Business User", "Viewer")

ROLE_PAGES = {
    "Admin": {
        "Home", "Data Onboarding", "Databricks Discovery", "AI Analysis",
        "Semantic Intelligence", "Business Model", "QA Validation",
        "Analytics", "Ask AI", "Genie Agent", "Security Center",
        "Connectors", "Audit & Policies",
    },
    "Data Engineer": {
        "Home", "Data Onboarding", "Databricks Discovery", "AI Analysis",
        "Semantic Intelligence", "Business Model", "QA Validation",
    },
    "Analyst": {"Home", "Analytics", "Ask AI"},
    "Business User": {"Home", "Analytics", "Genie Agent"},
    "Viewer": {"Home", "Analytics"},
}

ROLE_PUBLISH = {"Admin"}


def _secret(name: str, default: Any = None) -> Any:
    try:
        return st.secrets.get(name, default)
    except Exception:
        return default


def auth_enabled() -> bool:
    raw = _secret("CINVENT_AUTH_ENABLED", True)
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() not in {"0", "false", "no", "off"}


def _load_users() -> list[dict[str, str]]:
    """Load users from either CINVENT_USERS_JSON or CINVENT_USER_* tables."""
    users: list[dict[str, str]] = []

    raw_json = _secret("CINVENT_USERS_JSON")
    if raw_json:
        try:
            parsed = json.loads(str(raw_json))
            if isinstance(parsed, list):
                users.extend({str(k): str(v) for k, v in item.items()} for item in parsed if isinstance(item, dict))
        except Exception:
            pass

    # Preferred Streamlit Secrets structure for teams:
    # [CINVENT_USER_ADMIN]
    # email = "admin@company.com"
    # role = "Admin"
    # password_hash = "..."
    # salt = "..."
    try:
        for key in st.secrets.keys():
            key_text = str(key)
            if key_text == "CINVENT_USERS_JSON":
                continue
            # Accept both legacy/plural and preferred/singular secret section names.
            if not (key_text.startswith("CINVENT_USER_") or key_text.startswith("CINVENT_USERS_")):
                continue
            value = st.secrets[key]
            if hasattr(value, "get"):
                email = str(value.get("email", "")).strip().lower()
                name = str(value.get("name", "")).strip()
                role = str(value.get("role", "")).strip()
                password_hash = str(value.get("password_hash", "")).strip()
                salt = str(value.get("salt", "")).strip()
                if email and role and password_hash and salt:
                    users.append({
                        "email": email,
                        "name": name or email.split("@", 1)[0].replace(".", " ").replace("-", " ").title(),
                        "role": role,
                        "password_hash": password_hash,
                        "salt": salt,
                    })
    except Exception:
        pass

    # Deduplicate by email, with later configuration taking precedence.
    dedup: dict[str, dict[str, str]] = {}
    for user in users:
        email = user.get("email", "").strip().lower()
        if email:
            dedup[email] = user
    return list(dedup.values())


def password_hash(password: str, salt_hex: str) -> str:
    salt = bytes.fromhex(salt_hex)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    return digest.hex()


def authenticate(email: str, password: str) -> dict[str, str] | None:
    email = email.strip().lower()
    for user in _load_users():
        if user.get("email", "").lower() != email:
            continue
        role = user.get("role", "")
        if role not in ROLES:
            return None
        try:
            supplied = password_hash(password, user["salt"])
            if hmac.compare_digest(supplied, user["password_hash"]):
                return {"email": email, "name": user.get("name") or email.split("@", 1)[0].replace(".", " ").replace("-", " ").title(), "role": role}
        except Exception:
            return None
    return None


def is_authenticated() -> bool:
    return bool(st.session_state.get("cinvent_authenticated"))


def current_user() -> dict[str, str] | None:
    if not is_authenticated():
        return None
    return {
        "email": str(st.session_state.get("cinvent_email", "")),
        "role": str(st.session_state.get("cinvent_role", "")),
    }


def can_access(page: str, role: str | None = None) -> bool:
    role = role or str(st.session_state.get("cinvent_role", ""))
    return page in ROLE_PAGES.get(role, set())


def can_publish(role: str | None = None) -> bool:
    role = role or str(st.session_state.get("cinvent_role", ""))
    return role in ROLE_PUBLISH


def logout() -> None:
    for key in ("cinvent_authenticated", "cinvent_email", "cinvent_role"):
        st.session_state.pop(key, None)
    st.session_state["_invent_current_page"] = "Home"
    st.rerun()


def render_login() -> None:
    st.markdown("""
    <div style='max-width:520px;margin:7vh auto 0;background:#fff;border:1px solid #DCE5ED;border-radius:18px;padding:34px;box-shadow:0 18px 50px rgba(8,34,60,.08)'>
      <div style='display:flex;align-items:center;gap:12px;margin-bottom:20px'>
        <div style='width:42px;height:42px;border-radius:11px;background:linear-gradient(135deg,#0A8FA3,#0875D1);display:flex;align-items:center;justify-content:center;color:#fff;font-size:24px;font-weight:900'>C</div>
        <div><div style='font-size:22px;font-weight:800;color:#0B1F36'>C INVENT</div><div style='font-size:11px;color:#6C7E91'>Enterprise Semantic Analytics Platform</div></div>
      </div>
      <div style='font-size:14px;font-weight:800;color:#0B1F36;margin-bottom:4px'>Sign in</div>
      <div style='font-size:12px;color:#6C7E91;margin-bottom:18px'>Use your C INVENT account. Access is controlled by your assigned role.</div>
    </div>
    """, unsafe_allow_html=True)
    # The actual form is rendered immediately after the card header; CSS keeps it compact.
    with st.form("cinvent_login_form", clear_on_submit=False):
        email = st.text_input("Email", placeholder="name@company.com")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in", type="primary", use_container_width=True)
        if submitted:
            now = time.time()
            lock_until = float(st.session_state.get("cinvent_lock_until", 0))
            if now < lock_until:
                st.error("Too many failed attempts. Please try again in 60 seconds.")
                return
            user = authenticate(email, password)
            if user:
                st.session_state["cinvent_authenticated"] = True
                st.session_state["cinvent_email"] = user["email"]
                st.session_state["cinvent_role"] = user["role"]
                st.session_state["cinvent_login_failures"] = 0
                st.session_state["_invent_current_page"] = "Home"
                st.rerun()
            else:
                failures = int(st.session_state.get("cinvent_login_failures", 0)) + 1
                st.session_state["cinvent_login_failures"] = failures
                if failures >= 5:
                    st.session_state["cinvent_lock_until"] = now + 60
                    st.session_state["cinvent_login_failures"] = 0
                st.error("Invalid email or password.")


def require_login() -> bool:
    if not auth_enabled():
        return True
    if not is_authenticated():
        render_login()
        return False
    return True
