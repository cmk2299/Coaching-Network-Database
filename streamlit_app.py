"""
Streamlit Cloud Entrypoint
Redirects to the actual app in dashboard/
"""
import sys
import os

# Add execution folder to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'execution'))

# Import and run the actual app
exec(open(os.path.join(os.path.dirname(__file__), 'dashboard', 'app.py')).read())
