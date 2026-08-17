"""
Enterprise Semantic Analytics Platform — core AI engine.

This module implements the full analysis pipeline: Data Intelligence
(ingest -> profile -> quality -> security) and Semantic Intelligence
(entities -> relationships -> facts/dimensions -> measures -> metrics ->
glossary). Analytics Intelligence (dashboards, KPIs, Ask AI) lives in
analytics_engine.py and reads only the SemanticModel this module
produces — it never contains domain-specific logic itself.

Every step below is real, explainable logic — heuristic and statistical,
not a simulated animation. Steps that benefit from an LLM (fuzzy
relationship matching, richer glossary drafting) call out to Databricks
Foundation Model APIs in ai_engine.py and are clearly labeled as
AI-assisted suggestions requiring human review, never auto-applied.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import pandas as pd

PII_COLUMN_PATTERNS = {
    "name": ["full_name", "first_name", "last_name", "patient_name", "customer_name", "employee_name", "doctor_name", "physician_name"],
    "contact": ["email", "phone", "mobile", "address", "zip", "postal"],
    "identifier": ["ssn", "social_security", "passport", "national_id", "tax_id", "npi"],
    "financial": ["account_number", "card_number", "iban", "routing_number", "salary", "compensation"],
    "health": ["diagnosis", "medication", "condition", "blood_pressure", "heart_rate", "medical_record", "mrn"],
    "dob": ["date_of_birth", "dob", "birth_date"],
}
# Note: bare "name" is deliberately excluded from the "name" category —
# it over-matched reference/lookup columns like site_name or
# product_name, which are not personal data, producing false PII
# positives. Only specific person-identifying name patterns are flagged.


@dataclass
class ColumnProfile:
    name: str
    dtype: str
    null_pct: float
    distinct_count: int
    row_count: int
    uniqueness_ratio: float
    sample_values: list
    pii_category: str | None = None


@dataclass
class TableProfile:
    name: str
    row_count: int
    columns: list[ColumnProfile]
    df: pd.DataFrame = field(repr=False)
    duplicate_row_count: int = 0
    quality_warnings: list[str] = field(default_factory=list)


@dataclass
class RelationshipCandidate:
    from_table: str
    from_column: str
    to_table: str
    to_column: str
    confidence: float
    reason: str
    is_ai_suggested: bool = False
    is_many_to_many: bool = False


@dataclass
class BusinessMetric:
    name: str
    expression: str
    table: str
    description: str


@dataclass
class GlossaryEntry:
    term: str
    definition: str
    source_column: str


@dataclass
class SemanticModel:
    domain_name: str
    tables: dict[str, TableProfile]
    relationships: list[RelationshipCandidate]
    facts: list[str]
    dimensions: list[str]
    metrics: list[BusinessMetric] = field(default_factory=list)
    glossary: list[GlossaryEntry] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    pii_findings: dict[str, list[str]] = field(default_factory=dict)
    ai_suggestions: list[RelationshipCandidate] = field(default_factory=list)


def scan_metadata(files: dict[str, pd.DataFrame]) -> dict[str, TableProfile]:
    profiles = {}
    for name, df in files.items():
        row_count = len(df)
        dup_count = int(df.duplicated().sum()) if row_count else 0
        columns = []
        for col in df.columns:
            series = df[col]
            distinct = series.nunique(dropna=True)
            null_pct = series.isna().mean() * 100 if row_count else 0.0
            uniqueness = (distinct / row_count) if row_count else 0.0
            sample = series.dropna().unique()[:5].tolist()
            columns.append(ColumnProfile(
                name=col, dtype=str(series.dtype), null_pct=round(null_pct, 1),
                distinct_count=int(distinct), row_count=row_count,
                uniqueness_ratio=round(uniqueness, 4), sample_values=sample,
            ))
        profiles[name] = TableProfile(name=name, row_count=row_count, columns=columns, df=df, duplicate_row_count=dup_count)
    return profiles


def detect_data_quality_issues(profiles: dict[str, TableProfile]) -> None:
    for profile in profiles.values():
        if profile.duplicate_row_count > 0:
            pct = (profile.duplicate_row_count / profile.row_count * 100) if profile.row_count else 0
            profile.quality_warnings.append(
                f"{profile.duplicate_row_count} duplicate row(s) detected ({pct:.1f}% of table)"
            )
        for col in profile.columns:
            if col.null_pct > 30:
                profile.quality_warnings.append(f"Column '{col.name}' is {col.null_pct:.0f}% null")
            if col.distinct_count == 1 and profile.row_count > 1:
                profile.quality_warnings.append(f"Column '{col.name}' has only one distinct value across {profile.row_count} rows")


def classify_pii(profiles: dict[str, TableProfile]) -> dict[str, list[str]]:
    findings: dict[str, list[str]] = {}
    for table_name, profile in profiles.items():
        flagged = []
        for col in profile.columns:
            col_lower = col.name.lower()
            for category, patterns in PII_COLUMN_PATTERNS.items():
                if any(p in col_lower for p in patterns):
                    col.pii_category = category
                    flagged.append(col.name)
                    break
        if flagged:
            findings[table_name] = flagged
    return findings


def _normalize_col_name(name: str) -> str:
    n = re.sub(r'[^a-z0-9]', '', name.lower())
    n = re.sub(r'^(fk|pk)', '', n)
    return n


def _normalize_value_for_comparison(v) -> str:
    """
    Normalizes a value to a comparable string form, collapsing the
    float/int representation mismatch that occurs when pandas upcasts
    an otherwise-integer column to float because it contains a null
    (e.g. a nullable foreign key like manager_id becomes 33.0 instead
    of 33). Without this, comparing "33.0" against "33" as raw strings
    finds zero overlap even though they're the same value -- a real
    bug that silently broke relationship detection (both cross-table
    and self-referencing) any time one side of a real foreign key had
    a null and the other didn't. Caught by testing a self-referencing
    manager_id column, but the fix applies universally since this
    function is used by every relationship-detection comparison.
    """
    s = str(v)
    if s.endswith(".0"):
        try:
            float(s)
            return s[:-2]
        except ValueError:
            pass
    return s


def _value_overlap_ratio(series_a: pd.Series, series_b: pd.Series, sample_size: int = 500) -> float:
    a_vals = {_normalize_value_for_comparison(v) for v in series_a.dropna().unique()[:sample_size]}
    if not a_vals:
        return 0.0
    b_vals = {_normalize_value_for_comparison(v) for v in series_b.dropna().unique()[:sample_size * 4]}
    if not b_vals:
        return 0.0
    return len(a_vals & b_vals) / len(a_vals)


def _find_own_primary_key_column(profile: TableProfile) -> ColumnProfile | None:
    """Best-guess at a table's own primary key: the column with the
    highest uniqueness ratio among its id-token-named columns. Used by
    self-join detection below -- a heuristic, not a guarantee, same
    spirit as the rest of this engine's detection logic."""
    id_cols = [c for c in profile.columns if _looks_like_id_column(c.name, c.dtype)]
    if not id_cols:
        return None
    return max(id_cols, key=lambda c: c.uniqueness_ratio)


