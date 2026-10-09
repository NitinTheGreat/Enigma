# SKELETON — Specified but Not Enacted

**Working title.** Specified but Not Enacted: Auditing Epistemic Control
Mechanisms in an Agentic Intrusion Triage System

**Target.** 8 pages, IEEE two column.

**This is an outline to write from, not a draft.** Every line under a section
is a claim, not a paragraph. Each carries the appendix that supports it, the
number, the file under `results/` it comes from, and how strong the evidence
is. Three strengths are used:

- **measured** — a figure from a run with five seeds and a recorded deviation
- **small sample** — measured, but on 40 scenarios or 66 situations, or on a
  single cell, so the direction is supported and the level is not
- **code inspection** — established by reading the source, not by measurement

Page budget totals 8.0. Keep to it.

---

## Abstract — 0.25 pages

| Claim | Evidence | Number | Source | Strength |
| --- | --- | --- | --- | --- |
| Agentic triage systems ship hand designed epistemic guardrails that are rarely audited | none, framing | | | |
| We audit four such mechanisms in a working system and three do not do what they claim | L9.2, L9.7 | A effect −0.0030 ± 0.003, P effect 0.0000 | `results/ablation/main_effects_seed42.csv` | measured |
| One is inert, one is a clamp misdescribed as a persistence requirement, and the sensor level of a two level abstention design is never read | L9.2, L9.7, L9.8 | sensor effect +0.000000 | `results/two_level/two_level_seed42.json` | measured |
| A repair confirms the diagnosis: giving hypotheses stable identity makes persistence gate convergence for the first time | L10.1 | convergence 0.0000 to 0.1551 at threshold 0.30 | `results/repair/repair_summary_seed42.csv` | measured |
| We also report two evaluation hazards that invert the headline metric | L8.5, L9.6 | correct conclusions 0.22 to 0.50 under a defect | `results/clock_study/study_seed42.json` | measured |

---

## 1. Introduction — 0.75 pages

**Lead with the unknown_attack result.** It is the sharpest statement of the
problem: the mechanisms were designed for novel attacks and do almost nothing
there.

| Claim | Evidence | Number | Source | Strength |
| --- | --- | --- | --- | --- |
| On the unknown attack regime, the combined effect of the two working mechanisms is about −0.006 on abstention | L9.4 | U −0.0063 ± 0.013, S −0.0063 ± 0.013 | `results/ablation/regime_effects_seed42.csv` | measured |
| The same mechanisms move abstention by −0.55 and −0.45 on sparse evidence | L9.4 | 0.55, 0.45 | same | measured |
| So the guardrails work where evidence is scarce and not where the attack is unfamiliar, which is the opposite of the design intent | L9.4 | | | measured |
| Writing a guardrail is easy; verifying it is connected is not, and nobody checks | none, framing | | | |
| Contributions: an audit method, five mechanism findings, a repair experiment, two evaluation hazards | | | | |

Figure 1 goes here. `figures/fig1_architecture.pdf`.

---

## 2. Related work — 0.75 pages

| Claim | Evidence | Number | Source | Strength |
| --- | --- | --- | --- | --- |
| LLM assisted SOC and triage systems are proliferating and report end to end metrics | cite externally | | | |
| Selective prediction and the reject option are well founded in the classifier literature | cite externally, and L4 for our use of it | | | |
| Abstention in LLM reasoning is usually prompt level, not architectural | cite externally | | | |
| **None of this work audits whether its own guardrails are connected to anything** | the gap this paper fills | | | |
| Ablation is standard, but ablating a mechanism that is already inert returns a null that is read as unimportance rather than as disconnection | L9.3 | allon equals A equals P to four decimals | `results/ablation/cells_seed42.csv` | measured |

---

## 3. System under audit — 0.5 pages

Keep this short. The system is the instrument, not the contribution.

