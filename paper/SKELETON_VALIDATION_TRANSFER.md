# SKELETON — Validation transfer failure on UNSW-NB15

**Working title.** When Validation Lies: Three Independent Failures of
Validation Selected Procedures to Transfer on the Standard UNSW-NB15
Protocol

**Why this is a separate paper.** It has nothing to do with LLMs, agentic
systems, or epistemic control. It is a finding about a dataset protocol that
hundreds of papers use. Folding it into the audit paper would blunt both.

**Target.** A short paper, 4 to 6 pages, or a workshop track.

---

## The claim

Three procedures were selected on a validation split and each failed to
transfer to the test split, in the same direction, on the same dataset, in
one project. That is not three coincidences; it is a property of how the
standard UNSW-NB15 protocol is used.

| Instance | What was selected on validation | What happened on test | Appendix | Source |
| --- | --- | --- | --- | --- |
| 1 | SMOTE degree as a hyperparameter | validation selection picked the worse configuration | L3.14 | `results/sensitivity_minimal/` |
| 2 | Temperature scaling for calibration | did not transfer and made test calibration worse | L4.2 | `results/calibration/` |
| 3 | Isotonic calibration for RF and XGBoost | failed to transfer, the third instance | L5.2 | `results/baselines/rf_calibration.json`, `xgb_calibration.json` |

---

## Sections

### 1. Introduction — 0.5 pages

| Claim | Evidence | Strength |
| --- | --- | --- |
| UNSW-NB15 is a standard benchmark with a widely mirrored train and test split | cite externally | |
| The split's filenames are inverted in the common distribution, which is already a known hazard | L1.3 | measured |
| We report a second, less visible hazard: procedures selected on a validation partition carved from the training set do not transfer | L3.14, L4.2, L5.2 | measured |

### 2. Protocol and setup — 0.75 pages

| Claim | Evidence | Strength |
| --- | --- | --- |
| Three way split: train, validation, test, with the test partition untouched | L3.4 | measured |
| Leakage audit removing four paths present in the original notebook | L3.2, L3.3 | measured |
| Five seeds, closed set and open set configurations | L3.7, L3.8 | measured |
| Deep ensemble, Random Forest and XGBoost all evaluated | L3, L5.1 | measured |

### 3. Instance one, SMOTE degree — 0.75 pages

| Claim | Evidence | Number | Strength |
| --- | --- | --- | --- |
| SMOTE degree was treated as a hyperparameter and chosen on validation | L3.6 | | measured |
| The configuration validation preferred performed worse on test | L3.14 | see appendix for the pair | measured |
| The sensitivity analysis was declared before running | L3.11 | | measured, pre-registered |

### 4. Instance two, temperature scaling — 0.75 pages

| Claim | Evidence | Strength |
| --- | --- | --- |
| Temperature fitted on validation | L4.1 | measured |
| Test calibration was worse after scaling than before | L4.2 | measured |
| This is the critical experiment and its answer was reported honestly at the time | L4.4 | measured |

### 5. Instance three, isotonic calibration — 0.5 pages

| Claim | Evidence | Strength |
| --- | --- | --- |
| Isotonic regression fitted on validation for RF and XGBoost | L5.2 | measured |
| Failed to transfer for both | L5.2 | measured |
| Three classifiers, three procedures, one direction | L3.14, L4.2, L5.2 | measured |

### 6. Why — 1.0 pages

This is the section that has to be written and is not yet supported.

| Candidate explanation | Status |
| --- | --- |
| The validation partition is drawn from the training file, and the official train and test files differ in distribution | **hypothesis, not tested** |
| Class balance differs between the official partitions | **checkable from `results/dataset_manifest.json`, not yet checked** |
| SMOTE resampling makes the validation split synthetic-majority, so it is not a sample of anything | **plausible, L3.6 touches it** |
| Small test sample | ruled out, 82332 rows |

**The authors must do this work.** Three observations of a failure are a
finding; without a mechanism it is an anecdote repeated three times.

### 7. Recommendation — 0.5 pages

| Claim | Strength |
| --- | --- |
| Report both the validation-selected and the test-best configuration | argument |
| Treat calibration transfer as a result to report, not a step to perform silently | argument |
| For this dataset specifically, select on a held out slice of the official test partition's distribution, or report that you did not | argument |

### 8. Threats — 0.25 pages

| Threat | Strength |
| --- | --- |
| One dataset, one project, one team | stated |
| The three instances share preprocessing, so they may not be independent | **this is the strongest objection and must be addressed** |
| No mechanism established, see section 6 | stated |

---

# What this skeleton needs before it is a paper

1. **A mechanism.** Section 6 is currently a list of guesses. Check the class
   balance and feature distribution between the official partitions from
   `results/dataset_manifest.json`.
2. **Independence.** The three instances share a preprocessing pipeline. If
   the cause is the pipeline rather than the protocol, this is a bug report
   about one project, not a finding about UNSW-NB15. Rerunning instance two
   on a different preprocessing path would settle it.
3. **A literature check.** If this is already known, the paper is a
   replication note. Nobody has looked.

Until 1 and 2 are done, this is not submittable. It is recorded here so the
finding is not lost when the audit paper drops it.