def detect_self_referencing_relationships(profiles: dict[str, TableProfile]) -> list[RelationshipCandidate]:
    """
    Detects hierarchical self-joins WITHIN a single table -- e.g.
    manager_id referencing employee_id in the same Employees table
    (an org chart), or parent_category_id referencing category_id (a
    category tree), or parent_part_id referencing part_id (a bill of
    materials).

    This is a genuinely different detection problem than
    detect_relationships() above, which only ever compares columns
    ACROSS two different tables and therefore structurally cannot find
    a relationship where both sides live in the same table -- confirmed
    empirically: a table with a manager_id column produced zero
    relationships until this function was added.

    The hard part, found through testing, is telling a genuine
    hierarchy column apart from an ordinary foreign key to a DIFFERENT
    table that just happens to have overlapping id values by
    coincidence of small sequential ranges (e.g. a Claims table with
    both claim_id 1-150 and an unrelated claimant_customer_id 1-200).
    Name-root matching against the CURRENT table's own name doesn't
    work either: "manager_id" and "Employees" share no name root at
    all, even though that's the canonical example this feature exists
    for.

    The actual distinguishing signal: a genuine self-reference does NOT
    match the name of any OTHER real table in this same upload. A false
    positive like claimant_customer_id clearly references "customer" --
    and if a Customers table genuinely exists in this upload, that's
    real evidence this is an ordinary cross-table FK (missed by
    detect_relationships() only because the column is misleadingly
    named), not a hierarchy. So: exclude any id-token column whose name
    matches another table's name/singular form, then check remaining
    candidates for value overlap against the table's own primary key.
    """
    candidates: list[RelationshipCandidate] = []

    other_table_roots = {
        re.sub(r'\.(csv|xlsx?)$', '', name, flags=re.IGNORECASE).lower().rstrip("s")
        for name in profiles.keys()
    }

    for table_name, profile in profiles.items():
        pk_col = _find_own_primary_key_column(profile)
        if pk_col is None or pk_col.uniqueness_ratio < 0.95:
            continue  # no confident primary key to self-join against

        this_table_root = re.sub(r'\.(csv|xlsx?)$', '', table_name, flags=re.IGNORECASE).lower().rstrip("s")

        for c in profile.columns:
            if c.name == pk_col.name:
                continue
            if not _looks_like_id_column(c.name, c.dtype):
                continue

            candidate_tokens = set(re.split(r'[_\s\-]+', c.name.lower()))
            references_another_real_table = any(
                root != this_table_root and (root in candidate_tokens or any(t == root for t in candidate_tokens))
                for root in other_table_roots
            )
            if references_another_real_table:
                # This looks like an ordinary foreign key to a table
                # that genuinely exists in this upload, not a
                # self-referencing hierarchy -- e.g.
                # claimant_customer_id when a Customers table is
                # present. Leave it for detect_relationships() to
                # (attempt to) match cross-table; don't treat it as a
                # self-join just because its values happen to overlap
                # this table's own primary key by coincidence.
                continue

            overlap = _value_overlap_ratio(profile.df[c.name], profile.df[pk_col.name])
            if overlap < 0.5:
                continue

            non_null_pct = 100 - c.null_pct
            confidence = round(min(1.0, 0.4 * overlap + 0.3 + (0.2 if non_null_pct < 100 else 0.1)), 2)

            candidates.append(RelationshipCandidate(
                from_table=table_name, from_column=c.name,
                to_table=table_name, to_column=pk_col.name,
                confidence=confidence,
                reason=(
                    f"Self-referencing candidate within {table_name}: {c.name} looks like an id column "
                    f"whose values ({overlap*100:.0f}% overlap) exist within {pk_col.name}, this table's "
                    f"own apparent primary key — suggests a hierarchy (e.g. manager/employee, "
                    f"parent/child category, or bill-of-materials)"
                ),
            ))

    return candidates



