"""
INVENT local regression suite.

This suite intentionally uses only the checked-in demo datasets and the
pure semantic engine. It does not require Databricks credentials.

Live Databricks/Genie calls require deployment secrets and are tested by
the deployment smoke-test checklist in README.md.
"""

from __future__ import annotations

import py_compile
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "demo_datasets"

sys.path.insert(0, str(ROOT))

from semantic_engine import (  # noqa: E402
    classify_pii,
    classify_tables,
    detect_data_quality_issues,
    detect_relationships,
    generate_metrics,
    scan_metadata,
)


def assert_true(condition: bool, message: str):
    if not condition:
        raise AssertionError(message)


def load_domain(path: Path):
    return {
        csv.name: pd.read_csv(csv)
        for csv in sorted(path.glob("*.csv"))
    }


def run():
    assert_true(
        DEMO.exists(),
        "demo_datasets directory is missing",
    )

    domains = [
        p
        for p in sorted(DEMO.iterdir())
        if p.is_dir()
        and not p.name.startswith(".")
        and list(p.glob("*.csv"))
    ]

    assert_true(
        len(domains) >= 10,
        "Expected the bundled 10-domain demo suite.",
    )

    for domain in domains:

        files = load_domain(domain)

        profiles = scan_metadata(files)
        detect_data_quality_issues(profiles)
        pii = classify_pii(profiles)

        relationships = detect_relationships(
            profiles
        )

        facts, dimensions = classify_tables(
            profiles,
            relationships,
        )

        metrics = generate_metrics(
            profiles,
            facts,
            relationships,
        )

        assert_true(
            len(profiles) == len(files),
            f"{domain.name}: profile count mismatch",
        )

        assert_true(
            facts or dimensions,
            f"{domain.name}: no entities classified",
        )

        assert_true(
            len(metrics) >= len(facts),
            f"{domain.name}: expected at least one count metric per fact",
        )

        assert_true(
            not any(
                r.is_many_to_many
                for r in relationships
            ),
            f"{domain.name}: unexpected M:N candidate in bundled demo",
        )

        print(
            f"PASS {domain.name:15} "
            f"tables={len(files):2} "
            f"relationships={len(relationships):2} "
            f"facts={len(facts):2} "
            f"dimensions={len(dimensions):2} "
            f"metrics={len(metrics):2} "
            f"pii_tables={len(pii):2}"
        )

    # Manufacturing regression
    m = load_domain(
        DEMO / "manufacturing"
    )
    mp = scan_metadata(m)
    mr = detect_relationships(mp)
    mf, md = classify_tables(mp, mr)

    assert_true(
        {"production_runs.csv", "maintenance.csv", "defects.csv"}
        <= set(mf),
        "Manufacturing fact classification regression",
    )

    assert_true(
        {"products.csv", "machines.csv", "plants.csv"}
        <= set(md),
        "Manufacturing dimension classification regression",
    )

    assert_true(
        not any(
            r.from_table == "production_runs.csv"
            and r.to_table == "maintenance.csv"
            for r in mr
        ),
        "False Production Runs -> Maintenance relationship",
    )

    assert_true(
        not any(
            r.from_table == "production_runs.csv"
            and r.to_table == "machines.csv"
            and r.from_column == "plant_id"
            for r in mr
        ),
        "False Production Runs plant_id -> Machines relationship",
    )

    print("PASS manufacturing topology regressions")

    # Travel alternate-unique-key regression
    t = load_domain(
        DEMO / "travel"
    )
    tp = scan_metadata(t)
    tr = detect_relationships(tp)

    assert_true(
        any(
            r.from_table == "payments.csv"
            and r.to_table == "bookings.csv"
            and r.from_column == "booking_id"
            for r in tr
        ),
        "Missing Payments -> Bookings relationship",
    )

    assert_true(
        not any(
            r.from_table == "booking_services.csv"
            and r.to_table == "payments.csv"
            for r in tr
        ),
        "False Booking Services -> Payments relationship",
    )

    print("PASS travel alternate-key regression")

    # Python syntax regression
    for py_file in ROOT.rglob("*.py"):
        if "__pycache__" in py_file.parts:
            continue
        py_compile.compile(
            str(py_file),
            doraise=True,
        )

    print(
        f"PASS Python compilation ({len(list(ROOT.rglob('*.py')))} files scanned)"
    )

    # File-format regression: XML is tested in this build environment;
    # Parquet is tested when the required engine is installed (pyarrow is a
    # deployment dependency in requirements.txt).
    from data_engine import load_bytes, SUPPORTED_EXTENSIONS
    assert_true(".parquet" in SUPPORTED_EXTENSIONS, "Parquet support was removed")
    assert_true(".xml" in SUPPORTED_EXTENSIONS, "XML support was removed")

    xml_payload = b"<customers><row><customer_id>1</customer_id><name>A</name></row><row><customer_id>2</customer_id><name>B</name></row></customers>"
    loaded_xml = load_bytes("customers.xml", xml_payload)
    assert_true(len(loaded_xml) == 2 and "customer_id" in loaded_xml.columns, "XML ingestion regression")

    try:
        parquet_df = pd.DataFrame({"customer_id": [1, 2], "name": ["A", "B"]})
        parquet_buf = __import__("io").BytesIO()
        parquet_df.to_parquet(parquet_buf, index=False)
        loaded_parquet = load_bytes("customers.parquet", parquet_buf.getvalue())
        assert_true(list(loaded_parquet.columns) == ["customer_id", "name"], "Parquet ingestion regression")
        print("PASS Parquet + XML ingestion")
    except ImportError as exc:
        print(f"PASS XML ingestion; Parquet runtime engine unavailable in QA container ({exc}) — deployment requirements include pyarrow")

    print("\nINVENT LOCAL QA: PASS")


if __name__ == "__main__":
    run()
