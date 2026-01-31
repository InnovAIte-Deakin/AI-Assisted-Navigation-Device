// src/nav/v2_graph.ts
export type NodeId =
  | "N1" | "N2" | "N3" | "N4" | "N5"
  | "N6" | "N7" | "N8" | "N9" | "N10"
  | "N11" | "N12" | "N13" | "N14" | "N15";

export type Node = {
  id: NodeId;
  name: string;
  x: number; // relative coordinates (any scale)
  y: number;
};

export type Edge = {
  from: NodeId;
  to: NodeId;
  steps: number; // use steps not meters
};

export const POIS: Record<NodeId, Node> = {
  N1: { id: "N1", name: "Main Entrance", x: 10, y: 90 },
  N2: { id: "N2", name: "Exit", x: 80, y: 92 },
  N3: { id: "N3", name: "Help Desk", x: 60, y: 72 },
  N4: { id: "N4", name: "Display Area", x: 40, y: 82 },
  N5: { id: "N5", name: "Book Returns", x: 55, y: 86 },
  N6: { id: "N6", name: "Printing Area", x: 78, y: 60 },
  N7: { id: "N7", name: "Computer Zone", x: 65, y: 48 },
  N8: { id: "N8", name: "Quiet Study Area", x: 30, y: 50 },
  N9: { id: "N9", name: "Male Toilets", x: 12, y: 10 },
  N10:{ id: "N10",name: "Female Toilets", x: 12, y: 18 },
  N11:{ id: "N11",name: "Accessible Toilet", x: 30, y: 88 },
  N12:{ id: "N12",name: "Lift", x: 60, y: 62 },
  N13:{ id: "N13",name: "Staircase", x: 63, y: 58 },
  N14:{ id: "N14",name: "Meeting Rooms", x: 72, y: 25 },
  N15:{ id: "N15",name: "Office Area", x: 78, y: 30 },
};

/**
 * Graph as adjacency list, steps are demo numbers (relative).
 * You can change these later after you refine the connections.
 */
export const V2_GRAPH: Edge[] = [
  { from: "N1", to: "N4", steps: 12 },
  { from: "N4", to: "N5", steps: 8 },
  { from: "N5", to: "N3", steps: 10 },
  { from: "N3", to: "N12", steps: 10 },
  { from: "N12", to: "N13", steps: 4 },
  { from: "N3", to: "N7", steps: 16 },
  { from: "N7", to: "N6", steps: 10 },
  { from: "N7", to: "N8", steps: 20 },
  { from: "N1", to: "N11", steps: 10 },
  { from: "N1", to: "N2", steps: 6 },

  { from: "N8", to: "N10", steps: 30 },
  { from: "N8", to: "N9", steps: 28 },

  { from: "N7", to: "N14", steps: 22 },
  { from: "N14", to: "N15", steps: 8 },
];
