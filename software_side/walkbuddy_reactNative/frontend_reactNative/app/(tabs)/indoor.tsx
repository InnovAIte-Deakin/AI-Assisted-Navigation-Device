// app/indoor.tsx
import React, { useEffect, useMemo, useRef, useState } from "react";
import { View, Text, Pressable, StyleSheet, ScrollView, Platform } from "react-native";
import * as Speech from "expo-speech";
import * as Haptics from "expo-haptics";

import { POIS, V2_GRAPH, type NodeId } from "../../src/nav/v2_graph";
import { Radius, Typography } from "@/constants/theme";
import { useThemeColors } from "@/hooks/use-theme-colors";
import { PageHeader } from "@/components/ui/PageHeader";

type Adj = Record<string, Array<{ to: NodeId; cost: number }>>;

function buildAdjacency(): Adj {
  const adj: Adj = {};
  for (const e of V2_GRAPH) {
    if (!adj[e.from]) adj[e.from] = [];
    if (!adj[e.to]) adj[e.to] = [];
    adj[e.from].push({ to: e.to, cost: e.steps });
    adj[e.to].push({ to: e.from, cost: e.steps }); // treat as bidirectional for indoor corridors
  }
  return adj;
}

function getEdgeCost(a: NodeId, b: NodeId): number | null {
  for (const e of V2_GRAPH) {
    if ((e.from === a && e.to === b) || (e.from === b && e.to === a)) return e.steps;
  }
  return null;
}

// Dijkstra (simple + stable for demo)
function shortestPath(start: NodeId, goal: NodeId, adj: Adj): NodeId[] {
  if (start === goal) return [start];

  const dist: Record<string, number> = {};
  const prev: Record<string, NodeId | null> = {};
  const visited = new Set<string>();

  const nodes = Object.keys(POIS) as NodeId[];
  for (const n of nodes) {
    dist[n] = Number.POSITIVE_INFINITY;
    prev[n] = null;
  }
  dist[start] = 0;

  while (true) {
    let u: NodeId | null = null;
    let best = Number.POSITIVE_INFINITY;

    for (const n of nodes) {
      if (visited.has(n)) continue;
      if (dist[n] < best) {
        best = dist[n];
        u = n;
      }
    }

    if (!u) break;
    if (u === goal) break;

    visited.add(u);

    const nbrs = adj[u] || [];
    for (const { to, cost } of nbrs) {
      const alt = dist[u] + cost;
      if (alt < dist[to]) {
        dist[to] = alt;
        prev[to] = u;
      }
    }
  }

  if (!isFinite(dist[goal])) return [];

  const path: NodeId[] = [];
  let cur: NodeId | null = goal;
  while (cur) {
    path.push(cur);
    cur = prev[cur];
  }
  path.reverse();
  return path;
}

// heading angle from point A to B (degrees 0..360)
// 0 = East, 90 = North, 180 = West, 270 = South
function headingDeg(a: { x: number; y: number }, b: { x: number; y: number }): number {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const rad = Math.atan2(dy, dx);
  let deg = (rad * 180) / Math.PI;
  if (deg < 0) deg += 360;
  return deg;
}

function smallestAngleDiff(fromDeg: number, toDeg: number): number {
  let diff = (toDeg - fromDeg + 540) % 360 - 180;
  return diff; // -180..180
}

function turnWord(diff: number): string {
  const a = Math.abs(diff);
  if (a < 25) return "Go straight";
  if (diff > 0) return "Turn left";
  return "Turn right";
}

