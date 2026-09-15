"""Legacy single-Function entry point, retained for compatibility.

Current vercel.json uses Services with backend/app/main.py directly.
This module is not part of the current production route configuration.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))

from app.main import app  # noqa: E402,F401  (Vercel は `app` という ASGI アプリを探す)
