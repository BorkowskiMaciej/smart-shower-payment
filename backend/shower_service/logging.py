import json


def log(message: str, data: dict | None = None) -> None:
    """Emit structured operational data without customer details or secrets."""
    entry = {"message": message}
    if data:
        entry.update(data)
    print(json.dumps(entry, ensure_ascii=False, default=str))