| Claim | Evidence | Number | Source | Strength |
| --- | --- | --- | --- | --- |
| Three layers: UNSW-NB15 sensor, LangGraph reasoning loop, dashboard | L1, SYSTEM.md | | | code inspection |
| The sensor is a deep ensemble with temperature scaling and a reject option | L3, L4 | abstains on 22.85% of sub-suite signals | `results/scenarios/sub_suite_manifest.json` | measured |
| An information barrier passes ten aggregate fields and no raw signal | L8.1.1 | ten fields | `nodes.py` assemble_context | code inspection |
| Four epistemic mechanisms sit in the loop: UNKNOWN, sanity gate, asymmetric decay, persistence | L2 | | `builder.py` | code inspection |
| The classifier is a sensor, not a contribution, and is characterised only to the extent the audit needs | L3 | | | |

---

## 4. Audit method — 1.0 pages

| Claim | Evidence | Number | Source | Strength |
| --- | --- | --- | --- | --- |
| A frozen scenario suite with injected ground truth, hash pinned | L7.1, L8.1.6 | suite `52b89293`, sub-suite `a2b37f29` | `results/scenarios/*_manifest.json` | measured |
| Four evidence regimes: clear, ambiguous, sparse, unknown attack | L7.1 | 10 scenarios each in the sub-suite | `results/scenarios/sub_suite_manifest.json` | measured |
| Each mechanism is removable from the graph, not merely weakened | L2.8 | node absent from the compiled topology | `builder.py` | code inspection |
| Metric tiers declared before the grid ran | L8.1.4 | four live, two dead, two compromised | `paper/EVIDENCE.md` L8.1.4 | measured, pre-registered |
| Model responses are content addressed and cached, so the grid is affordable and repeatable | L6.8, L9.1 | hit rate 0.9911 | `results/ablation/run_seed42.json` | measured |
| Every run writes a manifest pinning three commits, the seed, the model and the config | L6.9 | | `results/*/manifest_*.json` | measured |

---

## 5. Audit findings — 1.75 pages

**The five mechanism table is the centre of the paper.**

| Mechanism | Verdict | Number | Source | Strength |
| --- | --- | --- | --- | --- |
| UNKNOWN hypothesis (U) | works | abstention effect −0.0985 ± 0.008 | `results/ablation/main_effects_seed42.csv` | measured |
| Sanity gate (S) | works, overlaps U heavily | −0.0833 ± 0.012, U×S interaction +0.0833 ± 0.0115 | `results/ablation/interactions_seed42.csv` | measured |
| Asymmetric decay (A) | inert | −0.0030 ± 0.003, one deviation from zero | `results/ablation/main_effects_seed42.csv` | measured |
| Persistence (P) | a clamp, not a requirement | 0.0000 ± 0.000 at threshold 0.80 | same | measured |
| Belief inertia | no effect on convergence | +0.0000 | `results/convergence_isolation/isolation_seed42.json` | measured |
| Sensor reject option | never read by the reasoner | +0.000000 | `results/two_level/two_level_seed42.json` | measured |

Supporting claims:

| Claim | Evidence | Number | Source | Strength |
| --- | --- | --- | --- | --- |
| Sixteen configurations collapse to five distinct outcomes | L9.3 | | `results/ablation/cells_seed42.csv` | measured |
| No named hypothesis survives an iteration | L9.7 | 0 of 10068 | `results/ablation/allon_t080_42.jsonl` | measured |
| dominant_iterations is {0} across every terminated record | L9.7 | 4382 records | same | measured |
| Therefore a persistence requirement of two is unsatisfiable by construction | L9.7 | | `nodes.py` evaluate_hypotheses | code inspection |
| The clamp holds convergence at exactly the threshold minus 0.01 | L9.6 | 0.2900 at 0.30, 0.4900 at 0.50 | `results/ablation/threshold_sweep_seed42.csv` | measured |
| The abstained flag reaches no decision path | L9.8 | | `reasoning_engine.py`, `nodes.py` | code inspection |

Figure 3 goes here. Table III, the full sixteen row table, goes to the appendix.

---

## 6. Ablation as confirmation — 0.75 pages

