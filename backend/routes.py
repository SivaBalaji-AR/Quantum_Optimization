from fastapi import APIRouter, HTTPException
from typing import List
import time

from models import Node, NodeCreate, RouteRequest, RouteResult
from db import get_db
from core import optimizer, build_graph_from_nodes, graph_visualization

router = APIRouter()

@router.get("/")
async def root():
    return {"message": "Quantum Route Optimization API"}

# --------- Nodes ----------
@router.post("/nodes", response_model=Node)
async def create_node(input: NodeCreate):
    db = await get_db()
    node = Node(**input.dict())
    await db.nodes.insert_one(node.dict())
    return node

@router.get("/nodes", response_model=List[Node])
async def get_nodes():
    db = await get_db()
    nodes = await db.nodes.find().to_list(1000)
    return [Node(**n) for n in nodes]

@router.delete("/nodes/{node_id}")
async def delete_node(node_id: str):
    db = await get_db()
    result = await db.nodes.delete_one({"id": node_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Node not found")
    return {"message": "Node deleted successfully"}

# --------- Routing ----------
@router.post("/route/optimize", response_model=RouteResult)
async def optimize_route(request: RouteRequest):
    graph = await build_graph_from_nodes()
    if request.start_node_id not in graph.nodes or request.end_node_id not in graph.nodes:
        raise HTTPException(status_code=404, detail="Start or end node not found")

    t0 = time.time()
    algo = request.algorithm.lower()
    if algo == "dijkstra":
        path, distance = optimizer.solve_dijkstra(graph, request.start_node_id, request.end_node_id)
    elif algo == "qaoa":
        path, distance = optimizer.solve_qaoa(graph, request.start_node_id, request.end_node_id)
    else:
        raise HTTPException(status_code=400, detail="Invalid algorithm. Use 'dijkstra' or 'qaoa'")

    exec_time = time.time() - t0
    if not path:
        raise HTTPException(status_code=404, detail="No path found between nodes")

    db = await get_db()
    result = RouteResult(
        algorithm=request.algorithm,
        start_node_id=request.start_node_id,
        end_node_id=request.end_node_id,
        path=path,
        distance=distance,
        execution_time=exec_time,
    )
    await db.route_results.insert_one(result.dict())
    return result

@router.get("/route/results", response_model=List[RouteResult])
async def get_route_results():
    db = await get_db()
    results = await db.route_results.find().to_list(1000)
    return [RouteResult(**r) for r in results]

# --------- Graph ----------
@router.get("/graph/visualization")
async def get_graph_visualization():
    return await graph_visualization()

# --------- Demo ----------
@router.post("/demo/create-sample-nodes")
async def create_sample_nodes():
    db = await get_db()
    await db.nodes.delete_many({})

    sample_nodes = [
        {"name": "Restaurant A", "lat": 40.7128, "lng": -74.0060},  # NYC
        {"name": "Restaurant B", "lat": 40.7589, "lng": -73.9851},  # Times Sq
        {"name": "Restaurant C", "lat": 40.6892, "lng": -74.0445},  # Jersey City
        {"name": "Customer 1",  "lat": 40.7505, "lng": -73.9934},
        {"name": "Customer 2",  "lat": 40.7282, "lng": -74.0776},   # Hoboken
        {"name": "Warehouse",   "lat": 40.7831, "lng": -73.9712},   # UWS
        {"name": "Distribution Center", "lat": 40.6782, "lng": -73.9442}, # Brooklyn
        {"name": "Restaurant D","lat": 40.7614, "lng": -73.9776},   # Lincoln Ctr
        {"name": "Customer 3",  "lat": 40.7400, "lng": -73.9897},   # Chelsea
        {"name": "Customer 4",  "lat": 40.6928, "lng": -73.9903},   # Brooklyn Heights
    ]

    created = []
    for data in sample_nodes:
        node = Node(**data)
        await db.nodes.insert_one(node.dict())
        created.append(node.dict())

    return {"message": f"Created {len(created)} sample nodes", "nodes": created}