export default function IndoorNavScreen() {
  const colors = useThemeColors();
  const adj = useMemo(() => buildAdjacency(), []);

  const [start, setStart] = useState<NodeId>("N1");
  const [dest, setDest] = useState<NodeId>("N3");

  // simulated pose in "map units"
  const [pos, setPos] = useState(() => ({ x: POIS[start].x, y: POIS[start].y }));
  const [heading, setHeading] = useState<number>(0); // user-facing heading for demo

  // which segment of the path we are currently walking
  const [segIndex, setSegIndex] = useState<number>(0);

  const lastSpokenRef = useRef<string>("");

  const path = useMemo(() => shortestPath(start, dest, adj), [start, dest, adj]);

  // reset pose + segment when start/dest changes
  useEffect(() => {
    setPos({ x: POIS[start].x, y: POIS[start].y });
    setSegIndex(0);
    setHeading(0);
    lastSpokenRef.current = "";
  }, [start, dest]);

  const currentNode = path.length ? path[Math.min(segIndex, path.length - 1)] : start;
  const nextNode = path.length && segIndex < path.length - 1 ? path[segIndex + 1] : null;

  const segmentSteps = useMemo(() => {
    if (!nextNode) return 0;
    return getEdgeCost(currentNode, nextNode) ?? 0;
  }, [currentNode, nextNode]);

  // how many "steps" remaining in current segment (rough), based on proximity
  const remainingSteps = useMemo(() => {
    if (!nextNode) return 0;
    const a = pos;
    const b = POIS[nextNode];
    const d = Math.hypot(b.x - a.x, b.y - a.y); // map units
    // convert map-unit distance to steps using ratio derived from segment steps
    // if you tweak POIS coordinates later this still works as "relative"
    const full = Math.hypot(POIS[nextNode].x - POIS[currentNode].x, POIS[nextNode].y - POIS[currentNode].y) || 1;
    const ratio = segmentSteps / full;
    return Math.max(0, Math.round(d * ratio));
  }, [pos, nextNode, currentNode, segmentSteps]);

  const instruction = useMemo(() => {
    if (!path.length) return "No route available";
    if (!nextNode) return `Arrived at ${POIS[dest].name}`;

    const ideal = headingDeg(POIS[currentNode], POIS[nextNode]);
    const diff = smallestAngleDiff(heading, ideal);
    const turn = turnWord(diff);

    // speak something meaningful, not constantly changing
    return `Walk about ${Math.max(1, remainingSteps)} steps towards ${POIS[nextNode].name}. ${turn}.`;
  }, [path.length, nextNode, dest, currentNode, remainingSteps, heading]);

  // speak only when instruction meaningfully changes (segment change / arrived / destination change)
  useEffect(() => {
    if (!instruction) return;
    if (instruction === lastSpokenRef.current) return;

    lastSpokenRef.current = instruction;
    Haptics.selectionAsync().catch(() => {});
    Speech.stop();
    Speech.speak(instruction, { rate: 1.0 });
  }, [instruction]);

  const reset = () => {
    setPos({ x: POIS[start].x, y: POIS[start].y });
    setSegIndex(0);
    setHeading(0);
    lastSpokenRef.current = "";
  };

  // Walk 1 step along the path toward nextNode
  const walkOneStep = () => {
    if (!path.length || !nextNode) return;

    const a = pos;
    const b = POIS[nextNode];
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    const len = Math.hypot(dx, dy) || 1;

    // convert "1 step" into map-units using segment ratio
    const full = Math.hypot(b.x - POIS[currentNode].x, b.y - POIS[currentNode].y) || 1;
    const ratio = segmentSteps / full;
    const stepMapUnits = 1 / (ratio || 1); // one step worth of map units

    const nx = a.x + (dx / len) * stepMapUnits;
    const ny = a.y + (dy / len) * stepMapUnits;

    setPos({ x: nx, y: ny });

    // if close enough to next node, snap and advance segment
    const reached = Math.hypot(b.x - nx, b.y - ny) < 1.0;
    if (reached) {
      setPos({ x: b.x, y: b.y });
      setSegIndex((i) => Math.min(i + 1, Math.max(0, path.length - 1)));

      // update heading to the segment direction automatically (so the turn words make sense)
      const newHeading = headingDeg(POIS[currentNode], POIS[nextNode]);
      setHeading(newHeading);

      // force next instruction to speak (segment changed)
      lastSpokenRef.current = "";
    }
  };

  const rotateLeft = () => setHeading((h) => (h + 15) % 360);
  const rotateRight = () => setHeading((h) => (h - 15 + 360) % 360);

  // web keyboard shortcuts (demo-friendly)
  useEffect(() => {
    if (Platform.OS !== "web") return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "ArrowUp") walkOneStep();
      if (e.key === "ArrowLeft") rotateLeft();
      if (e.key === "ArrowRight") rotateRight();
      if (e.key.toLowerCase() === "r") reset();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [walkOneStep]);

  const poiList = useMemo(() => Object.values(POIS), []);

  return (
    <View style={[styles.safeArea, { backgroundColor: colors.background }]}>
      <PageHeader title="Interior Navigation" />
      <ScrollView style={styles.wrap} contentContainerStyle={{ paddingBottom: 40 }}>
      {/* Current location */}
      <View style={[styles.card, { borderColor: colors.accent, backgroundColor: colors.surface }]}>
        <Text style={[styles.h, { color: colors.accent }]}>Current Location</Text>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8 }}>
          {poiList.map((p) => (
            <Pressable
              key={p.id}
              onPress={() => setStart(p.id)}
              style={[
                styles.pill,
                { borderColor: colors.accent },
                start === p.id && { backgroundColor: colors.accent },
              ]}
            >
              <Text style={[styles.pillText, { color: start === p.id ? colors.accentText : colors.accent }]}>{p.name}</Text>
            </Pressable>
          ))}
        </ScrollView>
      </View>

      {/* Destination */}
      <View style={[styles.card, { borderColor: colors.accent, backgroundColor: colors.surface }]}>
        <Text style={[styles.h, { color: colors.accent }]}>Destination</Text>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8 }}>
          {poiList.map((p) => (
            <Pressable
              key={p.id}
              onPress={() => setDest(p.id)}
              style={[
                styles.pill,
                { borderColor: colors.accent },
                dest === p.id && { backgroundColor: colors.accent },
              ]}
            >
              <Text style={[styles.pillText, { color: dest === p.id ? colors.accentText : colors.accent }]}>{p.name}</Text>
            </Pressable>
          ))}
        </ScrollView>
      </View>

      {/* Instruction */}
      <View style={[styles.card, { borderColor: colors.accent, backgroundColor: colors.surface }]}>
        <Text style={[styles.h, { color: colors.accent }]}>Instruction</Text>
        <Text style={[styles.big, { color: colors.text }]}>{instruction}</Text>
        {path.length > 0 && (
          <Text style={[styles.sub, { color: colors.textMuted }]}>
            Path: {path.map((id) => id).join(" → ")}
          </Text>
        )}
      </View>

      {/* Simulator */}
      <View style={[styles.card, { borderColor: colors.accent, backgroundColor: colors.surface }]}>
        <Text style={[styles.h, { color: colors.accent }]}>Simulator</Text>
        <Text style={[styles.sub, { color: colors.textMuted }]}>
          Position: ({pos.x.toFixed(1)}, {pos.y.toFixed(1)}) | Heading: {Math.round(heading)}°
        </Text>

        <View style={styles.row}>
          <Pressable style={[styles.btn, { backgroundColor: colors.accent }]} onPress={walkOneStep}>
            <Text style={[styles.btnText, { color: colors.accentText }]}>Walk 1 step</Text>
          </Pressable>

          <Pressable style={[styles.btnOutline, { borderColor: colors.accent }]} onPress={reset}>
            <Text style={[styles.btnOutlineText, { color: colors.accent }]}>Reset</Text>
          </Pressable>
        </View>

        <View style={styles.row}>
          <Pressable style={[styles.smallBtn, { borderColor: colors.accent }]} onPress={rotateLeft}>
            <Text style={[styles.smallBtnText, { color: colors.accent }]}>⟲</Text>
          </Pressable>
          <Pressable style={[styles.smallBtn, { borderColor: colors.accent }]} onPress={rotateRight}>
            <Text style={[styles.smallBtnText, { color: colors.accent }]}>⟳</Text>
          </Pressable>
          <Text style={[styles.sub, { color: colors.textMuted, marginLeft: 8 }]}>Rotate to see Left/Right change</Text>
        </View>

        {Platform.OS === "web" && (
          <Text style={[styles.sub, { color: colors.textMuted }]}>Web keys: ↑ walk, ← rotate left, → rotate right, R reset</Text>
        )}
      </View>
      </ScrollView>
    </View>
  );
}

