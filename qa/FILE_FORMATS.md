# INVENT File Format QA

Supported uploads: CSV, Excel, JSON, Parquet and XML.

## Parquet
`pyarrow` is pinned in `requirements.txt`. Generate real binary fixtures with:

```bash
python qa/generate_parquet_fixtures.py
```

The generator creates `customers.parquet`, `orders.parquet`, and `products.parquet`.

## XML
XML is parsed with pandas' `etree` parser, so no optional `lxml` dependency is required. The checked-in `qa/fixtures/xml/customers.xml` is a smoke-test fixture.
