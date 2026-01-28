import { EDGES, getNode, NODES } from "./graph";
import { NodeId } from "./types";

function edgeSteps(a: NodeId, b: NodeId) {
  const e = EDGES.find(x => (x.a === a && x.b === b) || (x.a === b && x.b === a));
  return e?.steps ?? 0;
}

function angleDeg(ax: number, ay: number, bx: number, by: number, cx: number, cy: number) {
  // angle between vector AB and BC
  const v1x = bx - ax;
  const v1y = by - ay;
  const v2x = cx - bx;
  const v2y = cy - by;

  const dot = v1x * v2x + v1y * v2y;
  const mag1 = Math.sqrt(v1x * v1x + v1y * v1y);
  const mag2 = Math.sqrt(v2x * v2x + v2y * v2y);
  if (mag1 === 0 || mag2 === 0) return 0;

  const cos = Math.max(-1, Math.min(1, dot / (mag1 * mag2)));
  const ang = Math.acos(cos) * (180 / Math.PI);

  // Determine left vs right using cross product sign
  const cross = v1x * v2y - v1y * v2x;
  return cross >= 0 ? ang : -ang; // positive = left-ish, negative = right-ish
}

function turnInstruction(turnAngle: number) {
  const a = turnAngle;
  const abs = Math.abs(a);

  // Small angle = continue
  if (abs < 25) return "Continue straight";
  if (abs < 60) return a > 0 ? "Turn slightly left" : "Turn slightly right";
  return a > 0 ? "Turn left" : "Turn right";
}

export function buildDirections(path: NodeId[]) {
  let totalSteps = 0;
  const lines: string[] = [];

  if (path.length < 2) return { lines, totalSteps };

  const startNode = getNode(path[0]);
  const endNode = getNode(path[path.length - 1]);
  if (!startNode || !endNode) return { lines, totalSteps };

  lines.push(`Starting from ${startNode.name}.`);

  for (let i = 0; i < path.length - 1; i++) {
    const a = path[i];
    const b = path[i + 1];
    const steps = edgeSteps(a, b);
    totalSteps += steps;

    const A = getNode(a);
    const B = getNode(b);

    if (!A || !B) continue;

    // If we have a next-next point, generate a turning instruction at B
    if (i < path.length - 2) {
      const c = path[i + 2];
      const C = getNode(c);
      if (C) {
        const turn = angleDeg(A.x, A.y, B.x, B.y, C.x, C.y);
        lines.push(`Walk about ${steps} steps towards ${B.name}. ${turnInstruction(turn)}.`);
      } else {
        lines.push(`Walk about ${steps} steps towards ${B.name}.`);
      }
    } else {
      lines.push(`Walk about ${steps} steps towards ${B.name}.`);
    }
  }

  lines.push(`You have arrived at ${endNode.name}.`);

  return { lines, totalSteps };
}
