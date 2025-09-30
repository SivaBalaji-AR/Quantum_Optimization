import math
import numpy as np
import networkx as nx
from typing import Dict, Any, List, Tuple
from db import get_db

from qiskit_aer import Aer
from qiskit_algorithms import QAOA   # ✅ comes from qiskit-algorithms
from qiskit_algorithms.optimizers import COBYLA
from qiskit_optimization import QuadraticProgram
from qiskit_optimization.algorithms import MinimumEigenOptimizer


# instead of algorithm_globals
np.random.seed(42)

# -------------------------
# Utilities
# -------------------------
def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Compute distance between two coordinates (km) using Haversine."""
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
    """Load all nodes from DB and construct a weighted complete graph."""
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
    """Prepare graph nodes and edges for frontend visualization."""
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
    """Qiskit-based QAOA for shortest path + Dijkstra fallback."""

    def solve_qaoa(self, graph: nx.Graph, start: str, end: str, p: int = 1) -> Tuple[List[str], float]:
        """
        Solve shortest path using a real QAOA formulation in Qiskit.
        Note: simplified QUBO (does not enforce strict flow constraints).
        """
        try:
            # Step 1: Build QUBO
            qp = QuadraticProgram()

            edges = list(graph.edges(data=True))
            edge_vars = []
            for idx, (u, v, data) in enumerate(edges):
                var_name = f"x_{u}_{v}"
                qp.binary_var(var_name)
                edge_vars.append((var_name, u, v, data["weight"]))

            # Objective: minimize total distance
            linear = {var: w for var, _, _, w in edge_vars}
            qp.minimize(linear=linear)

            # Step 2: Run QAOA
            algorithm_globals.random_seed = 42
            backend = Aer.get_backend("aer_simulator_statevector")

            qaoa = QAOA(optimizer=COBYLA(maxiter=50), reps=p, quantum_instance=backend)
            optimizer = MinimumEigenOptimizer(qaoa)

            result = optimizer.solve(qp)

            # Step 3: Extract chosen edges
            chosen_edges = [e for e in edge_vars if result.variables_dict.get(e[0], 0) > 0.5]

            if not chosen_edges:
                return [], float("inf")

            # Convert chosen edges into a path (greedy reconstruction)
            nodes_path = [start]
            current = start
            visited = {start}

            while current != end:
                next_edges = [e for e in chosen_edges if e[1] == current or e[2] == current]
                if not next_edges:
                    break
                _, u, v, w = next_edges[0]
                nxt = v if u == current else u
                if nxt in visited:
                    break
                nodes_path.append(nxt)
                visited.add(nxt)
                current = nxt

            distance = sum(e[3] for e in chosen_edges)
            return nodes_path, distance

        except Exception as e:
            print("QAOA error:", e)
            return self.solve_dijkstra(graph, start, end)

    def solve_dijkstra(self, graph: nx.Graph, start: str, end: str) -> Tuple[List[str], float]:
        """Classical shortest path via Dijkstra."""
        try:
            path = nx.shortest_path(graph, start, end, weight="weight")
            dist = nx.shortest_path_length(graph, start, end, weight="weight")
            return path, dist
        except nx.NetworkXNoPath:
            return [], float("inf")

    def solve_multi_stop(self, graph: nx.Graph, stops: List[str], algorithm: str = "dijkstra") -> Tuple[List[str], float]:
        """
        Compute route across multiple stops in the given order.
        e.g. [A, B, C, D] -> shortest path A→B + B→C + C→D.
        """
        if len(stops) < 2:
            return [], 0.0

        full_path: List[str] = []
        total_distance: float = 0.0

        for i in range(len(stops) - 1):
            s, t = stops[i], stops[i+1]
            if algorithm == "dijkstra":
                path, dist = self.solve_dijkstra(graph, s, t)
            else:
                path, dist = self.solve_qaoa(graph, s, t)

            if not path:
                return [], float("inf")

            # avoid duplicate nodes at segment junction
            if full_path:
                full_path.extend(path[1:])
            else:
                full_path.extend(path)

            total_distance += dist

        return full_path, total_distance


# Global optimizer instance
optimizer = QuantumRouteOptimizer()