def _relationship_key(
    from_table: str,
    from_column: str,
    to_table: str,
    to_column: str,
) -> tuple:
    """
    Canonical unordered key for a relationship.

    This prevents:
        A.id -> B.id
    and
        B.id -> A.id

    from becoming two semantic relationships.
    """
    left = (from_table, from_column)
    right = (to_table, to_column)
    return tuple(sorted((left, right)))


def _orient_relationship(
    table_a: str,
    col_a: ColumnProfile,
    table_b: str,
    col_b: ColumnProfile,
    overlap_a_in_b: float,
    overlap_b_in_a: float,
) -> tuple[str, str, str, str, float]:
    """
    Return the canonical child/FK -> parent/PK direction.

    Direction is based on:
      1. Which side is more unique (PK-like).
      2. Which side's values are contained in the other side.
      3. Table/column identity naming as a tie-breaker.

    The result is independent of upload/table iteration order.
    """

    # A clear uniqueness difference is the strongest signal.
    if col_a.uniqueness_ratio > col_b.uniqueness_ratio + 0.05:
        return (
            table_b,
            col_b.name,
            table_a,
            col_a.name,
            overlap_b_in_a,
        )

    if col_b.uniqueness_ratio > col_a.uniqueness_ratio + 0.05:
        return (
            table_a,
            col_a.name,
            table_b,
            col_b.name,
            overlap_a_in_b,
        )

    # When uniqueness is close, the direction with stronger containment
    # is the more likely FK -> PK direction.
    if overlap_a_in_b > overlap_b_in_a + 0.05:
        return (
            table_a,
            col_a.name,
            table_b,
            col_b.name,
            overlap_a_in_b,
        )

    if overlap_b_in_a > overlap_a_in_b + 0.05:
        return (
            table_b,
            col_b.name,
            table_a,
            col_a.name,
            overlap_b_in_a,
        )

    # Final deterministic tie-breaker: preserve stable lexical order.
    # This is only a fallback; equal uniqueness/containment is inherently
    # ambiguous and should not be presented as a strong relationship.
    if (table_a, col_a.name) <= (table_b, col_b.name):
        return (
            table_a,
            col_a.name,
            table_b,
            col_b.name,
            overlap_a_in_b,
        )

    return (
        table_b,
        col_b.name,
        table_a,
        col_a.name,
        overlap_b_in_a,
    )



def _find_pk_hubs(
    profiles: dict[str, TableProfile],
    min_uniqueness: float = 0.95,
) -> dict[str, list[tuple[str, str]]]:
    """
    Return identifier columns that behave like primary-key hubs.

    A hub is a column that is highly unique in its own table. This is
    deliberately domain-neutral: machine_id, customer_id, account_id,
    patient_id, etc. are all treated the same way.
    """
    hubs: dict[str, list[tuple[str, str]]] = {}
    for table_name, profile in profiles.items():
        for col in profile.columns:
            if (
                col.uniqueness_ratio >= min_uniqueness
                and _looks_like_id_column(col.name, col.dtype)
            ):
                hubs.setdefault(
                    _normalize_col_name(col.name),
                    [],
                ).append(
                    (table_name, col.name)
                )
    return hubs


def _is_shared_nonunique_key(
    profiles: dict[str, TableProfile],
    table_a: str,
    col_a: str,
    table_b: str,
    col_b: str,
    hubs: dict[str, list[tuple[str, str]]],
) -> bool:
    """
    Reject a false direct fact-to-fact / dimension-to-dimension edge when
    both columns are non-unique but a third table contains the same key as
    a unique primary-key hub.

    Example:
        production_runs.machine_id
        maintenance.machine_id

    Both are non-unique. machines.machine_id is unique, so the correct
    model is two FK->PK edges through Machines, not a many-to-many edge
    between Production Runs and Maintenance.
    """
    if _normalize_col_name(col_a) != _normalize_col_name(col_b):
        return False

    profile_a = profiles[table_a]
    profile_b = profiles[table_b]

    a = next(c for c in profile_a.columns if c.name == col_a)
    b = next(c for c in profile_b.columns if c.name == col_b)

    if (
        a.uniqueness_ratio >= 0.95
        or b.uniqueness_ratio >= 0.95
    ):
        return False

    key = _normalize_col_name(col_a)

    for hub_table, hub_col in hubs.get(key, []):
        if hub_table in {table_a, table_b}:
            continue

        return True

    return False


