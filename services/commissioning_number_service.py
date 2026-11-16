"""Race-safe tenant-scoped numbering on MaterialHub's document_sequence table."""
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from extensions import db
from models import DocumentSequence

SEQUENCE_KEYS = {
    "A": "CS-A", "B": "CS-B", "C": "CS-C",
    "PUNCH-A": "PN-A", "PUNCH-B": "PN-B", "PUNCH-C": "PN-C", "PUNCH-D": "PN-D",
}


def next_commissioning_number(company_name: str, sequence_key: str) -> int:
    if not company_name or not company_name.strip():
        raise ValueError("company_name is required")
    if sequence_key not in SEQUENCE_KEYS.values() or len(sequence_key) > 10:
        raise ValueError("Unknown or invalid OPERA sequence key")
    dialect = db.session.get_bind().dialect.name
    values = {"key": sequence_key, "company_name": company_name, "last_value": 0}
    if dialect == "postgresql":
        db.session.execute(pg_insert(DocumentSequence).values(**values).on_conflict_do_nothing(
            index_elements=["key", "company_name"]))
    elif dialect == "sqlite":
        db.session.execute(sqlite_insert(DocumentSequence).values(**values).on_conflict_do_nothing(
            index_elements=["key", "company_name"]))
    else:
        raise RuntimeError(f"Unsupported sequence database dialect: {dialect}")
    db.session.execute(
        update(DocumentSequence).where(
            DocumentSequence.key == sequence_key,
            DocumentSequence.company_name == company_name,
        ).values(last_value=DocumentSequence.last_value + 1)
    )
    return db.session.execute(select(DocumentSequence.last_value).where(
        DocumentSequence.key == sequence_key,
        DocumentSequence.company_name == company_name,
    )).scalar_one()


def format_checksheet_number(project_no: str, sheet_type: str, sequence: int) -> str:
    sheet_type = getattr(sheet_type, "value", sheet_type)
    if sheet_type not in {"A", "B", "C"}:
        raise ValueError("sheet_type must be A, B or C")
    return f"{project_no}-{sheet_type}-{sequence:05d}"


def format_punch_number(project_no: str, category: str, sequence: int) -> str:
    category = getattr(category, "value", category)
    if category not in {"A", "B", "C", "D"}:
        raise ValueError("category must be A, B, C or D")
    return f"{project_no}-PUNCH-{category}-{sequence:05d}"
