#!/usr/bin/env python3
"""
Build Full "Wer kennt wen" Network from Teammate Data

Creates unified network with:
- Coaches as nodes
- Players as nodes
- Coach-Coach edges (existing)
- Coach-Player edges (from teammate data)
- Player-Player edges (teammates of teammates)

Output: Complete social network graph
"""

import json
from pathlib import Path
from collections import defaultdict

# Paths
TEAMMATES_FILE = Path("data/teammates_bulk.json")
EXISTING_NETWORK = Path("data/network_graph_with_teammates.json")
OUTPUT_NODES = Path("data/full_network_nodes.json")
OUTPUT_EDGES = Path("data/full_network_edges.json")

def build_full_network():
    """Build complete network from teammate data."""
    print("\n" + "="*60)
    print("Building Full 'Wer kennt wen' Network")
    print("="*60 + "\n")

    # Load teammate data
    print("📊 Loading teammate data...")
    teammates_data = json.loads(TEAMMATES_FILE.read_text())
    coaches_with_teammates = teammates_data.get("coaches", [])
    print(f"   ✓ Loaded {len(coaches_with_teammates)} coaches with teammate data")
    print(f"   ✓ Total teammates found: {teammates_data.get('total_teammates_found', 0):,}")

    # Build nodes
    print("\n👥 Building node list...")
    nodes = {}

    # Add coaches as nodes
    for coach_data in coaches_with_teammates:
        coach_name = coach_data.get("name")
        if not coach_name:
            continue

        nodes[coach_name] = {
            "name": coach_name,
            "type": "coach",
            "url": coach_data.get("url", ""),
            "player_id": coach_data.get("player_id", ""),
            "has_playing_career": True
        }

    print(f"   ✓ Added {len(nodes)} coach nodes")

    # Add players as nodes (from all teammates)
    player_count = 0
    for coach_data in coaches_with_teammates:
        for teammate in coach_data.get("teammates", []):
            player_name = teammate.get("name")
            if not player_name or player_name in nodes:
                continue

            nodes[player_name] = {
                "name": player_name,
                "type": "player",
                "position": teammate.get("position", ""),
                "url": teammate.get("url", "")
            }
            player_count += 1

    print(f"   ✓ Added {player_count} player nodes")
    print(f"   ✓ Total nodes: {len(nodes):,}")

    # Build edges
    print("\n🔗 Building edges...")
    edges = []
    edge_set = set()  # To avoid duplicates

    # Coach-Player edges (from teammate data)
    coach_player_edges = 0
    for coach_data in coaches_with_teammates:
        coach_name = coach_data.get("name")
        if not coach_name:
            continue

        for teammate in coach_data.get("teammates", []):
            player_name = teammate.get("name")
            if not player_name:
                continue

            # Create edge key (alphabetically sorted to avoid duplicates)
            edge_key = tuple(sorted([coach_name, player_name]))

            if edge_key in edge_set:
                continue

            edge_set.add(edge_key)

            edges.append({
                "source": coach_name,
                "target": player_name,
                "type": "played_together",
                "shared_matches": teammate.get("shared_matches", 0),
                "teams_together": teammate.get("teams_together", 0),
                "total_minutes": teammate.get("total_minutes", 0),
                "strength": teammate.get("shared_matches", 0) / 10.0  # Normalize strength
            })
            coach_player_edges += 1

    print(f"   ✓ Created {coach_player_edges:,} coach-player edges")

    # Player-Player edges (transitive through coaches)
    print("\n🔄 Building player-player connections (teammates of teammates)...")

    # Group players by coaches they played with
    player_to_coaches = defaultdict(set)
    for coach_data in coaches_with_teammates:
        coach_name = coach_data.get("name")
        for teammate in coach_data.get("teammates", []):
            player_name = teammate.get("name")
            if player_name:
                player_to_coaches[player_name].add(coach_name)

    # Find players who share coaches (transitive teammates)
    player_player_edges = 0
    players = [name for name, node in nodes.items() if node["type"] == "player"]

    print(f"   → Processing {len(players):,} players...")

    for i, player_a in enumerate(players):
        if i % 1000 == 0 and i > 0:
            print(f"      Processed {i:,}/{len(players):,} players...")

        coaches_a = player_to_coaches.get(player_a, set())
        if not coaches_a:
            continue

        for player_b in players[i+1:]:  # Only check pairs once
            coaches_b = player_to_coaches.get(player_b, set())

            # If they share at least one coach, they're connected
            shared_coaches = coaches_a & coaches_b

            if shared_coaches:
                edge_key = tuple(sorted([player_a, player_b]))

                if edge_key in edge_set:
                    continue

                edge_set.add(edge_key)

                edges.append({
                    "source": player_a,
                    "target": player_b,
                    "type": "teammates",
                    "shared_coaches": len(shared_coaches),
                    "strength": len(shared_coaches) * 2  # Weight by number of shared coaches
                })
                player_player_edges += 1

    print(f"   ✓ Created {player_player_edges:,} player-player edges")

    # Load existing coach-coach edges
    print("\n📥 Loading existing coach-coach edges...")
    if EXISTING_NETWORK.exists():
        existing = json.loads(EXISTING_NETWORK.read_text())
        existing_edges = existing.get("edges", [])

        # Add coach-coach edges that aren't already in edge_set
        coach_coach_added = 0
        for edge in existing_edges:
            source = edge.get("source")
            target = edge.get("target")

            if not source or not target:
                continue

            edge_key = tuple(sorted([source, target]))

            if edge_key not in edge_set:
                edge_set.add(edge_key)
                edges.append(edge)
                coach_coach_added += 1

        print(f"   ✓ Added {coach_coach_added:,} existing coach-coach edges")
    else:
        print(f"   ⚠️  No existing network found, skipping coach-coach edges")

    # Save nodes and edges
    print("\n💾 Saving network data...")

    nodes_list = list(nodes.values())
    OUTPUT_NODES.write_text(json.dumps(nodes_list, indent=2))
    print(f"   ✓ Saved {len(nodes_list):,} nodes to {OUTPUT_NODES}")

    OUTPUT_EDGES.write_text(json.dumps(edges, indent=2))
    print(f"   ✓ Saved {len(edges):,} edges to {OUTPUT_EDGES}")

    # Statistics
    print("\n" + "="*60)
    print("NETWORK BUILD COMPLETE")
    print("="*60)

    coach_nodes = [n for n in nodes.values() if n["type"] == "coach"]
    player_nodes = [n for n in nodes.values() if n["type"] == "player"]

    print(f"\n📊 Network Statistics:")
    print(f"   • Total Nodes: {len(nodes):,}")
    print(f"     - Coaches: {len(coach_nodes):,}")
    print(f"     - Players: {len(player_nodes):,}")

    print(f"\n   • Total Edges: {len(edges):,}")
    print(f"     - Coach-Player: {coach_player_edges:,}")
    print(f"     - Player-Player: {player_player_edges:,}")
    print(f"     - Coach-Coach: {len(edges) - coach_player_edges - player_player_edges:,}")

    # Network density
    max_possible_edges = len(nodes) * (len(nodes) - 1) / 2
    density = len(edges) / max_possible_edges * 100 if max_possible_edges > 0 else 0

    print(f"\n   • Network Density: {density:.3f}%")
    print(f"   • Avg Connections per Node: {len(edges) * 2 / len(nodes):.1f}")

    # Top connected nodes
    print(f"\n🏆 Top 10 Most Connected Nodes:")
    node_connections = defaultdict(int)
    for edge in edges:
        node_connections[edge["source"]] += 1
        node_connections[edge["target"]] += 1

    top_nodes = sorted(node_connections.items(), key=lambda x: x[1], reverse=True)[:10]
    for i, (name, count) in enumerate(top_nodes, 1):
        node_type = nodes[name]["type"]
        print(f"   {i:2}. {name} ({node_type}): {count:,} connections")

    print("\n" + "="*60 + "\n")

    return nodes_list, edges

if __name__ == "__main__":
    nodes, edges = build_full_network()
    print(f"✅ Built network with {len(nodes):,} nodes and {len(edges):,} edges!")
