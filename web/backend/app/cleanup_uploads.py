"""Local maintenance entry point; never accepts a caller-provided storage path."""

from app.composition import cleanup_uploads
from app.infrastructure.settings import Settings


def main():
    count = cleanup_uploads(Settings())
    print(f"Removed {count} expired unconsumed upload records")


if __name__ == "__main__":
    main()
