# BAKKE — Acoustic Evidence Intelligence Platform

## Research-Driven Project Proposal

### 1. Executive Summary

**BAKKE** is an AI-powered **Acoustic Evidence Intelligence Platform** for investigator decision support. Rather than claiming to reconstruct a crime or determine guilt, BAKKE focuses on a more defensible problem:

> **Evidence-constrained hypothesis generation and consistency checking for investigators.**

The system ingests case material—including text, audio, photographs, witness statements, and forensic findings—and converts it into structured facts and a chronological timeline. It then generates multiple evidence-consistent hypotheses, checks each hypothesis for contradictions, identifies conflicts between witness claims and physical evidence, and presents the results through an interpretable **schematic 2D/3D storyboard**.

The objective is to prevent investigators from prematurely committing to a single narrative. BAKKE presents **multiple plausible scenarios, supporting evidence, contradictions, and impossible conditions** for human evaluation.

---

## 2. Problems Being Solved

### Evidence is collected but under-analyzed

Research conducted for this project indicates that only approximately **9.6% of hard-to-solve cases involving stranger perpetrators, no witnesses, and physical evidence receive laboratory analysis**, while approximately **7.5 lakh Indian cases per year** may close as untraced or with no clue.

**BAKKE:** structures heterogeneous evidence and connects evidence items to candidate explanations.

### Witness memory can be unreliable

Our research indicates that approximately **69% of DNA exoneration cases are associated with mistaken eyewitness identification**. A major gap is the lack of systematic tools for testing witness accounts against physical evidence.

**BAKKE:** detects timeline, spatial, physical, and evidentiary inconsistencies without deciding whether a witness is truthful.

### Cold and hit-and-run cases can stall

Research indicates that approximately **42–47% of fatal crashes in Delhi involve never-identified vehicles**, while approximately **34% of Indian road deaths are associated with hit-and-run incidents**.

**BAKKE:** organizes accident evidence into alternative event sequences and tests them against available constraints.

### Investigator tunnel vision

Once an investigator develops a strong theory or receives a suspect identification, alternative explanations may receive less attention.

**BAKKE:** deliberately generates **multiple evidence-consistent hypotheses** rather than one narrative.

---

## 3. Core Concept

BAKKE does **not** claim:

> “AI reconstructs the crime.”

BAKKE claims:

> **“BAKKE generates evidence-constrained hypotheses and checks their consistency for investigators.”**

The visual output is therefore a **schematic storyboard**, not a photorealistic recreation or a claim about what actually happened.

---

## 4. Proposed System

### Input

- Textual case files
- Witness statements
- Audio recordings
- Photographs
- Forensic findings
- Physical evidence descriptions
- Time and location information
- Accident/vehicle information
- Structured case records

### Processing

**1. Evidence Structuring**  
Convert raw material into facts involving people, objects, locations, times, actions, measurements, statements, and findings.

**2. Timeline Construction**  
Build a chronological representation of known and uncertain events.

**3. Evidence Retrieval**  
Retrieve relevant information from case files and forensic knowledge to ground reasoning.

**4. Multi-Hypothesis Generation**  
Generate multiple candidate scenarios instead of one narrative.

**5. Consistency Checking**  
Test scenarios against known facts, timeline constraints, spatial relationships, physical constraints, witness statements, and forensic findings.

**6. Contradiction Detection**  
Flag conflicts and impossible conditions.

Example:

> **IMPOSSIBLE:** Scenario requires Person A to be at Location B at 20:10, while verified evidence places Person A at Location C at 20:10.

**7. Scenario Visualization**  
Convert viable hypotheses into a schematic 2D/3D storyboard showing participants, objects, locations, movement paths, and event sequence.

---

## 5. Killer Demo

The core demonstration:

```text
UPLOAD CASE EVIDENCE
        ↓
STRUCTURE FACTS + TIMELINE
        ↓
GENERATE 3 CANDIDATE SCENARIOS
        ↓
CHECK EACH SCENARIO
        ↓
┌───────────────────────────────────┐
│ SCENARIO 1                        │
│ Supporting Evidence: 7            │
│ Witness Conflicts: 1              │
│ Impossible Conditions: 0          │
│ Support Score: HIGH               │
└───────────────────────────────────┘

┌───────────────────────────────────┐
│ SCENARIO 2                        │
│ Supporting Evidence: 5            │
│ Witness Conflicts: 2              │
│ Impossible Conditions: 1          │
│ Support Score: MEDIUM             │
└───────────────────────────────────┘

┌───────────────────────────────────┐
│ SCENARIO 3                        │
│ Supporting Evidence: 6            │
│ Witness Conflicts: 0              │
│ Impossible Conditions: 0          │
│ Support Score: HIGH               │
└───────────────────────────────────┘
        ↓
SCHEMATIC STORYBOARDS
        ↓
INVESTIGATOR COMPARISON
```

