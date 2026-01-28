import { EDGES, getNode } from "./graph";
import { NodeId } from "./types";

type Neighbor = { id: NodeId; cost: number };

function neighbors(id: NodeId): Neighbor[] {
  const out: Neighbor[] = [];
  for (const e of EDGES) {
    if (e.a === id) out.push({ id: e.b, cost: e.steps });
    if (e.b === id) out.push({ id: e.a, cost: e.steps });
  }
  return out;
}

// Heuristic for A*: straight-line distance on the relative coordinates
function h(a: NodeId, b: NodeId) {
  const A = getNode(a);
  const B = getNode(b);
  if (!A || !B) return 0;
  const dx = A.x - B.x;
  const dy = A.y - B.y;
  return Math.sqrt(dx * dx + dy * dy) * 100; // scale into “step-like” units
}

export function findPathAStar(start: NodeId, goal: NodeId): NodeId[] {
  const open = new Set<NodeId>([start]);
  const cameFrom = new Map<NodeId, NodeId>();

  const gScore = new Map<NodeId, number>();
  const fScore = new Map<NodeId, number>();
  gScore.set(start, 0);
  fScore.set(start, h(start, goal));

  function lowestF(): NodeId | null {
    let best: NodeId | null = null;
    let bestVal = Infinity;
    for (const n of open) {
      const v = fScore.get(n) ?? Infinity;
      if (v < bestVal) {
        bestVal = v;
        best = n;
      }
    }
    return best;
  }

  while (open.size > 0) {
    const current = lowestF();
    if (!current) break;

    if (current === goal) {
      // reconstruct
      const path: NodeId[] = [current];
      let cur = current;
      while (cameFrom.has(cur)) {
        cur = cameFrom.get(cur)!;
        path.unshift(cur);
      }
      return path;
    }

    open.delete(current);

    for (const nb of neighbors(current)) {
      const tentative = (gScore.get(current) ?? Infinity) + nb.cost;
      if (tentative < (gScore.get(nb.id) ?? Infinity)) {
        cameFrom.set(nb.id, current);
        gScore.set(nb.id, tentative);
        fScore.set(nb.id, tentative + h(nb.id, goal));
        open.add(nb.id);
      }
    }
  }

  return [];
}
