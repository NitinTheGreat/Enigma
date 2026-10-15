import type { RegimeKey } from "./data";

export const SCREENS = [
  { key: "start", short: "Start" },
  { key: "question", short: "The question" },
  { key: "system", short: "The system" },
  { key: "case", short: "One case" },
  { key: "flip", short: "Flip a guardrail" },
  { key: "clock", short: "A false win" },
  { key: "findings", short: "What we found" },
] as const;

export const REGIME_LABEL: Record<RegimeKey, string> = {
  clear: "clear evidence",
  ambiguous: "mixed evidence",
  sparse: "too little evidence",
  unknown_attack: "an attack it has never seen",
};

export const GLOSSARY = {
  guardrail: "A safety check added to the AI, meant to stop it jumping to conclusions.",
  abstain: "To answer ‘not sure’ instead of naming an attack.",
  unknown: "A standing ‘I do not know’ option that the AI can never delete.",
  ablation: "Switching one part off to see what changes.",
  convergence: "The point where the AI is confident enough to give an answer.",
} as const;

export const NOTES: string[] = [
  "This demo is about safety checks inside an AI security system. The question is simple: when a check seems to do nothing, why? Press Start.",
  "Click Remove guardrail. Both meters read zero. The left check is weak; the right one is not even connected. A normal test cannot tell them apart.",
  "Traffic goes into a trained sensor, is grouped into cases, and only ten summary numbers reach the AI. Click the sensor: its unsure mark stops at the barrier.",
  "This is a real logged run, not a simulation. Pick an attack it has never seen and press play. Watch the IDs: every round they are new.",
  "This is the core. Flip persistence: nothing changes. Flip the sensor flag: nothing changes. Then flip UNKNOWN on too little evidence and watch it drop.",
  "Turn the clock bug on. The headline score jumps, which looks like progress. On clear evidence it gets worse. A normal report would have shipped the bug.",
  "Two guardrails do the work, two do nothing measurable, one signal is never read. Fixing the persistence wiring made it act, which confirms the diagnosis.",
];

export const WHY: string[][] = [
  [
    "Security teams are adding AI agents with built in safety checks.",
    "Papers describe these checks. Few test whether they actually run.",
    "This demo walks through one real system we audited.",
  ],
  [
    "Switching a part off and measuring the change is called an ablation.",
    "If nothing changes, the part may be weak, or it may never run at all.",
    "The two need different fixes, so the reading alone is not enough.",
    "This screen is an illustration. The measured cases are on screen 4.",
  ],
  [
    "The AI never sees raw traffic, only ten summary numbers.",
    "The sensor’s unsure mark is recorded, but it is not one of the ten.",
    "So the system claims two layers of caution. In practice it has one.",
  ],
  [
    "Each run lasts up to three rounds: propose ideas, test them, score confidence.",
    "Persistence should wait for one idea to lead twice in a row.",
    "Every round rebuilds the list with new IDs, so that never happens.",
    "Each case is the median case of its type, picked by a fixed rule.",
  ],
  [
    "Every number is measured: 16 settings, five repeats, 9600 runs in all.",
    "Persistence and the sensor flag change nothing, to every decimal place.",
    "As a check, we repaired the persistence wiring. It then started to act.",
  ],
  [
    "The bug made the system think every case had gone quiet.",
    "So it said ‘not sure’ far more. Most case types reward that, so the score rose.",
    "On cases that needed an answer, it did worse. One number hid this.",
  ],
  [
    "Limits: one system, a synthetic test suite, five repeats per setting.",
    "Every number here is read from a committed results file.",
    "The persistence repair confirms the diagnosis. The audit method is the contribution.",
  ],
];

export const AUTHORS = ["Abhay Mahantesh Zalaki", "Guneet Kaur Arora", "Nitin Kumar Pandey"];
export const GUIDE = "Dr. Ebenezer Juliet";
export const AFFILIATION = "VIT Vellore";