**The ordering matters and must be stated.** The null effects were predicted
from code inspection before the grid finished, so the ablation confirms a
diagnosis rather than discovering one.

| Claim | Evidence | Number | Source | Strength |
| --- | --- | --- | --- | --- |
| The persistence clamp was identified in a mock rehearsal before any real model call was spent | commit `646c4d0`, 2026-09-20, message states every P enabled configuration sits at 0.2900 | | `git log` root repository | measured, timestamped |
| The grid then confirmed it at 9600 units against a real model | L9.6 | convergence 0.0000 with P enabled at every threshold | `results/ablation/threshold_sweep_seed42.csv` | measured |
| An ablation run without the prior diagnosis would have reported A and P as unimportant rather than as disconnected | L9.3 | | | argument |
| This is the methodological point: a null in an ablation is ambiguous between a mechanism that does little and one that is not wired in | | | | argument |

**Authors: cite the commit hash and date in the paper.** It is the only thing
that distinguishes a prediction from a post hoc story.

---

## 7. Repair experiment — 0.75 pages

| Claim | Evidence | Number | Source | Strength |
| --- | --- | --- | --- | --- |
| Giving a restated hypothesis the identity of its predecessor is a one switch change, off by default | L10.1 | | `nodes.py` _inherit_identity | code inspection |
| The repair is prompt neutral, so it costs nothing to run | L10.1 | cache hit rate 1.000000, 0 model calls, $0.00 | `results/repair/budget_full_seed42.json` | measured |
| Hypothesis recurrence rises from 0.0000 to 0.2045 | L10.1 | | `results/repair/repair_summary_seed42.csv` | measured |
| dominant_iterations rises from a maximum of 1 to a maximum of 3 | L10.1 | | same | measured |
| Persistence then gates convergence for the first time: 0.0000 to 0.1551 at threshold 0.30 | L10.1 | | same | measured |
| At 0.50 and 0.80 convergence stays at zero because confidences cap at 0.4620, below both | L10.1 | | same | measured |
| Verdict: the mechanism was correctly specified and incorrectly coupled | L10.1 | | | measured, small sample |
| The matching rule was fixed before the run and spot checked at 30 of 30 | L10.1 | threshold 0.70 | `results/repair/spot_check_verdict_seed42.json` | measured |

Figure 6 goes here.

---

## 8. Evaluation hazards — 1.0 pages

Three hazards, each generalisable beyond this system.

**8.1 Conflation inversion.**

| Claim | Evidence | Number | Source | Strength |
| --- | --- | --- | --- | --- |
| Evaluating staleness in host time while replaying archived events marks every situation quiet | L8.4 | quiet fraction 1.0000 in all five seeds | `results/clock_study/study_seed42.json` | measured |
| Trend detection collapses: the stable label is never emitted | L8.4 | 0 of 14445 iterations | same | measured |
| The headline metric *improves*: correct conclusions 0.22 to 0.50 | L8.5 | | same | measured |
| It is an abstention artefact. On the one regime requiring a conclusion, the defect makes the system worse | L8.5 | clear regime 0.130 to 0.080 | same | measured |
| The hazard has a threshold, not a gradient: 21% quiet changes nothing, 100% changes everything | L8.6 | | same | measured |

Figure 2 goes here.

**8.2 The convergence clamp.** Covered in section 5; cross reference only.

**8.3 Quiescence threshold.** Covered in 8.1; cross reference only.

---

## 9. Threats to validity — 0.5 pages

| Threat | Evidence | Strength |
| --- | --- | --- |
| The evaluation is synthetic throughout; no real deployment, no operator study | L7.7 | stated |
| 40 scenarios and 66 situations; per regime cells carry about 16 situations, a 95% interval of ±0.245 | L8.1.6 | measured |
| Five seeds support main effects and one interaction; no significance test is claimed | L9.5 | measured |
| The multi source condition is constructed, not observed | G9, still open | stated |
| The narrative a scenario is about is not recoverable from any aggregate the barrier exposes, so conclusion metrics are compromised | L8.1.2 | measured, lift −0.105 |
| Two of six categories share an identical detector signature, so they are indistinguishable by construction | L8.1.2 | code inspection |
| The LLM is non deterministic; caches are scoped per seed so replicates stay independent | L8.2 | measured |
| The classifier is a sensor, not a contribution | L3 | stated |