Each scenario exposes **supporting evidence, conflicting statements, impossible conditions, and the reasoning behind the score**.

---

## 6. Confidence Model

BAKKE should not describe its confidence score as the probability that a scenario actually happened.

Instead:

> **Confidence Score = Evidence Support / Consistency Score**

It represents how strongly available evidence supports a hypothesis and how few contradictions it contains.

| Scenario | Evidence Support | Conflicts | Impossible Conditions | Support |
|---|---:|---:|---:|---|
| A | 8 | 1 | 0 | High |
| B | 6 | 2 | 1 | Medium |
| C | 4 | 4 | 2 | Low |

A highly supported hypothesis is **not automatically the true historical sequence**.

---

## 7. System Architecture

```text
┌──────────────────────────────────────┐
│             CASE EVIDENCE             │
│ Text • Audio • Photos • Statements    │
│ Forensics • Measurements              │
└──────────────────┬───────────────────┘
                   ↓
┌──────────────────────────────────────┐
│          EVIDENCE INGESTION           │
│ Extraction • Classification           │
└──────────────────┬───────────────────┘
                   ↓
┌──────────────────────────────────────┐
│          CASE KNOWLEDGE LAYER         │
│ Facts • Entities • Timeline • Evidence│
└──────────────────┬───────────────────┘
                   ↓
┌──────────────────────────────────────┐
│       EVIDENCE-CONSTRAINED ENGINE     │
│ Hypothesis • Reasoning • Consistency  │
│ Contradictions • Evidence Linking     │
└──────────────────┬───────────────────┘
                   ↓
┌──────────────────────────────────────┐
│          SCENARIO EVALUATION          │
│ Support • Conflicts • Constraints     │
│ Impossible Conditions • Score         │
└──────────────────┬───────────────────┘
                   ↓
┌──────────────────────────────────────┐
│       SCHEMATIC STORYBOARD            │
│ Positions • Paths • Events • Timeline │
└──────────────────┬───────────────────┘
                   ↓
┌──────────────────────────────────────┐
│        INVESTIGATOR WORKSPACE         │
│ Compare • Inspect • Validate • Decide │
└──────────────────────────────────────┘
```

---

## 8. Feasibility and Scope

| Capability | Feasibility |
|---|---|
| Text/audio/photo ingestion | High |
| Structured fact extraction | High |
| Timeline generation | High |
| RAG over case files and forensic knowledge | High |
| Evidence-constrained hypothesis generation | Medium–High |
| Inconsistency detection | Medium–High |
| Support/confidence scoring | Medium |
| Schematic 2D/3D storyboard | Medium–High |
| Photorealistic crime-scene video | **Out of Scope** |

### Scope Decision

BAKKE will **not** attempt photorealistic crime-scene video.

The project will use **schematic visualizations and storyboard-style animations**. This keeps the system technically defensible and prevents visual output from being mistaken for factual evidence.

---

## 9. Research Contribution

A key research gap identified during the project investigation is the lack of a widely available public benchmark for:

> **Evidence → Plausible Hypotheses**

BAKKE addresses this gap through a structured evaluation framework and curated dataset for evidence-constrained scenario generation.

### Contributions

1. Evidence-to-hypothesis pipeline.
2. Consistency-checking mechanism.
3. Contradiction detection.
4. Evidence-linked scenario scoring.
5. Benchmark dataset and evaluation framework.
6. Human-in-the-loop investigative workflow.

---

## 10. Dataset Strategy

Real police case files are generally inaccessible for this project. BAKKE therefore proposes a **curated synthetic evaluation dataset** based on public material.

### Sources

- Published forensic case studies
- Publicly documented crime reconstructions
- Accident-reconstruction literature
- Public forensic reports and educational cases
- Public structured accident datasets where applicable

Each case becomes an evidence package:

```text
Case ID
↓
Facts
↓
Time & Location
↓
Physical Evidence
↓
Witness Statements
↓
Forensic Findings
↓
Ground-Truth Sequence
↓
Expected Constraints
```

