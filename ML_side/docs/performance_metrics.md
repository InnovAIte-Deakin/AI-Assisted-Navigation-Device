# Performance Metrics — Sprint 1 & 2
**AI-Assisted Navigation Device | ML Stream | Bravine Cheruiyot**
*Last updated: 2026-05-05*

---

## 1. Test Suite Results

### Sprint 1 — Navigation Pipeline Tests

| Test | Result | Time |
|------|--------|------|
| A* Pathfinding | PASSED | <1ms |
| D* Pathfinding | PASSED | <1ms |
| RRT* Pathfinding | PASSED | <1ms |
| Navigation Planner | PASSED | <1ms |
| Semantic Mapping | PASSED | <1ms |
| Visualisation | PASSED | <1ms |
| **Total** | **6/6** | **0.3s** |

### Sprint 2 — Full Test Suite

| Test File | Tests | Passed | Failed | Time |
|-----------|-------|--------|--------|------|
| `test_priority.py` | 30 | 30 | 0 | 0.24s |
| `test_api.py` | 25 | 25 | 0 | 3.47s |
| `test_llm_engine.py` | 13 | 13 | 0 | 0.20s |
| **Total** | **68** | **68** | **0** | **3.91s** |

### Test Pass Rate — Sprint 1 vs Sprint 2

```
Sprint 1   ████████████████████  6/6   (100%)
Sprint 2   ████████████████████  68/68 (100%)
Combined   ████████████████████  74/74 (100%)
```

---

## 2. Object Priority Assignment — Coverage Matrix

| Class | Priority | Label | Tests Covering | Result |
|-------|----------|-------|---------------|--------|
| stairs | 5 | CRITICAL | 4 | ✅ PASS |
| emergency-exit | 5 | CRITICAL | 2 | ✅ PASS |
| person | 4 | HIGH | 3 | ✅ PASS |
| fire-extinguisher | 4 | HIGH | 1 | ✅ PASS |
| door | 3 | MEDIUM | 2 | ✅ PASS |
| elevator | 3 | MEDIUM | 1 | ✅ PASS |
| handrail | 3 | MEDIUM | 1 | ✅ PASS |
| signage | 2 | LOW | 1 | ✅ PASS |
| whiteboard | 2 | LOW | 1 | ✅ PASS |
| tv | 2 | LOW | 1 | ✅ PASS |
| book | 1 | MINIMAL | 3 | ✅ PASS |
| books | 1 | MINIMAL | 1 | ✅ PASS |
| monitor | 1 | MINIMAL | 1 | ✅ PASS |
| office-chair | 1 | MINIMAL | 1 | ✅ PASS |
| table | 1 | MINIMAL | 1 | ✅ PASS |
| **Coverage** | | | **15/15 classes** | **100%** |

### Priority Distribution (15 classes)

```
CRITICAL (5) ██                        2 classes  (13%)
HIGH     (4) ██                        2 classes  (13%)
MEDIUM   (3) ███                       3 classes  (20%)
LOW      (2) ███                       3 classes  (20%)
MINIMAL  (1) █████                     5 classes  (33%)
             0        1        2        3        4        5
```

---

## 3. Navigation Decision Accuracy

Tested against 8 scenarios covering all priority tiers:

| Scenario | Input Priority | Expected Decision | Actual | Result |
|----------|---------------|-------------------|--------|--------|
| Stairs ahead | 5 | STOP | STOP | ✅ |
| Emergency exit detected | 5 | STOP | STOP | ✅ |
| Person blocking path | 4 | CAUTION | CAUTION | ✅ |
| Door ahead | 3 | AWARE | AWARE | ✅ |
| Book on left | 1 | PROCEED | PROCEED | ✅ |
| Empty scene | — | PROCEED | PROCEED | ✅ |
| Stairs + book (mixed) | 5 (override) | STOP | STOP | ✅ |
| Person + furniture (mixed) | 4 (override) | CAUTION | CAUTION | ✅ |
| **Accuracy** | | | | **8/8 (100%)** |

### Priority Override Behaviour

