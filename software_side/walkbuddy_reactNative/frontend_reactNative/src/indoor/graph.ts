import { Node, Edge, NodeId } from "./types";

// IMPORTANT:
// x,y are relative placeholders (0..1). We will refine when you confirm positions.
// For demo: keep them reasonable so direction angles work.
export const NODES: Node[] = [
  { id: "N1", name: "Main Entrance", type: "poi", x: 0.52, y: 0.86 },
  { id: "N2", name: "Main Exit", type: "poi", x: 0.74, y: 0.90 },
  { id: "N3", name: "Help Desk", type: "poi", x: 0.63, y: 0.75 },
  { id: "N4", name: "Printing", type: "poi", x: 0.49, y: 0.73 },
  { id: "N5", name: "Book Returns", type: "poi", x: 0.66, y: 0.83 },
  { id: "N6", name: "Staircase", type: "poi", x: 0.72, y: 0.46 },
  { id: "N7", name: "Computer Zone", type: "poi", x: 0.63, y: 0.48 },
  { id: "N8", name: "Quiet Study", type: "poi", x: 0.30, y: 0.50 },
  { id: "N9", name: "Toilets (Female)", type: "poi", x: 0.12, y: 0.16 },
  { id: "N10", name: "Toilets (Male)", type: "poi", x: 0.12, y: 0.24 },
  { id: "N11", name: "Lifts", type: "poi", x: 0.67, y: 0.61 },
  { id: "N12", name: "Meeting Rooms", type: "poi", x: 0.80, y: 0.18 },
  { id: "N13", name: "Corridor Hub", type: "junction", x: 0.58, y: 0.58 },
  { id: "N14", name: "Office", type: "poi", x: 0.79, y: 0.58 },
  { id: "N15", name: "Accessible Toilet", type: "poi", x: 0.73, y: 0.78 },
];

// For your “single path” layout, this edge list is basically a backbone + short branches.
// Steps are demo values. You do NOT need perfect numbers right now.
export const EDGES: Edge[] = [
  { a: "N1", b: "N5", steps: 18 },
  { a: "N5", b: "N3", steps: 14 },
  { a: "N3", b: "N13", steps: 22 },
  { a: "N13", b: "N7", steps: 18 },
  { a: "N7", b: "N6", steps: 10 },
  { a: "N13", b: "N11", steps: 10 },
  { a: "N11", b: "N14", steps: 14 },
  { a: "N3", b: "N4", steps: 10 },
  { a: "N13", b: "N8", steps: 40 },
  { a: "N8", b: "N10", steps: 55 },
  { a: "N10", b: "N9", steps: 12 },
  { a: "N3", b: "N15", steps: 16 },
  { a: "N11", b: "N12", steps: 38 },
  { a: "N1", b: "N2", steps: 8 },
];

export function getNode(id: NodeId) {
  return NODES.find(n => n.id === id);
}
