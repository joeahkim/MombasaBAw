"""Load the single local test record from details.txt."""

from pathlib import Path
import re


REQUIRED_FIELDS = ("Name", "Email", "Phone")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_PATTERN = re.compile(r"^\+?[0-9][0-9 ()-]{5,}$")


class DetailsError(ValueError):
    """Raised when details.txt is present but has invalid contents."""


def load_details(path=None):
    """Return the record identifier and its Name, Email, and Phone values."""
    details_path = Path(path) if path is not None else Path(__file__).with_name("details.txt")
    try:
        lines = details_path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        raise FileNotFoundError(f"Details file not found: {details_path}") from None

    record_id = None
    values = {}

    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if line.startswith("[") and line.endswith("]"):
            if record_id is not None:
                raise DetailsError(
                    f"Line {line_number}: only one record is supported in this file."
                )
            record_id = line[1:-1].strip()
            if not record_id:
                raise DetailsError(f"Line {line_number}: record identifier cannot be empty.")
            continue

        if record_id is None:
            raise DetailsError(f"Line {line_number}: expected a [RECORD_ID] header first.")
        if ":" not in line:
            raise DetailsError(f"Line {line_number}: expected a field in 'Name: value' format.")

        field, value = (part.strip() for part in line.split(":", 1))
        if field not in REQUIRED_FIELDS:
            raise DetailsError(
                f"Line {line_number}: invalid field {field!r}; expected Name, Email, or Phone."
            )
        if field in values:
            raise DetailsError(f"Line {line_number}: duplicate field {field!r}.")
        if not value:
            raise DetailsError(f"Line {line_number}: {field} cannot be empty.")
        values[field] = value

    if record_id is None:
        raise DetailsError("No [RECORD_ID] header was found.")

    missing = [field for field in REQUIRED_FIELDS if field not in values]
    if missing:
        raise DetailsError("Missing required field(s): " + ", ".join(missing) + ".")
    if not EMAIL_PATTERN.fullmatch(values["Email"]):
        raise DetailsError("Email must be in a valid address format.")
    if not PHONE_PATTERN.fullmatch(values["Phone"]):
        raise DetailsError("Phone must contain a valid number and may start with +.")

    return {"id": record_id, **values}


if __name__ == "__main__":
    print(load_details())