def _candidate_confidence(
    fk_to_pk_overlap: float,
    fk_uniqueness: float,
    pk_uniqueness: float,
) -> float:
    """
    Confidence for a canonical FK->PK relationship.

    Full parent-key coverage plus a genuinely unique parent key reaches
    100%. Partial coverage remains lower and explainable.
    """
    parent_signal = min(
        1.0,
        max(0.0, pk_uniqueness),
    )

    containment_signal = min(
        1.0,
        max(0.0, fk_to_pk_overlap),
    )

    cardinality_signal = 1.0 - min(
        1.0,
        max(0.0, fk_uniqueness),
    )

    score = (
        0.55 * containment_signal
        + 0.30 * parent_signal
        + 0.15 * cardinality_signal
    )

    return round(
        min(1.0, max(0.0, score)),
        2,
    )



def _is_table_own_primary_key(
    profile: TableProfile,
    column_name: str,
) -> bool:
    """
    Prefer the table's apparent own primary key over an alternate unique
    foreign key. This prevents false edges such as:

        booking_services.booking_id -> payments.booking_id

    when payments.booking_id is unique but payments.payment_id is the
    table's own primary key and both booking_services and payments really
    reference bookings.booking_id.
    """
    pk = _find_own_primary_key_column(profile)
    return bool(
        pk
        and pk.name == column_name
        and pk.uniqueness_ratio >= 0.95
    )


def detect_relationships(
    profiles: dict[str, TableProfile],
) -> list[RelationshipCandidate]:
    """
    Generic semantic relationship inference.

    Rules:
      * Only matching identifier-like columns are considered.
      * A highly unique side is preferred as the PK.
      * Full FK coverage of a unique PK is high-confidence.
      * Two non-unique columns are NOT automatically many-to-many.
        If a third table contains a unique hub for that key, the pair is
        treated as two relationships through the hub.
      * Reverse duplicates are canonicalized.
      * Fact-to-fact relationships are allowed only when one side is
        genuinely a parent/event key (for example defects -> production_runs).
    """
    candidates: list[RelationshipCandidate] = []
    table_names = list(profiles.keys())
    pk_hubs = _find_pk_hubs(profiles)

    for i, t1 in enumerate(table_names):
        for t2 in table_names[i + 1:]:
            p1, p2 = profiles[t1], profiles[t2]

            for c1 in p1.columns:
                for c2 in p2.columns:

                    if _normalize_col_name(c1.name) != _normalize_col_name(c2.name):
                        continue

                    normalized_name = _normalize_col_name(c1.name)

                    if normalized_name in (
                        "",
                        "name",
                        "date",
                        "description",
                    ):
                        continue

                    if not (
                        _looks_like_id_column(c1.name, c1.dtype)
                        or _looks_like_id_column(c2.name, c2.dtype)
                    ):
                        continue

                    overlap_1_in_2 = _value_overlap_ratio(
                        p1.df[c1.name],
                        p2.df[c2.name],
                    )
                    overlap_2_in_1 = _value_overlap_ratio(
                        p2.df[c2.name],
                        p1.df[c1.name],
                    )

                    if max(
                        overlap_1_in_2,
                        overlap_2_in_1,
                    ) < 0.50:
                        continue

                    # Shared-key detection prevents false M:N edges.
                    if _is_shared_nonunique_key(
                        profiles,
                        t1,
                        c1.name,
                        t2,
                        c2.name,
                        pk_hubs,
                    ):
                        continue

                    # Prefer the side that is the table's own PK.
                    # This correctly handles 1:1/unique-FK structures such
                    # as payments.booking_id -> bookings.booking_id.
                    t1_is_own_pk = _is_table_own_primary_key(
                        p1,
                        c1.name,
                    )
                    t2_is_own_pk = _is_table_own_primary_key(
                        p2,
                        c2.name,
                    )

                    if t1_is_own_pk and not t2_is_own_pk:
                        (
                            fk_table,
                            fk_col,
                            pk_table,
                            pk_col,
                            fk_to_pk_overlap,
                        ) = (
                            t2,
                            c2.name,
                            t1,
                            c1.name,
                            overlap_2_in_1,
                        )
                    elif t2_is_own_pk and not t1_is_own_pk:
                        (
                            fk_table,
                            fk_col,
                            pk_table,
                            pk_col,
                            fk_to_pk_overlap,
                        ) = (
                            t1,
                            c1.name,
                            t2,
                            c2.name,
                            overlap_1_in_2,
                        )
                    else:
                        (
                            fk_table,
                            fk_col,
                            pk_table,
                            pk_col,
                            fk_to_pk_overlap,
                        ) = _orient_relationship(
                            t1,
                            c1,
                            t2,
                            c2,
                            overlap_1_in_2,
                            overlap_2_in_1,
                        )

                    fk_column = next(
                        c for c in profiles[fk_table].columns
                        if c.name == fk_col
                    )
                    pk_column = next(
                        c for c in profiles[pk_table].columns
                        if c.name == pk_col
                    )

                    pk_uniqueness = pk_column.uniqueness_ratio
                    fk_uniqueness = fk_column.uniqueness_ratio

                    # A target's merely-unique foreign key is not enough.
                    # Prefer the target table's own primary key so a shared
                    # parent key does not turn two child facts into a fake
                    # direct relationship.
                    if not _is_table_own_primary_key(
                        profiles[pk_table],
                        pk_col,
                    ):
                        continue

                    # A direct FK->PK edge needs a genuinely parent-like
                    # target. This avoids inventing relationships between
                    # two transaction/event tables merely because IDs happen
                    # to overlap.
                    if pk_uniqueness < 0.95:
                        continue

                    confidence = _candidate_confidence(
                        fk_to_pk_overlap,
                        fk_uniqueness,
                        pk_uniqueness,
                    )

                    reason = (
                        f"Column names match ({fk_col} ~ {pk_col}); "
                        f"{fk_to_pk_overlap * 100:.0f}% of "
                        f"{fk_table}.{fk_col} values exist in "
                        f"{pk_table}.{pk_col}; "
                        f"{pk_table}.{pk_col} is highly unique "
                        f"(uniqueness {pk_uniqueness * 100:.0f}%)"
                    )

                    candidates.append(
                        RelationshipCandidate(
                            from_table=fk_table,
                            from_column=fk_col,
                            to_table=pk_table,
                            to_column=pk_col,
                            confidence=confidence,
                            reason=reason,
                            is_many_to_many=False,
                        )
                    )

    # Self-references remain supported.
    candidates.extend(
        detect_self_referencing_relationships(profiles)
    )

    # Canonical deterministic de-duplication.
    best_by_key: dict[tuple, RelationshipCandidate] = {}

    for candidate in candidates:
        key = _relationship_key(
            candidate.from_table,
            candidate.from_column,
            candidate.to_table,
            candidate.to_column,
        )

        existing = best_by_key.get(key)

        if (
            existing is None
            or candidate.confidence > existing.confidence
        ):
            best_by_key[key] = candidate

    return sorted(
        best_by_key.values(),
        key=lambda r: (
            -r.confidence,
            r.from_table,
            r.from_column,
            r.to_table,
            r.to_column,
        ),
    )


