#!/usr/bin/env python3
"""
Network Visualization Page
Full interactive network with D3.js
"""

import streamlit as st
import sys
from pathlib import Path

# Add parent directory to path
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from network_component import render_full_network_tab

st.set_page_config(
    page_title="Network - Football Coaches DB",
    page_icon="🕸️",
    layout="wide"
)

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
