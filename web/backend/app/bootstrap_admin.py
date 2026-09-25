"""Initialize once; never accept the password in process arguments."""

import getpass
import os

from app.composition import initialize_administrator
from app.contracts.errors import ServiceError
from app.infrastructure.settings import Settings


def main() -> int:
    settings = Settings()
    if settings.database_url is None:
        print("DATABASE_URL is required")
        return 1
    username = os.environ.get("BOOTSTRAP_USERNAME") or input("Admin username: ")
    password = os.environ.pop("BOOTSTRAP_PASSWORD", None) or getpass.getpass("Temporary password: ")
    try:
        initialize_administrator(settings, username, password)
    except ServiceError as error:
        print(f"Initialization failed: {error.code.value}")
        return 1
    except Exception:
        print("Initialization failed; check database availability and migrations")
        return 1
    print("Administrator initialized; password change required at first login")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