def canonicalize_relationships(
    relationships: list[RelationshipCandidate],
) -> list[RelationshipCandidate]:
    """
    Merge deterministic and AI suggestions representing the same
    relationship.

    If an AI suggestion points in the reverse direction of an existing
    relationship, it is merged into that relationship instead of being
    displayed as a second relationship.

    Deterministic evidence wins the governed graph. AI can increase the
    confidence/reasoning of a candidate but cannot create a duplicate edge.
    """

    by_key: dict[tuple, RelationshipCandidate] = {}

    for rel in relationships:
        key = _relationship_key(
            rel.from_table,
            rel.from_column,
            rel.to_table,
            rel.to_column,
        )

        existing = by_key.get(key)

        if existing is None:
            by_key[key] = rel
            continue

        # Keep the canonical deterministic relationship.
        if (
            existing.is_ai_suggested
            and not rel.is_ai_suggested
        ):
            rel.reason = (
                f"{rel.reason} "
                f"AI independently supported this relationship."
            )
            by_key[key] = rel
            continue

        # If both are deterministic, retain the stronger evidence.
        if (
            not existing.is_ai_suggested
            and not rel.is_ai_suggested
        ):
            if rel.confidence > existing.confidence:
                by_key[key] = rel
            continue

        # If an AI candidate is the only evidence, retain it as an
        # AI-reviewed suggestion. Do not silently turn it into a
        # deterministic relationship.
        if (
            existing.is_ai_suggested
            and rel.is_ai_suggested
        ):
            if rel.confidence > existing.confidence:
                by_key[key] = rel
            continue

        # Existing deterministic + new AI:
        # preserve deterministic confidence and annotate evidence.
        if not existing.is_ai_suggested and rel.is_ai_suggested:
            existing.reason = (
                f"{existing.reason} "
                f"AI independently supported this relationship "
                f"({rel.confidence * 100:.0f}% AI confidence)."
            )

    return sorted(
        by_key.values(),
        key=lambda r: -r.confidence,
    )


_ID_TOKEN_PATTERN = re.compile(r'(^|[^a-z0-9])id([^a-z0-9]|$)', re.IGNORECASE)


