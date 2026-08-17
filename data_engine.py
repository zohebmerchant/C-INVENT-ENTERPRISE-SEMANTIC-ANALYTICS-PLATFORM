"""
Enterprise Semantic Analytics Platform — Data Engine.

Source-agnostic ingestion boundary for the Streamlit POC.
Supports CSV, Excel, JSON, Parquet and XML uploads and exposes a common
DataFrame contract to the semantic engine.

The production architecture keeps connectors behind this boundary so
database/API/cloud/streaming adapters can be added without changing
semantic, analytics or UI code.
"""
from __future__ import annotations

import io
from dataclasses import dataclass
from typing import BinaryIO

import pandas as pd


SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".json", ".parquet", ".xml"}


@dataclass
class IngestedAsset:
    name: str
    dataframe: pd.DataFrame
    source_type: str


def _suffix(name: str) -> str:
    name = name.lower()
    for ext in SUPPORTED_EXTENSIONS:
        if name.endswith(ext):
            return ext
    return ""


def load_bytes(name: str, payload: bytes) -> pd.DataFrame:
    ext = _suffix(name)
    if ext == ".csv":
        return pd.read_csv(io.BytesIO(payload))
    if ext in {".xlsx", ".xls"}:
        return pd.read_excel(io.BytesIO(payload))
    if ext == ".json":
        return pd.read_json(io.BytesIO(payload))
    if ext == ".parquet":
        return pd.read_parquet(io.BytesIO(payload))
    if ext == ".xml":
        # Use pandas' standard-library ElementTree parser so XML uploads do
        # not require the optional lxml package. The default row XPath
        # (./*) works for the common <root><row>...</row></root> shape.
        return pd.read_xml(io.BytesIO(payload), parser="etree")
    raise ValueError(
        f"Unsupported file type for '{name}'. "
        f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
    )


def load_uploaded_files(uploaded_files) -> dict[str, pd.DataFrame]:
    result: dict[str, pd.DataFrame] = {}
    errors = []
    for item in uploaded_files or []:
        try:
            df = load_bytes(item.name, item.getvalue())
            if not isinstance(df, pd.DataFrame):
                raise ValueError("The source did not produce a tabular dataset.")
            result[item.name] = df
        except Exception as exc:
            errors.append(f"{item.name}: {exc}")
    if errors:
        raise ValueError("One or more files could not be loaded:\n" + "\n".join(errors))
    return result


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    seen = set()
    new_cols = []
    for raw in out.columns:
        name = str(raw).strip()
        name = name.replace("\n", " ").replace("\r", " ")
        name = "_".join(name.split())
        if not name:
            name = "unnamed_column"
        candidate = name
        n = 2
        while candidate.lower() in seen:
            candidate = f"{name}_{n}"
            n += 1
        seen.add(candidate.lower())
        new_cols.append(candidate)
    out.columns = new_cols
    return out


def prepare_files(files: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    return {name: normalize_columns(df) for name, df in files.items()}


def source_capabilities() -> dict[str, list[str]]:
    return {
        "File": ["CSV", "Excel", "JSON", "Parquet", "XML"],
        "Database": ["Connector boundary ready"],
        "API": ["Connector boundary ready"],
        "Cloud Storage": ["Connector boundary ready"],
        "Streaming": ["Lakeflow/Auto Loader adapter boundary ready"],
        "Documents": ["Document/RAG adapter boundary ready"],
    }
