"""
Enterprise Semantic Analytics Platform — Security Fabric.

This module is what makes "no manual Databricks intervention per
upload" a true claim rather than an aspiration. Every grant and every
Genie registration issued when a new domain is published happens here,
via direct Databricks REST API calls — not a SQL editor, not a human
clicking through the workspace UI.

Authentication is via a workspace Personal Access Token (PAT), not
OAuth M2M with a separate service principal — see _pat_config() below
for why. Under this model, the identity running the app already owns
the dedicated catalog it created during the one-time bootstrap (see
databricks_bootstrap.py), so there is no separate "grant privileges to
a service principal" step this module needs to avoid crossing. The one
genuinely one-time, human-run step is creating that dedicated catalog
itself, done once via databricks_bootstrap.py before the platform is
used — not repeated per upload or per domain.

Everything AFTER that one-time bootstrap — creating new schemas/tables/
views for each newly-published domain, optionally granting a separate
reader identity, registering/updating the domain's Genie Agent —
is genuinely automatic, called inline during publish, with no human in
the loop.

Uses direct `requests` calls against Databricks' REST API rather than
speculative SDK method names, since the exact wrapped-method surface
for Genie space management was unconfirmed against the pinned SDK
version at build time (see README for the citation). Grants use the
confirmed, documented `w.grants.update()` SDK method directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import uuid
import re

import requests
import streamlit as st
from databricks.sdk import WorkspaceClient
from databricks.sdk.core import Config
from databricks.sdk.service.catalog import PermissionsChange, Privilege, SecurableType


@dataclass
class SecurityAction:
    action: str
    target: str
    principal: str
    status: str  # "success" | "failed" | "pending_approval"
    detail: str = ""


@dataclass
class SecurityReport:
    pii_findings: dict
    actions: list = field(default_factory=list)
    requires_approval: list = field(default_factory=list)


def is_configured() -> bool:
    required = ["DATABRICKS_HOST", "DATABRICKS_TOKEN", "DATABRICKS_WAREHOUSE_ID", "DATABRICKS_CATALOG"]
    return all(k in st.secrets for k in required)


def _pat_config() -> Config:
    """
    Personal Access Token auth, not OAuth M2M (client_id/client_secret).

    This is a deliberate choice, not a simplification of convenience:
    Databricks Free Edition has no access to the account console or
    account-level APIs, and OAuth M2M service-principal authentication
    depends on that account-level identity infrastructure -- confirmed
    directly against Databricks' own Free Edition limitations docs and
    community reports of OAuth M2M failing there. A workspace-level PAT
    has no such dependency: it's generated from a workspace settings
    page (Settings -> Developer -> Access Tokens), available even on
    Free Edition, and works identically across the SQL connector, the
    Workspace SDK client, and the Foundation Model API.

    The one honest tradeoff: a PAT authenticates as whatever identity
    generated it -- typically a human user, not an autonomous service
    principal. For this demo, that's a feature, not a compromise: the
    platform runs under one dedicated identity, scoped to grants that
    identity has given itself on one dedicated catalog -- a simpler,
    equally honest story for an external, Free Edition deployment.
    """
    return Config(host=st.secrets["DATABRICKS_HOST"], token=st.secrets["DATABRICKS_TOKEN"])


@st.cache_resource
def get_workspace_client() -> WorkspaceClient:
    return WorkspaceClient(config=_pat_config())


def grant_select_on_schema(schema_full_name: str, principal: str) -> SecurityAction:
    """Grants SELECT + USE SCHEMA on a newly-published schema to a
    reader principal — the automatic, per-domain replacement for the
    manual GRANT statements run by hand in earlier phases."""
    w = get_workspace_client()
    try:
        w.grants.update(
            securable_type=SecurableType.SCHEMA,
            full_name=schema_full_name,
            changes=[PermissionsChange(principal=principal, add=[Privilege.SELECT, Privilege.USE_SCHEMA])],
        )
        return SecurityAction(
            action="Grant SELECT + USE SCHEMA", target=schema_full_name, principal=principal,
            status="success", detail="Issued via Databricks Grants API — no manual SQL editor step.",
        )
    except Exception as e:
        return SecurityAction(action="Grant SELECT + USE SCHEMA", target=schema_full_name, principal=principal, status="failed", detail=str(e))


def grant_use_catalog(catalog_name: str, principal: str) -> SecurityAction:
    w = get_workspace_client()
    try:
        w.grants.update(
            securable_type=SecurableType.CATALOG,
            full_name=catalog_name,
            changes=[PermissionsChange(principal=principal, add=[Privilege.USE_CATALOG])],
        )
        return SecurityAction(
            action="Grant USE CATALOG", target=catalog_name, principal=principal,
            status="success", detail="Issued via Databricks Grants API.",
        )
    except Exception as e:
        return SecurityAction(action="Grant USE CATALOG", target=catalog_name, principal=principal, status="failed", detail=str(e))


def _auth_headers() -> dict:
    w = get_workspace_client()
    return w.config.authenticate()


def _default_serialized_genie_space(
    table_full_name: str,
    metric_view_full_name: str | None = None,
    title: str = "Enterprise Semantic Analytics",
) -> str:
    """
    Build a minimal valid serialized Genie Agent/Space configuration.

    Genie Spaces are now called Genie Agents in current Databricks docs,
    but the REST API remains under /api/2.0/genie/spaces.

    The configuration deliberately starts with the published semantic
    model as the trusted data asset. Additional tables can be included
    when required, but the metric view is preferred for business Q&A.
    """
    import json

    tables = [
        {
            "identifier": table_full_name,
            "description": [
                "Published by Enterprise Semantic Analytics Platform."
            ],
        }
    ]

    metric_views = []

    if metric_view_full_name:
        metric_views.append(
            {
                "identifier": metric_view_full_name,
                "description": [
                    "Governed semantic metric view generated by the platform."
                ],
            }
        )

    payload = {
        "version": 2,
        "config": {
            "sample_questions": [
                {
                    "id": "sem001",
                    "question": ["What are the key KPIs for this domain?"],
                },
                {
                    "id": "sem002",
                    "question": ["Show the main business trends."],
                },
                {
                    "id": "sem003",
                    "question": ["What are the top drivers of performance?"],
                },
            ]
        },
        "data_sources": {
            "tables": tables,
            "metric_views": metric_views,
        },
        "instructions": {
            "text_instructions": [
                {
                    "id": "sem-instruction-001",
                    "content": [
                        "Use the governed semantic model and metric view "
                        "as the primary source for business answers."
                    ],
                }
            ]
        },
    }

    return json.dumps(payload)




def _genie_secret_mapping() -> dict[str, str]:
    """
    Read optional per-domain Genie Agent mapping.

    Preferred:
        [GENIE_SPACES]
        Retail = "..."
        Healthcare = "..."
        Finance = "..."

    Backward compatible:
        GENIE_SPACE_ID = "..."

    The mapping is metadata/configuration, not domain-specific application
    logic.
    """
    try:
        raw = st.secrets.get("GENIE_SPACES", {})
        if hasattr(raw, "items"):
            return {
                str(k).strip().lower(): str(v).strip()
                for k, v in raw.items()
                if str(v).strip()
            }
    except Exception:
        pass
    return {}


def genie_space_id_from_secrets(
    domain_name: str | None = None,
) -> str | None:
    mapping = _genie_secret_mapping()

    if domain_name:
        mapped = mapping.get(
            str(domain_name).strip().lower()
        )
        if mapped:
            return mapped

    # Legacy/shared-agent fallback.
    try:
        value = str(
            st.secrets.get(
                "GENIE_SPACE_ID",
                "",
            )
        ).strip()
        return value or None
    except Exception:
        return None


def genie_is_configured(
    domain_name: str | None = None,
) -> bool:
    return bool(
        genie_space_id_from_secrets(domain_name)
        or _genie_auto_create_enabled()
    )


def _genie_auto_create_enabled() -> bool:
    try:
        value = st.secrets.get(
            "GENIE_AUTO_CREATE",
            True,
        )
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
    except Exception:
        return True


def _is_valid_genie_agent_id(
    value: str | None,
) -> bool:
    """Validate a Genie Agent/Space identifier using the API's UUID contract.

    Databricks documents the space_id path parameter as a UUID. Older INVENT
    builds incorrectly required exactly 32 lowercase hexadecimal characters,
    which rejected valid hyphenated UUIDs and produced misleading
    "invalid Agent ID" failures for newer IDs.
    """
    if not value:
        return False
    text = str(value).strip()
    try:
        uuid.UUID(text)
        return True
    except (ValueError, AttributeError, TypeError):
        try:
            uuid.UUID(hex=text)
            return True
        except (ValueError, AttributeError, TypeError):
            return False


def _genie_headers() -> dict[str, str]:
    return {
        **_auth_headers(),
        "Content-Type": "application/json",
    }


def _genie_url(space_id: str) -> str:
    host = st.secrets["DATABRICKS_HOST"].rstrip("/")
    return (
        f"{host}/api/2.0/genie/spaces/"
        f"{space_id}"
    )


def genie_ui_url(space_id: str) -> str:
    host = st.secrets["DATABRICKS_HOST"].rstrip("/")
    return (
        f"{host}/genie/rooms/"
        f"{space_id}"
    )


def _new_genie_item_id() -> str:
    return uuid.uuid4().hex


def _merge_genie_serialized_space(
    serialized_space: str,
    metric_view_full_name: str,
    domain_name: str,
    measures: list[str] | None = None,
    dimensions: list[str] | None = None,
    sample_questions: list[str] | None = None,
) -> str:
    """
    Safely merge INVENT metadata into an existing serialized Genie Agent.

    Databricks UpdateSpace is a full serialized-space replacement, so the
    existing configuration is preserved and only INVENT-owned additions
    are merged.
    """
    config = json.loads(serialized_space)

    if not isinstance(config, dict):
        raise RuntimeError(
            "Genie serialized_space is not a JSON object."
        )

    config.setdefault("version", 2)
    config.setdefault("config", {})
    config.setdefault("data_sources", {})
    config.setdefault("instructions", {})

    data_sources = config["data_sources"]
    if not isinstance(data_sources, dict):
        data_sources = {}
        config["data_sources"] = data_sources

    metric_views = data_sources.setdefault(
        "metric_views",
        [],
    )

    if not isinstance(metric_views, list):
        metric_views = []
        data_sources["metric_views"] = metric_views

    # Keep exactly one INVENT canonical Metric View for each domain Agent.
    # Older releases registered one MV per fact; remove those legacy sources
    # from the domain Agent while preserving unrelated user-managed sources.
    metric_view_prefix = ".".join(metric_view_full_name.split(".")[:-1]) + "."
    cleaned_metric_views = []
    for item in metric_views:
        identifier = str(item.get("identifier") or "") if isinstance(item, dict) else ""
        if identifier == metric_view_full_name:
            continue
        if identifier.startswith(metric_view_prefix) and identifier.rsplit(".", 1)[-1].startswith("mv_"):
            continue
        cleaned_metric_views.append(item)

    cleaned_metric_views.append(
        {
            "identifier": metric_view_full_name,
            "description": [
                f"INVENT canonical governed Metric View for the {domain_name} domain.",
                "All detected fact tables are published as Delta tables; this Agent uses one canonical domain Metric View.",
            ],
        }
    )
    data_sources["metric_views"] = cleaned_metric_views
    metric_views = cleaned_metric_views

    # Sample questions
    questions = config["config"].setdefault(
        "sample_questions",
        [],
    )
    if not isinstance(questions, list):
        questions = []
        config["config"]["sample_questions"] = questions

    generated_questions = list(
        sample_questions or []
    )

    if measures:
        generated_questions.extend([
            f"What are the key KPIs for {domain_name}?",
            f"Show {measures[0]} by the main business dimensions.",
        ])

    if dimensions:
        generated_questions.append(
            f"Show the trend of {measures[0] if measures else 'the main KPI'} "
            f"by {dimensions[0]}."
        )

    existing_questions = {
        q
        for item in questions
        if isinstance(item, dict)
        for q in item.get("question", [])
        if isinstance(q, str)
    }

    for question in generated_questions[:8]:
        if question in existing_questions:
            continue

        questions.append(
            {
                "id": _new_genie_item_id(),
                "question": [question],
            }
        )
        existing_questions.add(question)

    # Governance instructions
    text_instructions = config["instructions"].setdefault(
        "text_instructions",
        [],
    )
    if not isinstance(text_instructions, list):
        text_instructions = []
        config["instructions"]["text_instructions"] = (
            text_instructions
        )

    instruction = (
        "INVENT governed semantic model: use the published Metric View "
        f"{metric_view_full_name} as the primary analytical source for "
        f"the {domain_name} domain. Prefer its defined measures and "
        "dimensions. Do not invent alternative metric definitions. "
        "For Metric View measures, use MEASURE() when generating SQL. "
        "Do not bypass the governed semantic layer with raw-table joins "
        "when the requested answer is represented by the Metric View."
    )

    existing_instructions = {
        content
        for item in text_instructions
        if isinstance(item, dict)
        for content in item.get("content", [])
        if isinstance(content, str)
    }

    if instruction not in existing_instructions:
        text_instructions.append(
            {
                "id": _new_genie_item_id(),
                "content": [instruction],
            }
        )

    return json.dumps(
        config,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _find_existing_genie_agent(domain_name: str) -> str | None:
    """Find an existing INVENT Genie Agent by its deterministic title.

    This is the recovery path for stale/invalid GENIE_SPACE_ID values. The
    list endpoint is read-only and lets a deployment recover without forcing
    the user to delete or recreate an Agent manually.
    """
    host = st.secrets["DATABRICKS_HOST"].rstrip("/")
    try:
        resp = requests.get(
            f"{host}/api/2.0/genie/spaces",
            params={"page_size": 100},
            headers=_genie_headers(),
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        expected = f"INVENT — {domain_name}".strip().casefold()
        for item in data.get("spaces", []) or []:
            title = str(item.get("title") or "").strip().casefold()
            candidate = item.get("space_id") or item.get("id")
            if title == expected and _is_valid_genie_agent_id(candidate):
                return str(candidate)
    except Exception:
        return None
    return None


def _update_existing_genie_agent(
    space_id: str,
    metric_view_full_name: str,
    domain_name: str,
    measures: list[str] | None,
    dimensions: list[str] | None,
    sample_questions: list[str] | None,
) -> SecurityAction:
    """
    Update an existing Genie Agent using Databricks' current
    serialized_space UpdateSpace API.
    """
    try:
        get_resp = requests.get(
            _genie_url(space_id),
            params={
                "include_serialized_space": "true",
            },
            headers=_genie_headers(),
            timeout=30,
        )

        get_resp.raise_for_status()
        current = get_resp.json()

        serialized = current.get(
            "serialized_space"
        )

        if not serialized:
            raise RuntimeError(
                "Databricks returned no serialized_space. "
                "The publishing identity needs permission to edit "
                "the Genie Agent."
            )

        updated_serialized = (
            _merge_genie_serialized_space(
                serialized,
                metric_view_full_name,
                domain_name,
                measures,
                dimensions,
                sample_questions,
            )
        )

        payload = {
            "serialized_space": updated_serialized,
        }

        # Do not send a stale export etag. Genie UpdateSpace can return HTTP
        # 409 when the Agent was edited in Catalog/Genie after the GET. The
        # API explicitly supports omitting etag to skip conflict detection.
        resp = requests.patch(
            _genie_url(space_id),
            headers=_genie_headers(),
            json=payload,
            timeout=30,
        )

        if resp.status_code == 409:
            # One safe retry without conflict metadata. The update is still
            # scoped to the single canonical INVENT Metric View.
            payload.pop("etag", None)
            resp = requests.patch(
                _genie_url(space_id),
                headers=_genie_headers(),
                json=payload,
                timeout=30,
            )
        resp.raise_for_status()

        return SecurityAction(
            action="Genie Agent",
            target=metric_view_full_name,
            principal=f"genie-space:{space_id}",
            status="success",
            detail=(
                f"Metric View registered in Genie Agent "
                f"{space_id} for domain '{domain_name}'."
            ),
        )

    except requests.HTTPError as exc:
        status = (
            exc.response.status_code
            if exc.response is not None
            else "unknown"
        )

        body = ""
        try:
            body = exc.response.text[:500]
        except Exception:
            pass

        return SecurityAction(
            action="Genie Agent",
            target=metric_view_full_name,
            principal=f"genie-space:{space_id}",
            status="failed",
            detail=(
                f"Genie UpdateSpace failed HTTP {status}. "
                f"{body}"
            ).strip(),
        )

    except Exception as exc:
        return SecurityAction(
            action="Genie Agent",
            target=metric_view_full_name,
            principal=f"genie-space:{space_id}",
            status="failed",
            detail=str(exc),
        )


def _create_genie_agent(
    metric_view_full_name: str,
    domain_name: str,
    measures: list[str] | None,
    dimensions: list[str] | None,
    sample_questions: list[str] | None,
) -> tuple[str | None, SecurityAction]:
    """
    Create a domain-specific Genie Agent when no existing ID is mapped.

    Creation uses the documented CreateSpace serialized payload. If the
    workspace/plan does not permit Genie management, semantic publishing
    remains successful and the failure is reported as an explicit optional
    consumption action.
    """
    host = st.secrets["DATABRICKS_HOST"].rstrip("/")

    base_config = {
        "version": 2,
        "config": {
            "sample_questions": [],
        },
        "data_sources": {
            "tables": [],
            "metric_views": [],
        },
        "instructions": {
            "text_instructions": [],
        },
    }

    serialized = _merge_genie_serialized_space(
        json.dumps(base_config),
        metric_view_full_name,
        domain_name,
        measures,
        dimensions,
        sample_questions,
    )

    payload = {
        "title": f"INVENT — {domain_name}",
        "description": (
            f"INVENT governed semantic analytics for "
            f"the {domain_name} domain."
        ),
        "warehouse_id": st.secrets[
            "DATABRICKS_WAREHOUSE_ID"
        ],
        "serialized_space": serialized,
    }

    try:
        resp = requests.post(
            f"{host}/api/2.0/genie/spaces",
            headers=_genie_headers(),
            json=payload,
            timeout=45,
        )
        resp.raise_for_status()

        data = resp.json()
        space_id = (
            data.get("space_id")
            or data.get("id")
        )

        if not space_id:
            raise RuntimeError(
                "CreateSpace succeeded but no Genie Agent ID was returned."
            )

        return (
            str(space_id),
            SecurityAction(
                action="Genie Agent",
                target=metric_view_full_name,
                principal=f"genie-space:{space_id}",
                status="success",
                detail=(
                    f"Created and configured Genie Agent "
                    f"{space_id} for domain '{domain_name}'."
                ),
            ),
        )

    except requests.HTTPError as exc:
        status = (
            exc.response.status_code
            if exc.response is not None
            else "unknown"
        )
        body = ""
        try:
            body = exc.response.text[:500]
        except Exception:
            pass

        return (
            None,
            SecurityAction(
                action="Genie Agent",
                target=metric_view_full_name,
                principal="auto-create",
                status="failed",
                detail=(
                    f"Genie CreateSpace failed HTTP {status}. "
                    f"{body}"
                ).strip(),
            ),
        )

    except Exception as exc:
        return (
            None,
            SecurityAction(
                action="Genie Agent",
                target=metric_view_full_name,
                principal="auto-create",
                status="failed",
                detail=str(exc),
            ),
        )


def record_genie_not_configured(
    domain_name: str,
) -> SecurityAction:
    return SecurityAction(
        action="Genie Agent",
        target=domain_name,
        principal="not-configured",
        status="skipped",
        detail=(
            "No domain Genie Agent is configured and automatic creation "
            "is disabled."
        ),
    )


def register_table_with_genie_space(
    space_id: str | None,
    table_full_name: str,
    metric_view_full_name: str | None = None,
    domain_name: str | None = None,
    measures: list[str] | None = None,
    dimensions: list[str] | None = None,
    sample_questions: list[str] | None = None,
) -> tuple[str | None, SecurityAction]:
    """
    Ensure the domain's published Metric View is configured in Genie.

    Returns the resolved Genie Agent ID and an audit action.
    """
    metric_view = (
        metric_view_full_name
        or table_full_name
    )

    if not metric_view:
        return (
            None,
            SecurityAction(
                action="Genie Agent",
                target=domain_name or "domain",
                principal="not-configured",
                status="failed",
                detail="No Metric View was supplied.",
            ),
        )

    # First recover the deterministic domain agent. This prevents every
    # publish from creating another INVENT — <domain> Agent when an older
    # valid domain agent already exists.
    existing_domain_space = _find_existing_genie_agent(domain_name or "domain")
    if existing_domain_space:
        space_id = existing_domain_space

    if space_id:
        if not _is_valid_genie_agent_id(space_id):
            recovered = _find_existing_genie_agent(
                domain_name or "domain"
            )
            if recovered:
                space_id = recovered
            elif _genie_auto_create_enabled():
                created_id, create_action = _create_genie_agent(
                    metric_view,
                    domain_name or "domain",
                    measures,
                    dimensions,
                    sample_questions,
                )
                if created_id:
                    return created_id, create_action
                create_action.detail = (
                    "Configured Genie Agent ID was invalid/stale. "
                    "Automatic recovery could not create a replacement. "
                    + create_action.detail
                )
                return None, create_action
            else:
                return (
                    None,
                    SecurityAction(
                        action="Genie Agent",
                        target=metric_view,
                        principal=f"genie-space:{space_id}",
                        status="failed",
                        detail=(
                            "Configured Genie Agent ID is not a valid UUID. "
                            "GENIE_AUTO_CREATE is disabled and no matching "
                            "INVENT Agent could be recovered."
                        ),
                    ),
                )

        action = _update_existing_genie_agent(
            space_id,
            metric_view,
            domain_name or "domain",
            measures,
            dimensions,
            sample_questions,
        )
        if action.status == "success":
            return space_id, action

        # Recover a deleted/stale UUID without hiding real permission errors.
        if _genie_auto_create_enabled() and (
            "HTTP 404" in action.detail
            or "NOT_FOUND" in action.detail
            or "FEATURE_DISABLED" in action.detail
        ):
            recovered = _find_existing_genie_agent(
                domain_name or "domain"
            )
            if recovered and recovered != space_id:
                retry = _update_existing_genie_agent(
                    recovered,
                    metric_view,
                    domain_name or "domain",
                    measures,
                    dimensions,
                    sample_questions,
                )
                if retry.status == "success":
                    retry.detail = (
                        "Recovered stale Genie Agent mapping automatically. "
                        + retry.detail
                    )
                    return recovered, retry

            created_id, create_action = _create_genie_agent(
                metric_view,
                domain_name or "domain",
                measures,
                dimensions,
                sample_questions,
            )
            if created_id:
                create_action.detail = (
                    "Recreated the stale/missing Genie Agent automatically. "
                    + create_action.detail
                )
                return created_id, create_action

        return None, action

    if _genie_auto_create_enabled():
        return _create_genie_agent(
            metric_view,
            domain_name or "domain",
            measures,
            dimensions,
            sample_questions,
        )

    return (
        None,
        SecurityAction(
            action="Genie Agent",
            target=metric_view,
            principal="not-configured",
            status="skipped",
            detail=(
                "No Genie Agent is mapped to this domain and "
                "GENIE_AUTO_CREATE is disabled."
            ),
        ),
    )


def build_security_report(pii_findings: dict) -> SecurityReport:
    """
    The propose -> approve gate. PII/PHI masking and production publish
    are AI PROPOSALS shown to a human, never auto-applied — a
    deliberate design choice, not a limitation being apologized for.
    """
    report = SecurityReport(pii_findings=pii_findings)
    for table, columns in pii_findings.items():
        report.requires_approval.append(
            f"{table}: {', '.join(columns)} — flagged as PII/PHI, recommend masking before wider access"
        )
    return report
