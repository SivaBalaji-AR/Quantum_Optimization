import math
import numpy as np
import networkx as nx
from typing import Dict, Any, List
from db import get_db

# -------------------------
# Utilities
# -------------------------
def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6371.0
    lat1, lng1, lat2, lng2 = map(math.radians, [lat1, lng1, lat2, lng2])
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

# -------------------------
# Graph build helpers
# -------------------------
async def build_graph_from_nodes() -> nx.Graph:
    db = await get_db()
    nodes_cursor = db.nodes.find()
    nodes = await nodes_cursor.to_list(1000)
    G = nx.Graph()
    for node in nodes:
        G.add_node(node['id'], name=node['name'], lat=node['lat'], lng=node['lng'])

    node_list = list(G.nodes(data=True))
    for i, (n1, d1) in enumerate(node_list):
        for j, (n2, d2) in enumerate(node_list):
            if i < j:
                dist = haversine_km(d1['lat'], d1['lng'], d2['lat'], d2['lng'])
                G.add_edge(n1, n2, weight=dist)
    return G

async def graph_visualization() -> Dict[str, List[Dict[str, Any]]]:
    db = await get_db()
    nodes = await db.nodes.find().to_list(1000)

    vis_nodes = [
        {"id": n['id'], "name": n['name'], "lat": n['lat'], "lng": n['lng']} for n in nodes
    ]

    vis_edges = []
    for i, n1 in enumerate(vis_nodes):
        for j, n2 in enumerate(vis_nodes):
            if i < j:
                d = haversine_km(n1['lat'], n1['lng'], n2['lat'], n2['lng'])
                vis_edges.append({"from": n1['id'], "to": n2['id'], "weight": round(d, 2)})

    return {"nodes": vis_nodes, "edges": vis_edges}

# -------------------------
# Algorithms
# -------------------------
class QuantumRouteOptimizer:
    """Your original 'quantum-inspired' path selector + Dijkstra fallback."""
    def solve_qaoa(self, graph: nx.Graph, start: str, end: str, p: int = 1):
        try:
            paths = list(nx.all_simple_paths(graph, start, end, cutoff=5))
            if not paths:
                return [], float('inf')

            path_data = []
            for path in paths:
                distance = sum(graph[path[i]][path[i+1]]['weight'] for i in range(len(path)-1))
                path_data.append((path, distance))

            min_d = min(d for _, d in path_data)
            max_d = max(d for _, d in path_data)
            if min_d == max_d:
                idx = np.random.randint(len(path_data))
                return path_data[idx]

            probs = []
            for _, dist in path_data:
                norm = (dist - min_d) / (max_d - min_d)
                probs.append(np.exp(-2 * norm))
            total = sum(probs)
            probs = [p / total for p in probs]

            idx = np.random.choice(len(path_data), p=probs)
            return path_data[idx]
        except Exception:
            return self.solve_dijkstra(graph, start, end)

    def solve_dijkstra(self, graph: nx.Graph, start: str, end: str):
        try:
            path = nx.shortest_path(graph, start, end, weight='weight')
            dist = nx.shortest_path_length(graph, start, end, weight='weight')
            return path, dist
        except nx.NetworkXNoPath:
            return [], float('inf')

optimizer = QuantumRouteOptimizer()
