from pydantic import BaseModel, Field
from typing import List, Dict
from datetime import datetime
import uuid

class Node(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    lat: float
    lng: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class NodeCreate(BaseModel):
    name: str
    lat: float
    lng: float

class RouteRequest(BaseModel):
    start_node_id: str
    end_node_id: str
    algorithm: str  # "dijkstra" or "qaoa"

class RouteResult(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    algorithm: str
    start_node_id: str
    end_node_id: str
    path: List[str]
    distance: float
    execution_time: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class GraphVisualization(BaseModel):
    nodes: List[Dict]
    edges: List[Dict]
