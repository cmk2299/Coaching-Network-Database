#!/usr/bin/env python3
"""
Network Visualization Page
Full interactive network with D3.js
"""

import streamlit as st
import sys
from pathlib import Path

st.set_page_config(
    page_title="Network - Football Coaches DB",
    page_icon="🕸️",
    layout="wide"
)

# Check if network data is available
DATA_DIR = Path(__file__).parent.parent.parent / "data"
network_file = DATA_DIR / "network_graph.json"

if not network_file.exists():
    st.error("⚠️ Network Visualization Not Available")
    st.info("""
    The network visualization requires large data files (38MB+) that are not included in the deployed version due to GitHub file size limits.

    **To use this feature:**
    - Run the dashboard locally with: `streamlit run dashboard/app.py`
    - All network data files are available in the GitHub repository

    **Alternative:** You can still browse coach profiles and see their teammate lists in the main search interface.

    **Coming Soon:** Cloud-hosted network data for full visualization on Streamlit Cloud!
    """)
    st.stop()

# Import only if data is available
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

try:
    from network_component import render_full_network_tab

    # Custom CSS matching main app
    st.markdown("""
    <style>
        .main-header {
            font-size: 2.5rem;
            font-weight: bold;
            margin-bottom: 1rem;
            color: #1d3557;
        }
    </style>
    """, unsafe_allow_html=True)

    # Render the network
    render_full_network_tab()

    # Add footer
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666; font-size: 0.9rem;'>
        <p>Football Coaches Database • 1,095 Nodes • 38,359 Connections</p>
        <p>Use your mouse to drag nodes, scroll to zoom, click for details</p>
    </div>
    """, unsafe_allow_html=True)

except ImportError as e:
    st.error(f"⚠️ Network component not available: {e}")
    st.info("This feature requires additional dependencies. Please run locally.")
