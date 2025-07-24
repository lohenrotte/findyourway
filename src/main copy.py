# Final refined walking loop generator
import osmnx as ox
import networkx as nx
import random
import math
from collections import defaultdict

def preprocess_walk_graph(G):
    """
    Clean the walking graph to improve loop generation by:
    - Removing problematic or impractical pedestrian edge types
    - Filtering out extremely short edges that create noise
    """
    edges_to_remove = []

    # Edge types not suitable for pleasant walking loops
    bad_highway_tags = {
        "steps", "corridor", "escalator", "elevator", "platform",
        "raceway", "proposed", "construction", "service", "footway"
    }

    for u, v, k, d in G.edges(keys=True, data=True):
        highway = d.get("highway", None)
        if isinstance(highway, list):
            if any(tag in bad_highway_tags for tag in highway):
                edges_to_remove.append((u, v, k))
        elif highway in bad_highway_tags:
            edges_to_remove.append((u, v, k))

        # Remove short edges that add noise
        if d.get("length", 0) < 5:
            edges_to_remove.append((u, v, k))

    G.remove_edges_from(edges_to_remove)
    G.remove_nodes_from(list(nx.isolates(G)))

    return G

def score_path(path, dist, target_dist, visited_edges):
    unique_nodes = len(set(path))
    repeated_nodes = len(path) - unique_nodes

    # Detect short subloops (returning to same node within 30 steps)
    subloops = 0
    last_seen = {}
    for i, node in enumerate(path):
        if node in last_seen and i - last_seen[node] < 30:
            subloops += 1
        last_seen[node] = i

    # Count edge repetition
    repeated_edges = sum(1 for e, count in visited_edges.items() if count > 1)

    return (
        -abs(dist - target_dist)
        + unique_nodes * 10
        - repeated_nodes * 40
        - subloops * 30
        - repeated_edges * 20
    )


def is_close_to_start(G, node, start, threshold_m=100):
    y1, x1 = G.nodes[node]['y'], G.nodes[node]['x']
    y0, x0 = G.nodes[start]['y'], G.nodes[start]['x']
    dist = ox.distance.great_circle(y1, x1, y0, x0)
    return dist < threshold_m

def random_loop(G, start, target_dist=10000, margin=0.05, max_steps=200, attempt_id=0):
    path = [start]
    dist = 0
    steps = 0
    node = start
    visited_edges = defaultdict(int)
    node_visits = defaultdict(int)

    while steps < max_steps:
        neighbors = list(G[node])
        random.shuffle(neighbors)

        moved = False
        for neighbor in neighbors:
            if len(path) >= 2 and neighbor == path[-2]:
                continue
            if node_visits[neighbor] >= 3:
                continue
            try:
                edge_data = list(G.get_edge_data(node, neighbor).values())[0]
                edge_len = edge_data.get("length", 1)
            except:
                continue

            path.append(neighbor)
            dist += edge_len
            edge_key = tuple(sorted((node, neighbor)))
            visited_edges[edge_key] += 1
            node = neighbor
            node_visits[neighbor] += 1
            steps += 1
            moved = True
            break

        if not moved:
            break

        if dist >= (1 - margin) * target_dist and is_close_to_start(G, node, start):
            score = score_path(path, dist, target_dist, visited_edges)
            print(f"    ✅ Loop found: {round(dist)}m, Steps: {steps}, Score: {score}")
            return path, dist, score

    return None, 0, -math.inf

def find_top_loops(G, start, target_dist=10000, margin=0.05, attempts=300000, top_k=3):
    results = []
    seen_hashes = set()
    print(f"🔍 Looking for ~{target_dist}m loops (±{int(margin*100)}%), max {attempts} attempts...")
    for i in range(1, attempts + 1):
        path, dist, score = random_loop(G, start, target_dist, margin, attempt_id=i)
        if path:
            path_hash = tuple(sorted(set(path)))
            if path_hash not in seen_hashes:
                seen_hashes.add(path_hash)
                results.append((score, path, dist))
    results.sort(reverse=True)
    return results[:top_k]

def main():
    address = "Rue Defacqz, Brussels, Belgium"
    network_type = "walk"
    target_distance = 5000  # meters

    print(f"📍 Geocoding: {address}")
    location = ox.geocode(address)

    radius = 1000 if network_type == "walk" else 1000
    print(f"🛰️  Downloading {network_type} graph with radius {radius}m...")
    G = ox.graph_from_point(location, dist=radius, network_type=network_type, simplify=True)
    G = ox.project_graph(G)
    G = preprocess_walk_graph(G)

    start = ox.distance.nearest_nodes(G, X=location[1], Y=location[0])
    print(f"📌 Starting from node: {start}")

    top_loops = find_top_loops(G, start, target_dist=target_distance, margin=0.05, attempts=300000, top_k=3)

    if not top_loops:
        print("❌ No valid loops found.")
    else:
        for idx, (score, path, dist) in enumerate(top_loops, 1):
            print(f"\n🏁 Loop {idx}: Length {round(dist)}m, Steps {len(path)}, Score {score}")
            ox.plot_graph_route(G, path, route_linewidth=3, bgcolor='white')

if __name__ == "__main__":
    main()
