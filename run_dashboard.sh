#!/bin/bash
# Start the Football Coaches Database Dashboard

cd "$(dirname "$0")"
echo "🚀 Starting Football Coaches Database Dashboard..."
echo ""
python3 -m streamlit run dashboard/app.py --server.port 8501