---

## 10. Conclusion — 0.25 pages

| Claim | Evidence | Strength |
| --- | --- | --- |
| Of four hand designed epistemic controls, one works, one works and overlaps it, one is inert, one is a clamp | L9.12 | measured |
| The two level abstention design is specified and not enacted | L9.8 | measured |
| A one switch repair confirms the persistence diagnosis | L10.1 | measured |
| Auditing whether a guardrail is connected should precede ablating it | | argument |

---

# Claims with weak evidence

The authors must either support these or soften them before submission.

1. **"The mechanisms were designed for novel attacks."** No design document
   says so. It is inferred from the UNKNOWN hypothesis existing. Either find
   the original intent in the commit history or soften to "are most needed
   there".
2. **Anything resting on `correct_conclusion_rate` for the clear regime.**
   L8.1.2 shows the narrative is unrecoverable, so the metric is measuring
   vocabulary overlap. Report it only with the caveat attached.
3. **`false_conclusion_rate` anywhere.** Same reason. It appears in L9.9 and
   should not reach the abstract or the conclusion.
4. **The repair result at thresholds 0.50 and 0.80.** It is a null, and the
   null has an alternative explanation: confidences cap at 0.4620 for reasons
   the experiment did not isolate.
5. **"Three of four did not survive being measured."** A is inert at one
   deviation, which is weaker than "does nothing". Say "one is inert within
   the resolution of five seeds".
6. **Generality of the conflation hazard.** Demonstrated on one system with
   one uniformly stale corpus. The threshold behaviour in L8.6 is a single
   observation at 21% versus 100%, with nothing in between.

# Findings to compress to one paragraph each

These are real and do not deserve a section.

1. **Narrative non-recoverability.** L8.1.1 and L8.1.2. One paragraph in
   threats to validity, carrying the −0.105 lift and the identical detector
   signature. It explains why the conclusion metrics are caveated and nothing
   more.
2. **Classifier characterisation.** L3 and L4 in full. One paragraph in
   section 3, giving the abstention fraction and pointing at the appendix.
   Temperature scaling failing to transfer is interesting and belongs in the
   other paper, not this one.
3. **The Amdahl scheduling result.** L7.9.8 and L8.2. One paragraph in the
   audit method: wall clock is floored by the longest unit, cross product
   scheduling is what makes a 9600 unit grid affordable, predicted 2009 s
   against actual 1980 s. It is a reproducibility engineering note, not a
   contribution.

# Findings to remove into a separate paper

**The validation transfer failure across L3.14, L4.2 and L5.2.** Three
independent instances of a calibration or selection procedure chosen on
validation data failing on test data, on the standard UNSW-NB15 protocol. It
has nothing to do with LLMs, agentic systems or epistemic control, and
including it would blunt this paper's argument. Its own skeleton is in
`paper/SKELETON_VALIDATION_TRANSFER.md`.

---

# Page budget

| Section | Pages |
| --- | --- |
| Abstract | 0.25 |
| 1 Introduction | 0.75 |
| 2 Related work | 0.75 |
| 3 System under audit | 0.50 |
| 4 Audit method | 1.00 |
| 5 Audit findings | 1.75 |
| 6 Ablation as confirmation | 0.75 |
| 7 Repair experiment | 0.75 |
| 8 Evaluation hazards | 1.00 |
| 9 Threats to validity | 0.50 |
| 10 Conclusion | 0.25 |
| **Total** | **8.25** |

**0.25 pages over.** Take it from Related work or from section 8.2 and 8.3,
which are cross references and could be two sentences inside section 5.

Figures: 1, 2, 3, 6. Four figures at roughly 0.3 pages each are inside the
section budgets above. Tables I baseline comparison and II component status
go in the appendix with Table III.
