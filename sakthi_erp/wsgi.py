import os
from pathlib import Path
from django.core.wsgi import get_wsgi_application

# Explicitly load .env from the backend root directory for Gunicorn / WSGI servers
base_dir = Path(__file__).resolve().parent.parent
env_path = base_dir / ".env"

if env_path.exists():
    try:
        import dotenv

        dotenv.load_dotenv(env_path)
    except ImportError:
        pass

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sakthi_erp.settings")

application = get_wsgi_application()
