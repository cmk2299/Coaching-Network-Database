#!/usr/bin/env python3
"""
Network Visualization Component for Streamlit Dashboard
Provides both full network view and ego network view
"""

import json
import streamlit as st
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"


def load_network(filter_name="full"):
    """Load network data"""
    if filter_name == "full":
        filepath = DATA_DIR / "network_graph.json"
    else:
        filepath = DATA_DIR / f"network_graph_{filter_name}.json"

    with open(filepath, 'r') as f:
        return json.load(f)


def get_ego_network(coach_name, network, depth=1):
    """
    Get ego network for a specific coach
    Returns nodes and edges for this coach and their direct connections
    """
    # Find all edges involving this coach
    ego_edges = []
    connected_nodes = set([coach_name])

    for edge in network['edges']:
        if edge['source'] == coach_name:
            ego_edges.append(edge)
            connected_nodes.add(edge['target'])
        elif edge['target'] == coach_name:
            ego_edges.append(edge)
            connected_nodes.add(edge['source'])

    # Get node data for connected nodes
    node_map = {node['name']: node for node in network['nodes']}
    ego_nodes = [node_map[name] for name in connected_nodes if name in node_map]

    return {
        'nodes': ego_nodes,
        'edges': ego_edges,
        'center': coach_name,
        'total_connections': len(connected_nodes) - 1
    }


def render_full_network_tab():
    """Render the full network visualization tab"""
    st.header("🕸️ Network Visualization")

    st.markdown("""
    Explore the complete football coaches network with interactive visualization.
    **Features:** Drag nodes, zoom, search, filter by type
    """)

    # Network filter selector
    col1, col2 = st.columns([1, 3])

    with col1:
        network_filter = st.selectbox(
            "Network View",
            [
                ("coaches_only", "Coaches Only (196)"),
                ("decision_makers", "Decision Makers (95)"),
                ("technical_staff", "Technical Staff (714)"),
                ("academy", "Academy (46)"),
                ("full", "Full Network (1,095)")
            ],
            format_func=lambda x: x[1],
            index=0
        )

        filter_name = network_filter[0]

    with col2:
        st.info("""
        **Legend:**
        🔴 Head Coach | 🔵 Assistant Coach | 🟢 Scout | 🟡 Sporting Director | 🟣 Executive | ⚪ Support Staff
        """)

    # Load network data
    try:
        network = load_network(filter_name)

        # Display stats
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Nodes", len(network['nodes']))
        with col2:
            st.metric("Connections", len(network['edges']))
        with col3:
            avg_connections = len(network['edges']) * 2 / len(network['nodes'])
            st.metric("Avg Connections", f"{avg_connections:.1f}")

        # Embed the HTML visualization
        # We'll create a streamlit-compatible version
        render_d3_network(network, height=700)

    except FileNotFoundError:
        st.error(f"Network file not found for filter: {filter_name}")


