"""Load local test records from details.txt (one [ID] block per account)."""

from pathlib import Path
import re


REQUIRED_FIELDS = ("Email", "Phone")
ALLOWED_FIELDS = REQUIRED_FIELDS
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_PATTERN = re.compile(r"^\+?[0-9][0-9 ()-]{5,}$")


class DetailsError(ValueError):
    """Raised when details.txt is present but has invalid contents."""


def load_details(path=None):
    """Return a list of account dicts from details.txt.

    Each dict has keys: ``id``, ``Email``, ``Phone``.
    """
    details_path = (
        Path(path) if path is not None else Path(__file__).with_name("details.txt")
    )
    try:
        lines = details_path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        raise FileNotFoundError(f"Details file not found: {details_path}") from None

    raw_records = []
    current = None
    seen_ids = set()

    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if line.startswith("[") and line.endswith("]"):
            record_id = line[1:-1].strip()
            if not record_id:
                raise DetailsError(
                    f"Line {line_number}: record identifier cannot be empty."
                )
            if record_id in seen_ids:
                raise DetailsError(
                    f"Line {line_number}: duplicate record id {record_id!r}."
                )
            seen_ids.add(record_id)
            current = {"id": record_id, "line": line_number, "values": {}}
            raw_records.append(current)
            continue

        if current is None:
            raise DetailsError(
                f"Line {line_number}: expected a [RECORD_ID] header first."
            )
        if ":" not in line:
            raise DetailsError(
                f"Line {line_number}: expected a field in 'Field: value' format."
            )

        field, value = (part.strip() for part in line.split(":", 1))
        if field not in ALLOWED_FIELDS:
            raise DetailsError(
                f"Line {line_number}: invalid field {field!r}; "
                f"expected one of {', '.join(ALLOWED_FIELDS)}."
            )
        if field in current["values"]:
            raise DetailsError(f"Line {line_number}: duplicate field {field!r}.")
        if not value:
            raise DetailsError(f"Line {line_number}: {field} cannot be empty.")
        current["values"][field] = value

    if not raw_records:
        raise DetailsError("No [RECORD_ID] headers were found.")

    seen_emails = {}
    result = []
    for raw in raw_records:
        record_id = raw["id"]
        values = raw["values"]

        missing = [f for f in REQUIRED_FIELDS if f not in values]
        if missing:
            raise DetailsError(
                f"Record [{record_id}]: missing required field(s): "
                + ", ".join(missing)
                + "."
            )

        email = values["Email"]
        if not EMAIL_PATTERN.fullmatch(email):
            raise DetailsError(f"Record [{record_id}]: invalid email format {email!r}.")
        phone = values["Phone"]
        if not PHONE_PATTERN.fullmatch(phone):
            raise DetailsError(f"Record [{record_id}]: invalid phone format {phone!r}.")

        email_key = email.casefold()
        if email_key in seen_emails:
            raise DetailsError(
                f"Record [{record_id}]: duplicate email {email!r} "
                f"(also used by [{seen_emails[email_key]}])."
            )
        seen_emails[email_key] = record_id

        result.append({"id": record_id, **values})

    return result


if __name__ == "__main__":
    import json

    print(json.dumps(load_details(), indent=2, sort_keys=True))