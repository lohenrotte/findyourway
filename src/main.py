import osmnx as ox
import networkx as nx
import random
import math
from collections import defaultdict

def preprocess_graph(G, mode):
    # Remove short edges
    edges_to_remove = [
        (u, v, k) for u, v, k, d in G.edges(keys=True, data=True)
        if d.get("length", 0) < 7
    ]
    G.remove_edges_from(edges_to_remove)

    if mode == "walk":
        # Remove problematic pedestrian edge types
        bad_tags = {"steps", "corridor", "platform"}
        edges_to_remove = []
        for u, v, k, d in G.edges(keys=True, data=True):
            highway = d.get("highway")
            if isinstance(highway, list):
                if any(tag in bad_tags for tag in highway):
                    edges_to_remove.append((u, v, k))
            elif highway in bad_tags:
                edges_to_remove.append((u, v, k))
        G.remove_edges_from(edges_to_remove)

    return G



def score_path(path, dist, target_dist):
    unique_nodes = len(set(path))
    repeated = len(path) - unique_nodes

    # Count short-loop returns (loop within 20 steps)
    subloops = 0
    last_seen = {}
    for i, node in enumerate(path):
        if node in last_seen and i - last_seen[node] < 20:
            subloops += 1
        last_seen[node] = i

    return (
        -abs(dist - target_dist)              # closeness to target
        + unique_nodes * 10                   # reward diversity
        - repeated * 20                       # penalize revisits
        - subloops * 25                       # penalize tight loops
    )

def is_close_to_start(G, node, start, threshold_m=50):
    y1, x1 = G.nodes[node]['y'], G.nodes[node]['x']
    y0, x0 = G.nodes[start]['y'], G.nodes[start]['x']
    dist = ox.distance.great_circle(y1, x1, y0, x0)
    return dist < threshold_m



def random_loop(G, start, target_dist=5000, margin=0.2, max_steps=120, attempt_id=0):
    path = [start]
    dist = 0
    steps = 0
    node = start
    visited_edges = set()
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
            visited_edges.add((node, neighbor))
            node = neighbor
            node_visits[neighbor] += 1
            steps += 1
            moved = True
            break

        if not moved:
            break

        if (1 - margin) * target_dist <= dist <= (1 + margin) * target_dist:
            if is_close_to_start(G, node, start):
                score = score_path(path, dist, target_dist)
                print(f"    ✅ Loop found: {round(dist)}m, Steps: {steps}, Score: {score}")
                return path, dist, score

    return None, 0, -math.inf

def find_top_loops(G, start, target_dist=5000, margin=0.2, attempts=1000, top_k=3):
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
    network_type = "bike"  # or "bike"
    target_distance = 10000  # meters

    print(f"📍 Geocoding: {address}")
    location = ox.geocode(address)

    print(f"🛰️  Downloading {network_type} graph...")
    G = ox.graph_from_point(location, dist=1000, network_type=network_type, simplify=True)
    G = ox.project_graph(G)
    G = preprocess_graph(G, network_type)

    start = ox.distance.nearest_nodes(G, X=location[1], Y=location[0])
    print(f"📌 Starting from node: {start}")

    top_loops = find_top_loops(G, start, target_dist=target_distance, margin=0.05, attempts=200000, top_k=3)

    if not top_loops:
        print("❌ No valid loops found.")
    else:
        for idx, (score, path, dist) in enumerate(top_loops, 1):
            print(f"\n🏁 Loop {idx}: Length {round(dist)}m, Steps {len(path)}, Score {score}")
            ox.plot_graph_route(G, path, route_linewidth=3, bgcolor='white')

if __name__ == "__main__":
    main()