def _looks_like_id_column(col_name: str, dtype: str) -> bool:
    """
    Matches "id" as a whole word/token anywhere in the column name --
    e.g. "id (pk)", "customer_id", "record-id#", "ID" -- rather than
    only a plain endswith("id") check on the raw name (which misses
    punctuation/annotation right after "id", like "id (pk)") or a fully
    merged normalized string (which can accidentally join "id" with an
    adjacent word, e.g. "id (pk)" -> "idpk", breaking a suffix check
    just as badly in the opposite direction). A word-boundary match on
    the original string avoids both failure modes.

    Deliberately does NOT exclude float-typed columns. An earlier
    version returned False for any float dtype, on the assumption that
    id columns are always clean integers -- but pandas silently upcasts
    an integer column to float the moment it contains even one null,
    which is a very common, legitimate pattern for a NULLABLE foreign
    key (e.g. manager_id where the top of an org chart has no manager,
    or an optional promo_code_id). That earlier version made every such
    column invisible to ID detection, letting it be proposed as an
    AVG()/SUM() metric -- caught by testing a self-referencing
    employee/manager hierarchy, a realistic case that surfaced this
    immediately. The name-token match alone is a reliable enough
    signal: a column genuinely named with "id" as a token is not a
    legitimate continuous measure, whatever its pandas-inferred dtype.
    """
    return bool(_ID_TOKEN_PATTERN.search(col_name))


CATEGORY_NAME_SIGNALS = [
    "decile", "rating", "score", "tier", "grade", "level", "rank",
    "class", "category", "segment", "quartile", "quintile", "stars",
]


def _looks_like_rating_or_category_column(col: ColumnProfile, row_count: int) -> bool:
    """
    A column is treated as a rating/category (excluded from metrics) only
    if it's BOTH low-cardinality AND named like a rating/category.
    Cardinality alone is not sufficient: a genuine additive count column
    (e.g. nrx_count, ranging 0-7 in practice) can have very few distinct
    values without being a rating scale — excluding it on cardinality
    alone was a real false positive, caught by testing against real
    data, that silently dropped a legitimate metric a domain expert
    would expect to see (e.g. "Total New Prescriptions").
    """
    if "int" not in col.dtype or row_count == 0:
        return False
    name_lower = col.name.lower()
    name_signals = any(sig in name_lower for sig in CATEGORY_NAME_SIGNALS)
    low_cardinality = col.distinct_count <= 15 and (col.distinct_count / row_count) < 0.5
    return low_cardinality and name_signals


NON_ADDITIVE_PATTERNS = [
    "rate", "ratio", "percent", "pct", "score", "average", "avg",
    "age", "temperature", "pressure", "index", "level",
    "duration", "cycle_time", "response_time", "latency",
]


def _looks_non_additive(col_name: str) -> bool:
    """
    A column whose name signals it's a measurement/rate/ratio rather than
    a genuine additive quantity (heart_rate, conversion_rate, avg_score,
    blood_pressure) should never be proposed as a SUM() metric — summing
    a rate or a percentage across rows produces a number with no real
    business meaning. These are legitimate candidates for AVG() instead,
    which the metric generator does not yet propose automatically (a
    human reviewing the draft can add it) — the point of this check is
    only to keep an obviously wrong SUM() out of the auto-generated set.
    """
    name_lower = col_name.lower()
    return any(p in name_lower for p in NON_ADDITIVE_PATTERNS)



def _genuine_measure_columns(
    profile: TableProfile,
) -> list[ColumnProfile]:
    numeric_cols = [
        c for c in profile.columns
        if (
            "int" in c.dtype
            or "float" in c.dtype
        )
    ]

    return [
        c
        for c in numeric_cols
        if not _looks_like_id_column(
            c.name,
            c.dtype,
        )
        and not _looks_like_rating_or_category_column(
            c,
            profile.row_count,
        )
    ]


def _event_table_score(
    profile: TableProfile,
    incoming_count: int,
    outgoing_count: int,
) -> float:
    """
    Estimate whether a table behaves like a business event/fact.

    This is intentionally domain-agnostic.

    Signals:
      - real numeric measures
      - event/time columns
      - incoming child rows
      - multiple FK relationships
      - row-level transaction/event structure

    A lookup/master dimension usually has descriptive columns and a
    unique key but few/no measures. A child event table such as Defects
    can therefore remain a FACT even though Production Runs references
    it or vice versa.
    """

    score = 0.0

    measures = _genuine_measure_columns(profile)

    if measures:
        score += 0.45

    lower_names = {
        c.name.lower()
        for c in profile.columns
    }

    event_signals = (
        "date",
        "time",
        "timestamp",
        "start",
        "end",
        "duration",
        "quantity",
        "amount",
        "cost",
        "value",
        "count",
        "rate",
        "severity",
        "defect",
        "status",
        "result",
        "event",
        "run",
        "maintenance",
    )

    if any(
        any(token in name for token in event_signals)
        for name in lower_names
    ):
        score += 0.20

    if incoming_count > 0:
        score += 0.10

    if outgoing_count > 0:
        score += min(
            0.20,
            0.10 * outgoing_count,
        )

    # Very small master/lookup tables with a highly unique ID and no
    # measures should remain dimensions.
    if (
        profile.row_count > 0
        and measures == []
    ):
        score -= 0.30

    return max(
        0.0,
        min(1.0, score),
    )



