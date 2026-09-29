#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
from pathlib import Path


def main():
    """Run administrative tasks."""
    # Explicitly load .env from the backend root directory regardless of CWD
    base_dir = Path(__file__).resolve().parent
    env_path = base_dir / ".env"

    if env_path.exists():
        try:
            import dotenv

            dotenv.load_dotenv(env_path)
        except ImportError:
            pass

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sakthi_erp.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