### Target

**60–80 case packages** for the semester implementation, with a possible **70/15/15 train/validation/test split**.

---

## 11. Evaluation Framework

### Hypothesis Retrieval

Measure whether a ground-truth-compatible scenario appears in:

- Top-1
- Top-3
- Top-5

### Faithfulness

Measure how frequently generated scenarios introduce unsupported or contradictory facts.

### Feasibility Error Rate

Measure scenarios violating explicit physical, temporal, or spatial constraints.

### Witness Consistency

Measure whether generated scenarios remain consistent with witness statements and identify known contradictions.

### Baseline Comparison

Compare:

1. BAKKE
2. Rule-based baseline
3. Human evaluators/investigators

Use the same evaluation set with appropriate **k-fold evaluation, statistical tests, and error analysis**.

---

## 12. Three-Paper Research Structure

### Paper 1 — Literature Survey

**AI and LLM-Based Methods for Forensic Reconstruction and Evidence Analysis**

Survey existing forensic AI, LLM reasoning, evidence analysis, reconstruction, explainability, and human-in-the-loop systems.

### Paper 2 — Proposed System

**Evidence-Constrained Hypothesis Generation for Investigative Decision Support**

Evaluate:

- Top-k hypothesis performance
- Faithfulness
- Feasibility-error rate
- Witness consistency

### Paper 3 — Comparative Evaluation

**Comparative Evaluation of Evidence-Constrained Hypothesis Generation**

Compare BAKKE against rule-based methods and human baselines using the same evaluation set, statistical analysis, and error analysis.

---

## 13. Reusing the Existing MediHelp Architecture

BAKKE can reuse the existing **MediHelp** architecture for:

- Intake
- RAG
- Explainability
- Human-in-the-loop workflow
- Audit trail
- Structured case processing

The primary new component is the **Scenario Engine**:

```text
Hypothesis Generation
        +
Consistency Checking
        +
Evidence Linking
        +
Scenario Scoring
        +
Storyboard Generation
```

Therefore, the project is a focused extension of an existing architecture rather than a complete rebuild.

---

## 14. Investigator-in-the-Loop

```text
AI
↓
Generate Possibilities
↓
Explain Evidence
↓
Flag Contradictions
↓
Visualize Scenarios
↓
Human Investigator
↓
Compare With Additional Evidence
↓
Final Decision
```

BAKKE supports investigation; it does not replace investigative judgment.

---

## 15. Expected Outcome

The final prototype should be capable of:

- Accepting a structured evidence package.
- Extracting relevant facts.
- Building a case timeline.
- Retrieving supporting case knowledge.
- Generating multiple candidate hypotheses.
- Checking hypotheses against constraints.
- Detecting contradictions.
- Linking claims to evidence.
- Producing support/consistency scores.
- Generating schematic 2D/3D scenario storyboards.
- Comparing competing hypotheses.
- Maintaining an auditable human-in-the-loop workflow.

---

## 16. Recommended Semester Scope

### Phase 1 — Foundation
- Literature review
- Evidence schema
- Dataset collection
- Case representation

### Phase 2 — Intelligence
- Evidence extraction
- Timeline generation
- RAG
- Hypothesis generation
- Constraint checking
- Contradiction detection

### Phase 3 — Visualization
- Scenario representation
- Schematic 2D/3D storyboard
- Movement and event visualization
- Scenario comparison

### Phase 4 — Evaluation
- Build 60–80 case evaluation set
- Run baseline comparisons
- Measure Top-k performance
- Measure faithfulness
- Measure feasibility-error rate
- Measure witness consistency
- Statistical analysis

### Phase 5 — Research Output
- Literature survey paper
- Proposed-system paper
- Comparative evaluation paper
- Final prototype demonstration

---

## 17. Final Positioning

**BAKKE is not a system that tells investigators who committed a crime.**

It asks:

> **“Given everything we currently know, what are the plausible explanations—and which of them are consistent or inconsistent with the evidence?”**

That distinction defines the project's **technical scope, research contribution, and practical value**.

### One-Line Pitch

> **BAKKE turns fragmented case evidence into multiple evidence-constrained hypotheses, checks them for contradictions, and visualizes the possibilities so investigators can make better-informed decisions.**

### Tagline

> **BAKKE — Hear the Evidence. Visualize the Possibilities.**