def _table_has_event_signals(
    profile: TableProfile,
) -> bool:
    names = {
        c.name.lower()
        for c in profile.columns
    }

    signals = (
        "date",
        "time",
        "timestamp",
        "quantity",
        "amount",
        "cost",
        "value",
        "count",
        "rate",
        "duration",
        "downtime",
        "production",
        "defect",
        "maintenance",
        "transaction",
        "order",
        "encounter",
        "claim",
        "payment",
        "usage",
        "reading",
        "booking",
        "attendance",
        "payroll",
        "run",
        "event",
    )

    return any(
        any(token in name for token in signals)
        for name in names
    )


def _is_reference_numeric_column(
    col: ColumnProfile,
) -> bool:
    """
    Numeric columns on master/reference entities are not automatically
    measures. Examples: standard_cost on Products, list_price on a
    product master, credit_limit on a customer master.

    They become measures only when the table otherwise behaves like an
    event/transaction table.
    """
    name = col.name.lower()

    reference_tokens = (
        "standard_cost",
        "list_price",
        "unit_price",
        "price",
        "cost",
        "limit",
        "rate",
        "threshold",
        "capacity",
        "target",
    )

    return any(
        token in name
        for token in reference_tokens
    )


def _genuine_measure_columns(
    profile: TableProfile,
    master_like: bool = False,
) -> list[ColumnProfile]:
    numeric_cols = [
        c for c in profile.columns
        if (
            "int" in c.dtype
            or "float" in c.dtype
        )
    ]

    measures = []

    for col in numeric_cols:
        if _looks_like_id_column(
            col.name,
            col.dtype,
        ):
            continue

        if _looks_like_rating_or_category_column(
            col,
            profile.row_count,
        ):
            continue

        if master_like and _is_reference_numeric_column(col):
            continue

        measures.append(col)

    return measures


def _master_entity_score(
    profile: TableProfile,
    incoming_count: int,
    outgoing_count: int,
) -> float:
    """
    Score a table as a descriptive/master entity.

    A unique key plus mostly descriptive attributes should remain a
    dimension even when it contains reference numeric attributes such
    as standard_cost.
    """
    id_columns = [
        c for c in profile.columns
        if (
            _looks_like_id_column(c.name, c.dtype)
            and c.uniqueness_ratio >= 0.95
        )
    ]

    if not id_columns:
        return 0.0

    score = 0.55

    descriptive_count = sum(
        1
        for c in profile.columns
        if (
            "object" in c.dtype
            or "string" in c.dtype.lower()
        )
        and not _looks_like_id_column(
            c.name,
            c.dtype,
        )
    )

    if descriptive_count >= 1:
        score += 0.20

    if descriptive_count >= 2:
        score += 0.10

    # Master entities commonly contain dates (commission_date, birth_date,
    # effective_date) and reference values (standard_cost, list_price).
    # Only strong transaction/event vocabulary should disqualify a master.
    strong_event_tokens = (
        "transaction",
        "order",
        "encounter",
        "claim",
        "payment",
        "usage",
        "reading",
        "booking",
        "attendance",
        "payroll",
        "defect",
        "production",
        "maintenance",
        "run",
        "event",
        "ticket",
        "service",
        "shipment",
        "invoice",
        "purchase",
        "sale",
    )
    if any(
        any(token in c.name.lower() for token in strong_event_tokens)
        for c in profile.columns
    ):
        score -= 0.30

    if incoming_count > 0:
        score += 0.05

    if outgoing_count > 0:
        score -= 0.10

    return max(
        0.0,
        min(1.0, score),
    )


def classify_tables(
    profiles: dict[str, TableProfile],
    relationships: list[RelationshipCandidate],
) -> tuple[list[str], list[str]]:
    """
    Domain-neutral entity-role classification.

    FACT:
      Event/transaction/measurement table with real measures or clear
      event signals.

    DIMENSION:
      Master/reference entity with a highly unique identifier and
      descriptive attributes, even if it contains reference numeric
      values such as standard_cost.

    This supports multiple facts sharing conformed dimensions and does
    not contain any domain-specific if/elif logic.
    """
    incoming = {
        name: 0
        for name in profiles
    }

    outgoing = {
        name: 0
        for name in profiles
    }

    for rel in relationships:
        if rel.from_table == rel.to_table:
            continue

        outgoing[rel.from_table] += 1
        incoming[rel.to_table] += 1

    facts: list[str] = []
    dimensions: list[str] = []

    for name, profile in profiles.items():

        master_score = _master_entity_score(
            profile,
            incoming_count=incoming[name],
            outgoing_count=outgoing[name],
        )

        master_like = master_score >= 0.70

        measures = _genuine_measure_columns(
            profile,
            master_like=master_like,
        )

        event_shape = _table_has_event_signals(
            profile
        )

        # Strong master/reference entity.
        if master_like and not (
            measures
            and event_shape
            and outgoing[name] >= 1
        ):
            dimensions.append(name)
            continue

        # Event/fact entity.
        if measures and (
            outgoing[name] >= 1
            or incoming[name] >= 1
            or event_shape
        ):
            facts.append(name)
            continue

        # A table with explicit event signals and an identifier can still
        # be a fact even if it has no numeric measure.
        if (
            event_shape
            and outgoing[name] >= 1
            and not master_like
        ):
            facts.append(name)
            continue

        # Default to dimension only when the table strongly looks like a
        # reference/master entity. Otherwise keep it as a fact candidate
        # if it has rows and an event identifier.
        if master_like:
            dimensions.append(name)
        else:
            facts.append(name)

    # A standalone numeric table is still a fact.
    if len(profiles) == 1:
        only = next(iter(profiles))
        if _genuine_measure_columns(profiles[only]):
            facts = [only]
            dimensions = []

    return facts, dimensions