```
Mixed scene: book (P1) + stairs (P5)
  Without priority → book wins (detected first)  ❌
  With priority    → stairs wins (highest danger) ✅

Mixed scene: table (P1) + person (P4) + whiteboard (P2)
  Without priority → table wins (first detected)  ❌
  With priority    → person wins (highest danger) ✅
```

---

## 4. YOLO Model Performance — Sprint 1

| Metric | Value | Target |
|--------|-------|--------|
| mAP@0.5 (6 classes) | 85.7% | 80% | ✅ |
| Inference speed | ~50ms/frame | <100ms | ✅ |
| Training epochs | 150 | — | — |
| Dataset size | 2,400+ images | — | — |
| Confidence threshold | 0.5 | — | — |

### Per-Class Detection Performance (Sprint 1)

```
monitor       ████████████████████  90%
office-chair  ████████████████████  95%
table         ██████████████████    88%
whiteboard    ████████████████      82%
books         ████████████████      83%
book          ███████████████       78%
              0%      25%     50%     75%    100%
```

---

## 5. Pathfinding Performance — Sprint 1

| Algorithm | Avg Time | Use Case |
|-----------|----------|----------|
| A* | 17–50ms | Optimal short paths, static map |
| D* | 25–60ms | Dynamic re-routing |
| RRT* | ~320ms | Complex/cluttered spaces |

### Algorithm Speed Comparison

```
A*    ███                  17–50ms   (fastest, optimal)
D*    ████                 25–60ms   (dynamic obstacles)
RRT*  ████████████████     ~320ms    (complex spaces)
      0ms    100ms   200ms   300ms   400ms
```

---

## 6. FastAPI Deployment — Endpoint Performance

| Endpoint | Avg Response | Tests | Status |
|----------|-------------|-------|--------|
| GET /health | <5ms | 2/2 | ✅ |
| GET /classes | <5ms | 3/3 | ✅ |
| POST /navigate | 50–200ms | 7/7 | ✅ |
| POST /detect | 50–150ms | 6/6 | ✅ |
| GET /demo | 50–200ms | 3/3 | ✅ |

---

## 7. Hybrid LLM Engine — Tier Performance

| Tier | Avg Latency | Availability | Fallback |
|------|------------|-------------|---------|
| Ollama (offline) | 200–500ms | Requires local install | → OpenAI |
| OpenAI (cloud) | 300–800ms | Requires API key | → Rule-based |
| Rule-based | <1ms | Always available | Final fallback |

### Latency Comparison

```
Rule-based  ▏                         <1ms
Ollama      ██████████                200–500ms
OpenAI      █████████████             300–800ms
            0ms   200ms  400ms  600ms  800ms
```

---

## 8. Sprint Summary

| Metric | Sprint 1 | Sprint 2 | Total |
|--------|----------|----------|-------|
| Tests written | 6 | 68 | 74 |
| Tests passing | 6/6 | 68/68 | 74/74 |
| Pass rate | 100% | 100% | 100% |
| Object classes | 6 | 15 | 15 |
| Files created/modified | 12 | 18 | 30 |
| GitHub PRs raised | 1 | 3 | 4 |
| Issues closed | — | #65, #67 | 2 |

### Sprint Velocity

```
Tests
74 |                              ████
68 |                         ████ ████
   |                    ████ ████ ████
 6 | ████           ████ ████ ████ ████
   +----------------------------------
      S1 total  S2 api  S2 llm  S2 pri
```

---

## 9. Issue Coverage

| Issue | Description | Status |
|-------|-------------|--------|
| #65 | HAZARD_CLASSES.md — keystone spec | ✅ Closed |
| #67 | max_messages=1 silent data loss | ✅ Closed |
| #55 | person=SAFE contradiction flagged | ⚠️ Flagged |
| #68 | Update safetygate.py keywords | 🔜 Unblocked |
| #69 | Update message_reasoning.py | 🔜 Unblocked |
| #70 | Add hazard annotations | 🔜 Unblocked |
| #71 | Retrain YOLO 18 classes | 🔜 Unblocked |
| #72 | End-to-end validation | 🔜 Unblocked |
