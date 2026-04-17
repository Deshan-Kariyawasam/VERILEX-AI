"""
PythonAnywhere WSGI entry point for the Verilex backend.

Replace YOURUSERNAME with your actual PythonAnywhere username.
The ANTHROPIC_API_KEY is best set via the PythonAnywhere web UI
(Web tab > Environment variables), not hardcoded here.
"""

import sys
import os

# ── Add the project directory to Python's path ────────────────────────────────
project_home = "/home/YOURUSERNAME/verilex-backend"
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# ── Environment variables (set via PA dashboard instead when possible) ────────
# os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-...")
# os.environ.setdefault("CLAUDE_MODEL", "claude-opus-4-7")

# ── Import and expose the Flask app as `application` ─────────────────────────
from app import app as application  # noqa: E402