def generate_metrics(model_tables: dict[str, TableProfile], facts: list[str], relationships: list[RelationshipCandidate]) -> list[BusinessMetric]:
    metrics = []
    for fact_name in facts:
        profile = model_tables[fact_name]
        if profile.row_count == 0:
            # No rows means no real aggregate to compute -- a SUM/AVG/
            # COUNT metric over an empty table is not a genuine business
            # metric, just a placeholder that would render a blank or
            # misleading KPI card. Skip metric generation for this fact
            # entirely rather than propose hollow metrics.
            continue
        related_fk_cols = {r.from_column for r in relationships if r.from_table == fact_name}
        for c in profile.columns:
            if c.name in related_fk_cols:
                continue
            if c.null_pct >= 100.0:
                # Every value is null -- there is nothing to sum or
                # average, and proposing this as a metric would always
                # render as a blank/zero KPI card with no real meaning.
                continue
            is_id = _looks_like_id_column(c.name, c.dtype)
            is_rating = _looks_like_rating_or_category_column(c, profile.row_count)
            is_non_additive = _looks_non_additive(c.name)
            if ("int" in c.dtype or "float" in c.dtype) and not is_id and not is_rating:
                if is_non_additive:
                    # A rate/measurement/score column (e.g. heart_rate,
                    # conversion_rate) shouldn't be summed, but AVG() is
                    # a genuinely meaningful metric for it -- excluding
                    # it entirely was a real gap: a healthcare demo
                    # naming "average heart rate" as an expected metric
                    # would otherwise never see it generated.
                    metrics.append(BusinessMetric(
                        name=f"Average {c.name.replace('_', ' ').title()}",
                        expression=f"AVG({c.name})",
                        table=fact_name,
                        description=f"Average {c.name} across all {fact_name} records",
                    ))
                else:
                    metrics.append(BusinessMetric(
                        name=f"Total {c.name.replace('_', ' ').title()}",
                        expression=f"SUM({c.name})",
                        table=fact_name,
                        description=f"Sum of {c.name} across all {fact_name} records",
                    ))
        clean_name = fact_name.replace(".csv", "").replace(".xlsx", "").replace("_", " ").title()
        metrics.append(BusinessMetric(
            name=f"{clean_name} Count", expression="COUNT(*)", table=fact_name,
            description=f"Total number of {fact_name} records",
        ))
    return metrics


def generate_glossary(model_tables: dict[str, TableProfile]) -> list[GlossaryEntry]:
    entries = []
    seen_terms = set()
    for table_name, profile in model_tables.items():
        for c in profile.columns:
            term = c.name.replace("_", " ").title()
            if term in seen_terms:
                continue
            seen_terms.add(term)
            entries.append(GlossaryEntry(
                term=term, definition=f"Column '{c.name}' from {table_name} ({c.dtype})",
                source_column=f"{table_name}.{c.name}",
            ))
    return entries


def run_full_analysis(files: dict[str, pd.DataFrame], domain_name: str) -> SemanticModel:
    profiles = scan_metadata(files)
    detect_data_quality_issues(profiles)
    pii_findings = classify_pii(profiles)
    relationships = detect_relationships(profiles)
    facts, dimensions = classify_tables(profiles, relationships)
    metrics = generate_metrics(profiles, facts, relationships)
    glossary = generate_glossary(profiles)

    warnings = []
    for r in relationships:
        if r.is_many_to_many:
            warnings.append(f"Many-to-many candidate: {r.from_table}.{r.from_column} <-> {r.to_table}.{r.to_column}")
    if not facts:
        warnings.append("No fact table confidently identified — upload a table with a numeric measure and a foreign key to another table")
    referenced = {r.to_table for r in relationships}
    fk_sources = {r.from_table for r in relationships}
    unreferenced_dims = [d for d in dimensions if d not in referenced and d not in fk_sources]
    for d in unreferenced_dims:
        warnings.append(f"'{d}' has no detected relationship to any other table — possible missing dimension link")

    return SemanticModel(
        domain_name=domain_name, tables=profiles, relationships=relationships,
        facts=facts, dimensions=dimensions, metrics=metrics, glossary=glossary,
        warnings=warnings, pii_findings=pii_findings,
    )
