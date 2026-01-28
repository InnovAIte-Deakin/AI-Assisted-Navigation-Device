// src/nav/astar.ts
import type { Edge, NodeId } from "./v2_graph";

type Adj = Record<NodeId, Array<{ to: NodeId; cost: number }>>;

function buildAdj(edges: Edge[]): Adj {
  const adj = {} as Adj;

  for (const e of edges ?? []) {
    if (!adj[e.from]) adj[e.from] = [];
    if (!adj[e.to]) adj[e.to] = [];

    // undirected (bidirectional) so routes work both ways
    adj[e.from].push({ to: e.to, cost: e.steps });
    adj[e.to].push({ to: e.from, cost: e.steps });
  }

  return adj;
}

export function aStar(start: NodeId, goal: NodeId, edges: Edge[]): NodeId[] {
  const adj = buildAdj(edges);

  // Dijkstra (good enough for demo; A* heuristic optional later)
  const dist: Partial<Record<NodeId, number>> = {};
  const prev: Partial<Record<NodeId, NodeId | null>> = {};
  const visited = new Set<NodeId>();

  // init
  Object.keys(adj).forEach((k) => {
    dist[k as NodeId] = Infinity;
    prev[k as NodeId] = null;
  });
  dist[start] = 0;

  while (true) {
    // pick unvisited node with smallest dist
    let u: NodeId | null = null;
    let best = Infinity;

    for (const k of Object.keys(adj) as NodeId[]) {
      if (!visited.has(k) && (dist[k] ?? Infinity) < best) {
        best = dist[k] ?? Infinity;
        u = k;
      }
    }

    if (!u) break;         // unreachable
    if (u === goal) break;  // reached goal

    visited.add(u);

    for (const n of adj[u] ?? []) {
      const alt = (dist[u] ?? Infinity) + n.cost;
      if (alt < (dist[n.to] ?? Infinity)) {
        dist[n.to] = alt;
        prev[n.to] = u;
      }
    }
  }

  if ((dist[goal] ?? Infinity) === Infinity) return [];

  // reconstruct
  const path: NodeId[] = [];
  let cur: NodeId | null = goal;

  while (cur) {
    path.push(cur);
    cur = prev[cur] ?? null;
  }

  path.reverse();
  return path;
}
