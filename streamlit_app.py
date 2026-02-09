"""
Streamlit Cloud Entrypoint
Redirects to the actual app in dashboard/
"""
import sys
import os
from pathlib import Path

# Get the base directory
BASE_DIR = Path(__file__).resolve().parent

# Add execution folder to path
sys.path.insert(0, str(BASE_DIR / 'execution'))

# Import and run the actual app
app_path = BASE_DIR / 'dashboard' / 'app.py'
with open(app_path, 'r', encoding='utf-8') as f:
    exec(f.read(), {'__file__': str(app_path)})
