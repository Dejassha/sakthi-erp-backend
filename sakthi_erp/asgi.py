"""
ASGI config for sakthi_erp project.

Exposes the ASGI callable as a module-level variable named ``application``.
For modern async servers (Uvicorn / Daphne) handling WebSockets or async HTTP.
"""

import os
from pathlib import Path
from django.core.asgi import get_asgi_application

# Explicitly load .env from the backend root directory for ASGI servers (Uvicorn / Daphne)
base_dir = Path(__file__).resolve().parent.parent
env_path = base_dir / ".env"

if env_path.exists():
    try:
        import dotenv

        dotenv.load_dotenv(env_path)
    except ImportError:
        pass

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sakthi_erp.settings")

application = get_asgi_application()
