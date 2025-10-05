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
from qiskit.primitives import Sampler

from qiskit_optimization.applications import Tsp 


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
async def build_graph_from_nodes(node_ids: List[str]) -> nx.Graph:
    """
    Load a specific list of nodes from DB and construct a weighted complete graph.
    """
    print(f"\n--- Building graph for {len(node_ids)} selected nodes ---")
    db = await get_db()
    
    # Query MongoDB to find all documents where the 'id' is in our list
    query = {"id": {"$in": node_ids}}
    nodes_cursor = db.nodes.find(query)
    nodes = await nodes_cursor.to_list(len(node_ids))

    print(f"1. Fetched {len(nodes)} matching nodes from MongoDB.")

    G = nx.Graph()
    for node in nodes:
        G.add_node(node['id'], name=node['name'], lat=node['lat'], lng=node['lng'])

    print(f"2. Added {G.number_of_nodes()} nodes to the graph object.")

    # This part remains the same, building a complete graph from the nodes we found
    print("3. Creating edges...")
    node_list = list(G.nodes(data=True))
    for i, (n1, d1) in enumerate(node_list):
        for j, (n2, d2) in enumerate(node_list):
            if i < j:
                dist = haversine_km(d1['lat'], d1['lng'], d2['lat'], d2['lng'])
                G.add_edge(n1, n2, weight=dist)

    print("--- Graph Ready ---\n")
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
    """
    Solves routing problems using classical and quantum algorithms.
    Includes Dijkstra for A-to-B paths and QAOA for the Traveling Salesperson Problem (TSP).
    """

    def solve_tsp_qaoa(self, graph: nx.Graph, p: int = 1) -> Tuple[List[str], float]:
        """
        Solves the Traveling Salesperson Problem (TSP) using QAOA.
        Finds the optimal tour that visits every node in the graph.
        """
        # Pre-check: TSP needs at least 2 nodes to be meaningful.
        if graph.number_of_nodes() < 2:
            return [], 0.0
            
        try:
            # 1. IMPORTANT: Relabel the graph nodes to integers (0, 1, 2...)
            # The Tsp class requires an integer-labeled graph.
            # We store the `mapping` to convert the result back later.
            int_graph = nx.convert_node_labels_to_integers(graph, label_attribute='original_label')
            
            # Create an inverse mapping to get original IDs from integer labels
            inverse_mapping = nx.get_node_attributes(int_graph, 'original_label')

            # 2. Create a TSP instance from the integer-labeled graph
            tsp = Tsp(int_graph)
            qp = tsp.to_quadratic_program()

            # 3. Set up and run the QAOA solver
            sampler = Sampler(options={"seed": 42})
            qaoa = QAOA(sampler=sampler, optimizer=COBYLA(maxiter=100), reps=p)
            optimizer = MinimumEigenOptimizer(qaoa)
            result = optimizer.solve(qp)

            # 4. Interpret the result (path will be a list of integers)
            path = tsp.interpret(result)

            adj_matrix = nx.to_numpy_array(int_graph)
        
            distance = Tsp.tsp_value(path, adj_matrix)
            
            # 5. Use the INVERSE mapping to convert the integer path back to original node IDs
            path_ids = [inverse_mapping[i] for i in path]
            
            # To make it a round trip, add the starting node to the end
            path_ids.append(path_ids[0])
            
            return path_ids, distance

        except Exception as e:
            print(f"QAOA TSP Error: {e}")
            return [], float("inf")

    def solve_dijkstra(self, graph: nx.Graph, start: str, end: str) -> Tuple[List[str], float]:
        """Classical shortest path via Dijkstra."""
        try:
            path = nx.shortest_path(graph, source=start, target=end, weight="weight")
            dist = nx.shortest_path_length(graph, source=start, target=end, weight="weight")
            return path, dist
        except nx.NetworkXNoPath:
            return [], float("inf")

    def solve_multi_stop(self, graph: nx.Graph, stops: List[str], algorithm: str) -> Tuple[List[str], float]:
        """
        Computes a route across multiple stops.
        - 'dijkstra': Solves in the given order [A->B, B->C, ...].
        - 'qaoa-tsp': Solves the TSP to find the optimal order of all nodes in the graph.
        """
        algorithm = algorithm.lower()

        if algorithm == "qaoa":
            # The 'stops' list is ignored for TSP, as it solves for all nodes in the graph.
            return self.solve_tsp_qaoa(graph)

        elif algorithm == "dijkstra":
            if len(stops) < 2:
                return [], 0.0
            
            full_path: List[str] = []
            total_distance: float = 0.0

            for i in range(len(stops) - 1):
                s, t = stops[i], stops[i+1]
                path, dist = self.solve_dijkstra(graph, s, t)
                if not path:
                    return [], float("inf")
                
                if full_path:
                    full_path.extend(path[1:])
                else:
                    full_path.extend(path)
                total_distance += dist

            return full_path, total_distance
            
        else:
            raise ValueError("Invalid algorithm specified.")


# Global optimizer instance
optimizer = QuantumRouteOptimizer()