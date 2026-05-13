from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List

from internal.graph.nav_graph import nav_graph
from internal.graph.pathfinder import astar, get_path_distance, get_path_instructions

router = APIRouter(prefix="/navigation", tags=["navigation"])


# ── Request / Response schemas ──────────────────────────────────────────────

class NavigateRequest(BaseModel):
    start_id: str
    goal_id: str

class NodeInfo(BaseModel):
    id: str
    label: str
    x: float
    y: float

class NavigateResponse(BaseModel):
    path: List[str]
    labels: List[str]
    instructions: List[str]
    total_distance_metres: float
    step_count: int


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/health")
def health_check():
    """Confirm navigation router is live and graph is loaded."""
    return {
        "status": "ok",
        "graph": nav_graph.get_stats()
    }


@router.get("/nodes", response_model=List[NodeInfo])
def get_all_nodes():
    """Return every node in the current map."""
    return [
        NodeInfo(id=n.id, label=n.label, x=n.x, y=n.y)
        for n in nav_graph.all_nodes()
    ]


@router.get("/nodes/{node_id}", response_model=NodeInfo)
def get_node(node_id: str):
    """Return a single node by ID."""
    node = nav_graph.get_node(node_id)
    if not node:
        raise HTTPException(
            status_code=404,
            detail=f"Node '{node_id}' not found"
        )
    return NodeInfo(id=node.id, label=node.label, x=node.x, y=node.y)


@router.post("/navigate", response_model=NavigateResponse)
def navigate(req: NavigateRequest):
    """Find the shortest path between two nodes using A*."""
    if not nav_graph.node_exists(req.start_id):
        raise HTTPException(
            status_code=404,
            detail=f"Start node '{req.start_id}' not found"
        )
    if not nav_graph.node_exists(req.goal_id):
        raise HTTPException(
            status_code=404,
            detail=f"Goal node '{req.goal_id}' not found"
        )

    path = astar(nav_graph, req.start_id, req.goal_id)

    if path is None:
        raise HTTPException(
            status_code=404,
            detail="No path found between these nodes"
        )

    return NavigateResponse(
        path=path,
        labels=[nav_graph.nodes[nid].label for nid in path],
        instructions=get_path_instructions(nav_graph, path),
        total_distance_metres=get_path_distance(nav_graph, path),
        step_count=len(path)
    )


@router.delete("/nodes/{node_id}")
def remove_node(node_id: str):
    """Remove a node and all its edges (e.g. mark an area as blocked)."""
    if not nav_graph.node_exists(node_id):
        raise HTTPException(
            status_code=404,
            detail=f"Node '{node_id}' not found"
        )
    nav_graph.remove_node(node_id)
    return {"status": "removed", "node_id": node_id}


@router.patch("/nodes/{from_id}/edges/{to_id}")
def update_edge(from_id: str, to_id: str, new_weight: float):
    """Update edge weight dynamically (e.g. obstacle detected, reroute needed)."""
    if not nav_graph.node_exists(from_id) or not nav_graph.node_exists(to_id):
        raise HTTPException(
            status_code=404,
            detail="One or both nodes not found"
        )
    nav_graph.update_edge_weight(from_id, to_id, new_weight)
    return {
        "status": "updated",
        "from": from_id,
        "to": to_id,
        "new_weight": new_weight
    }