def render_d3_network(network, height=700, highlight_node=None):
    """
    Render D3.js network visualization in Streamlit
    """

    # Prepare data for JavaScript
    nodes_json = json.dumps(network['nodes'][:100] if len(network['nodes']) > 100 else network['nodes'])
    edges_json = json.dumps(network['edges'][:500] if len(network['edges']) > 500 else network['edges'])

    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <script src="https://d3js.org/d3.v7.min.js"></script>
        <style>
            body {{ margin: 0; background: #0a0a0a; }}
            #viz {{ width: 100%; height: {height}px; }}
            .node {{ cursor: pointer; stroke: #fff; stroke-width: 1.5px; }}
            .node:hover {{ stroke: #ffd700; stroke-width: 3px; }}
            .link {{ stroke: rgba(100,100,100,0.3); }}
            .label {{ font-size: 10px; fill: #fff; text-anchor: middle;
                     pointer-events: none; text-shadow: 0 0 3px #000; }}
        </style>
    </head>
    <body>
        <svg id="viz"></svg>
        <script>
            const width = window.innerWidth;
            const height = {height};

            const typeColors = {{
                'head_coach': '#ff6b6b',
                'assistant_coach': '#4ecdc4',
                'scout': '#45b7d1',
                'sporting_director': '#f9ca24',
                'executive': '#6c5ce7',
                'youth_coach': '#fd79a8',
                'support_staff': '#a29bfe',
                'unclassified': '#888'
            }};

            const nodes = {nodes_json};
            const links = {edges_json};

            const svg = d3.select('#viz')
                .attr('width', width)
                .attr('height', height);

            const g = svg.append('g');

            const zoom = d3.zoom()
                .scaleExtent([0.1, 10])
                .on('zoom', (event) => {{
                    g.attr('transform', event.transform);
                }});

            svg.call(zoom);

            const simulation = d3.forceSimulation(nodes)
                .force('link', d3.forceLink(links).id(d => d.id).distance(50))
                .force('charge', d3.forceManyBody().strength(-80))
                .force('center', d3.forceCenter(width / 2, height / 2));

            const link = g.append('g')
                .selectAll('line')
                .data(links)
                .join('line')
                .attr('class', 'link')
                .attr('stroke-width', d => Math.sqrt(d.strength || 1) * 0.5);

            const node = g.append('g')
                .selectAll('circle')
                .data(nodes)
                .join('circle')
                .attr('class', 'node')
                .attr('r', 5)
                .attr('fill', d => typeColors[d.type] || '#888')
                .call(d3.drag()
                    .on('start', dragstarted)
                    .on('drag', dragged)
                    .on('end', dragended));

            simulation.on('tick', () => {{
                link
                    .attr('x1', d => d.source.x)
                    .attr('y1', d => d.source.y)
                    .attr('x2', d => d.target.x)
                    .attr('y2', d => d.target.y);

                node
                    .attr('cx', d => d.x)
                    .attr('cy', d => d.y);
            }});

            function dragstarted(event) {{
                if (!event.active) simulation.alphaTarget(0.3).restart();
                event.subject.fx = event.subject.x;
                event.subject.fy = event.subject.y;
            }}

            function dragged(event) {{
                event.subject.fx = event.x;
                event.subject.fy = event.y;
            }}

            function dragended(event) {{
                if (!event.active) simulation.alphaTarget(0);
                event.subject.fx = null;
                event.subject.fy = null;
            }}
        </script>
    </body>
    </html>
    """

    st.components.v1.html(html_code, height=height, scrolling=False)


def render_ego_network(coach_name, compact=False):
    """
    Render ego network for a specific coach
    Used on coach detail pages
    """
    st.subheader(f"🕸️ {coach_name}'s Network")

    # Load full network
    network = load_network("full")

    # Get ego network
    ego = get_ego_network(coach_name, network, depth=1)

    if ego['total_connections'] == 0:
        st.info(f"No connections found for {coach_name}")
        return

    # Show stats
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Direct Connections", ego['total_connections'])

    with col2:
        # Count by type
        types = {}
        for node in ego['nodes']:
            if node['name'] != coach_name:
                node_type = node.get('type', 'unclassified')
                types[node_type] = types.get(node_type, 0) + 1

        most_common = max(types.items(), key=lambda x: x[1]) if types else ("N/A", 0)
        st.metric("Most Common", most_common[0].replace('_', ' ').title(),
                  delta=f"{most_common[1]} connections")

    with col3:
        # Average strength
        if ego['edges']:
            avg_strength = sum(e.get('strength', 1) for e in ego['edges']) / len(ego['edges'])
            st.metric("Avg Connection Strength", f"{avg_strength:.1f}")

    # Render visualization
    height = 400 if compact else 600

    if len(ego['nodes']) > 50:
        st.warning(f"⚠️ Large network ({len(ego['nodes'])} nodes). Showing first 50 connections.")
        ego['nodes'] = ego['nodes'][:50]
        ego['edges'] = [e for e in ego['edges']
                        if e['source'] in [n['name'] for n in ego['nodes']]
                        and e['target'] in [n['name'] for n in ego['nodes']]]

    render_d3_network(ego, height=height, highlight_node=coach_name)

    # Link to full network
    if st.button("🔍 Explore Full Network", key=f"explore_{coach_name}"):
        st.session_state['network_highlight'] = coach_name
        st.switch_page("pages/3_🕸️_Network.py")  # Will create this page


if __name__ == "__main__":
    # Test the component
    st.title("Network Component Test")
    render_full_network_tab()