/* STYLES — structural only; colors applied inline so they react to
   light/dark via useThemeColors(). */

const styles = StyleSheet.create({
  safeArea: { flex: 1 },
  wrap: { flex: 1, paddingHorizontal: 14 },

  card: {
    borderWidth: 1,
    borderRadius: Radius.md,
    padding: 12,
    marginBottom: 10,
    gap: 8,
  },

  h: { fontWeight: "900" },
  big: { fontSize: Typography.size.md, fontWeight: "800" },
  sub: { marginTop: 4 },

  pill: { borderWidth: 1, paddingVertical: 8, paddingHorizontal: 12, borderRadius: Radius.pill },
  pillText: { fontWeight: "800" },

  row: { flexDirection: "row", gap: 10, alignItems: "center", marginTop: 8, flexWrap: "wrap" },
  btn: { paddingVertical: 12, paddingHorizontal: 14, borderRadius: Radius.md },
  btnText: { fontWeight: "900" },
  btnOutline: { borderWidth: 1, paddingVertical: 12, paddingHorizontal: 14, borderRadius: Radius.md },
  btnOutlineText: { fontWeight: "900" },

  smallBtn: {
    borderWidth: 1,
    borderRadius: 10,
    width: 44,
    height: 44,
    alignItems: "center",
    justifyContent: "center",
  },
  smallBtnText: { fontWeight: "900", fontSize: Typography.size.md },
});
