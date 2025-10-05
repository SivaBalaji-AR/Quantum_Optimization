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
    print(f"Received raw request body: {request.dict()}")
    graph = await build_graph_from_nodes(node_ids=request.stops)

    if len(graph.nodes) != len(request.stops):
        raise HTTPException(status_code=404, detail="One or more selected nodes were not found in the database.")

    # Check that all stops exist
    for stop in request.stops:
        if stop not in graph.nodes:
            raise HTTPException(status_code=404, detail=f"Node {stop} not found")

    t0 = time.time()
    algo = request.algorithm.lower()

    if algo == "dijkstra":
        path, distance = optimizer.solve_multi_stop(graph, request.stops, "dijkstra")
    elif algo == "qaoa":
        if len(request.stops) > 5:
            raise HTTPException(status_code=400, detail="QAOA TSP is too slow for more than 5 stops.")
        if len(request.stops) < 3:
            raise HTTPException(status_code=400, detail="QAOA TSP requires at least 3 stops.")
        path, distance = optimizer.solve_multi_stop(graph, request.stops, "qaoa")
    else:
        raise HTTPException(status_code=400, detail="Invalid algorithm. Use 'dijkstra' or 'qaoa'")

    exec_time = time.time() - t0
    if not path:
        raise HTTPException(status_code=404, detail="No path found between stops")

    db = await get_db()
    result = RouteResult(
        algorithm=request.algorithm,
        start_node_id=request.stops[0],
        end_node_id=request.stops[-1],
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
    {"name": "Gandhipuram Central Bus Stand", "lat": 11.0183, "lng": 76.9685},
    {"name": "Coimbatore Junction Railway Station", "lat": 10.9945, "lng": 76.9654},
    {"name": "Annapoorna Restaurant, RS Puram", "lat": 11.0072, "lng": 76.9515},
    {"name": "Warehouse, SIDCO Industrial Estate", "lat": 10.9580, "lng": 76.9298},
    {"name": "Distribution Center, Peelamedu", "lat": 11.0305, "lng": 77.0301},
    {"name": "Customer 1, Saibaba Colony", "lat": 11.0286, "lng": 76.9500},
    {"name": "Customer 2, Race Course Road", "lat": 11.0008, "lng": 76.9792},
    {"name": "Textile Mill, Avinashi Road", "lat": 11.0451, "lng": 77.0655},
    {"name": "BrookeFields Mall", "lat": 11.0084, "lng": 76.9598},
    {"name": "Tidel Park Coimbatore", "lat": 11.0238, "lng": 77.0294},
]

    created = []
    for data in sample_nodes:
        node = Node(**data)
        await db.nodes.insert_one(node.dict())
        created.append(node.dict())

    return {"message": f"Created {len(created)} sample nodes", "nodes": created}
