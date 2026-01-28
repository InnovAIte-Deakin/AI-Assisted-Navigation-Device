// src/nav/guidance.ts
import type { NodeId, Node } from "./v2_graph";

type POIMap = Record<NodeId, Node>;

export function computeGuidance(
  path: NodeId[],
  pos: { x: number; y: number },
  pois: POIMap
) {
  if (!path.length) {
    return { text: "No route available", target: null as NodeId | null };
  }

  // find nearest “next node” on path based on distance to pos
  let bestIdx = 0;
  let bestD = Infinity;

  for (let i = 0; i < path.length; i++) {
    const n = pois[path[i]];
    const d = Math.hypot(n.x - pos.x, n.y - pos.y);
    if (d < bestD) {
      bestD = d;
      bestIdx = i;
    }
  }

  const current = path[bestIdx];
  const next = path[Math.min(bestIdx + 1, path.length - 1)];
  const dest = path[path.length - 1];

  if (current === dest && bestD < 1.5) {
    return { text: `Arrived at ${pois[dest].name}`, target: null as NodeId | null };
  }

  const target = next;
  const targetNode = pois[target];
  const stepsRough = Math.max(1, Math.round(Math.hypot(targetNode.x - pos.x, targetNode.y - pos.y)));

  return {
    text: `Walk about ${stepsRough} steps towards ${targetNode.name}`,
    target,
  };
}
