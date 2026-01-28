export type NodeType = "poi" | "junction";

export type NodeId =
  | "N1" | "N2" | "N3" | "N4" | "N5" | "N6" | "N7" | "N8" | "N9" | "N10"
  | "N11" | "N12" | "N13" | "N14" | "N15";

export type Node = {
  id: NodeId;
  name: string;
  type: NodeType;
  x: number; // relative map coordinates (0..1)
  y: number; // relative map coordinates (0..1)
};

export type Edge = {
  a: NodeId;
  b: NodeId;
  steps: number; // relative steps estimate
};
