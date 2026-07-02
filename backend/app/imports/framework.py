"""Supplier import framework (docs/spec/09 §import framework).

Data arrives as anything (Excel/CSV/photos/WhatsApp) — so the framework is:
raw rows in → mapping applied → per-row validation → dry-run report →
idempotent commit. Every run is a supplier_import_jobs row; every source row
is a supplier_import_rows row with ok/warn/error + messages. Dry-run never
touches target tables; commit is safe to re-run (upsert by natural key).

First target: diamond_price_tables (the MVP admin-entered stone prices).
"""

import csv
import io
import uuid
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    DiamondPriceTable,
    StoneShape,
    StoneType,
    SupplierImportJob,
    SupplierImportRow,
)

REQUIRED_FIELDS = [
    "stone_type",
    "shape",
    "carat_min",
    "carat_max",
    "color",
    "clarity",
    "price_per_carat",
    "currency",
]


def parse_csv(text: str) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(text))
    return [dict(row) for row in reader]


def apply_mapping(raw: dict[str, str], mapping: dict[str, str] | None) -> dict[str, str]:
    """mapping: {target_field: source_column}; None = columns already match."""
    if not mapping:
        return raw
    return {field: raw.get(column, "") for field, column in mapping.items()}


async def _validate_row(
    session: AsyncSession, tenant_id: uuid.UUID, mapped: dict[str, str]
) -> tuple[dict[str, Any] | None, list[str]]:
    """Returns (normalized_row, errors). normalized_row is None on error."""
    errors: list[str] = []
    for field in REQUIRED_FIELDS:
        if not str(mapped.get(field, "")).strip():
            errors.append(f"missing required field '{field}'")
    if errors:
        return None, errors

    stone_type = (
        await session.execute(
            select(StoneType).where(
                StoneType.tenant_id == tenant_id, StoneType.key == mapped["stone_type"].strip()
            )
        )
    ).scalar_one_or_none()
    if stone_type is None:
        errors.append(f"unknown stone_type '{mapped['stone_type']}'")

    shape = (
        await session.execute(
            select(StoneShape).where(
                StoneShape.tenant_id == tenant_id, StoneShape.key == mapped["shape"].strip()
            )
        )
    ).scalar_one_or_none()
    if shape is None:
        errors.append(f"unknown shape '{mapped['shape']}'")

    def _dec(field: str) -> Decimal | None:
        try:
            value = Decimal(str(mapped[field]).strip())
        except (InvalidOperation, ValueError):
            errors.append(f"'{field}' is not a number: {mapped[field]!r}")
            return None
        if value <= 0:
            errors.append(f"'{field}' must be positive")
            return None
        return value

    carat_min = _dec("carat_min")
    carat_max = _dec("carat_max")
    price = _dec("price_per_carat")
    if carat_min is not None and carat_max is not None and carat_min >= carat_max:
        errors.append("carat_min must be < carat_max")

    currency = str(mapped["currency"]).strip().upper()
    if len(currency) != 3:
        errors.append(f"currency must be a 3-letter code, got {currency!r}")

    if errors:
        return None, errors
    return (
        {
            "stone_type_id": stone_type.id,
            "shape_id": shape.id,
            "carat_min": carat_min,
            "carat_max": carat_max,
            "color": str(mapped["color"]).strip().upper(),
            "clarity": str(mapped["clarity"]).strip().upper(),
            "price_per_carat": price,
            "currency": currency,
        },
        [],
    )


async def run_diamond_price_import(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    csv_text: str,
    mapping: dict[str, str] | None = None,
    dry_run: bool = True,
    supplier_id: uuid.UUID | None = None,
) -> SupplierImportJob:
    """Dry-run: validate every row, write the job + row report, touch nothing

    else. Commit: upsert diamond_price_tables keyed on
    (stone_type, shape, carat band, color, clarity, supplier) — re-running
    the same file changes nothing (idempotent).
    """
    job = SupplierImportJob(
        tenant_id=tenant_id,
        supplier_id=supplier_id,
        source="csv",
        status="running",
        mapping=mapping,
        dry_run=dry_run,
    )
    session.add(job)
    await session.flush()

    raw_rows = parse_csv(csv_text)
    ok = errors = created = updated = 0

    for raw in raw_rows:
        mapped = apply_mapping(raw, mapping)
        normalized, row_errors = await _validate_row(session, tenant_id, mapped)
        status = "error" if row_errors else "ok"
        session.add(
            SupplierImportRow(
                import_job_id=job.id,
                raw=raw,
                mapped={k: str(v) for k, v in (normalized or {}).items()} or None,
                status=status,
                messages={"errors": row_errors} if row_errors else None,
            )
        )
        if row_errors:
            errors += 1
            continue
        ok += 1

        if not dry_run:
            existing = (
                await session.execute(
                    select(DiamondPriceTable).where(
                        DiamondPriceTable.tenant_id == tenant_id,
                        DiamondPriceTable.stone_type_id == normalized["stone_type_id"],
                        DiamondPriceTable.shape_id == normalized["shape_id"],
                        DiamondPriceTable.carat_min == normalized["carat_min"],
                        DiamondPriceTable.carat_max == normalized["carat_max"],
                        DiamondPriceTable.color == normalized["color"],
                        DiamondPriceTable.clarity == normalized["clarity"],
                        DiamondPriceTable.supplier_id == supplier_id,
                    )
                )
            ).scalar_one_or_none()
            if existing is None:
                session.add(
                    DiamondPriceTable(tenant_id=tenant_id, supplier_id=supplier_id, **normalized)
                )
                created += 1
            elif (
                existing.price_per_carat != normalized["price_per_carat"]
                or existing.currency != normalized["currency"]
            ):
                existing.price_per_carat = normalized["price_per_carat"]
                existing.currency = normalized["currency"]
                updated += 1

    job.status = "completed" if errors == 0 else ("partial" if ok else "failed")
    job.stats = {
        "rows": len(raw_rows),
        "ok": ok,
        "errors": errors,
        "created": created,
        "updated": updated,
    }
    await session.flush()
    return job
