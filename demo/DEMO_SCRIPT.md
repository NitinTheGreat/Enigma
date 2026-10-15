# Demo script, five minutes

Start the demo with `npm run demo` inside `demo/`, open the address it prints,
press **F** for full screen. Press **P** at any time for these notes on screen;
the audience view hides them by default.

Keys: arrows move, **0** to **6** jump, **F** full screen, **P** presenter notes.
If anything misbehaves, present from `demo/fallback/`, one PNG per screen plus
the key interaction states.

| # | Screen | Time | Say this | Click this |
| --- | --- | --- | --- | --- |
| 0 | Start | 0:20 | "When an AI security system's safety check does nothing, is it weak, or not connected at all?" | **Start** |
| 1 | The question | 0:40 | "Here are two guardrails. One is weak. One has a cut wire. Watch what a normal test reports." | **Remove guardrail**. Both meters read 0.0000. Point at the stamp: "Same result. Different reason. So we check the wiring first." |
| 2 | The system | 0:50 | "Traffic goes into a trained sensor, is grouped into cases, and only ten summary numbers reach the AI." | Click **ML sensor**: "It is unsure on 23 % of signals." Point at the red cross: "That unsure mark stops at the barrier." |
| 3 | One case | 0:55 | "This is a real logged run, not a simulation. Watch the IDs." | **an attack it has never seen**, then **play**. At round 2: "Every idea got a new ID, so none can count as still leading. That is why persistence never fires." |
| 4 | Flip a guardrail | 1:10 | "This is the core. Every number here is measured, across 9600 runs." | Flip **Persistence**: nothing changes, "not connected". Flip **Sensor flag**: nothing changes. Turn both back on, flip **UNKNOWN**: 1.0000 to 0.0000. Then switch to **an attack it has never seen** and flip UNKNOWN again: it barely moves. |
| 5 | A false win | 0:35 | "Here is a bug that a scoreboard would reward." | **Clock bug on**. "The headline rises from 0.22 to 0.50. On clear evidence it falls from 0.130 to 0.080. A standard report would have picked the broken version." |
| 6 | What we found | 0:30 | "Two guardrails do the work. Two do nothing measurable. One safety signal is never read. Check the wiring before you measure the effect." | Nothing. Pause on the thesis. |

Total about 5 minutes. Screens 3 and 4 can stretch if the reviewer asks to try
a switch themselves.

## If the reviewer asks

- **"Where does this number come from?"** Every number on screen is read from
  `demo/public/data/*.json`, and each entry names the committed results file and
  field it came from. The small grey path under a number is that file. The
  files are built and checked against the paper by
  `scripts/build_demo_data.py`, which refuses to write anything if a value
  disagrees with the paper.
- **"Is the repair the contribution?"** No. Fixing the persistence wiring made
  it start to act, which confirms the defect. The contribution is the audit
  method: check that a guardrail is connected before measuring how much it
  helps.
- **"Why did the clear evidence case get the wrong call on screen 3?"** That
  case was picked by the same fixed rule as the paper's figure, the median case
  of its type. Its first analysis ended after one piece of evidence, and the
  system said not sure. We show it as it happened.
- **"How many seeds?"** Five. Limits are on the last screen: one system, a
  synthetic test suite, five seeds.
- **"Does it need the internet?"** No. It runs from a local static bundle, with
  no API key and no model calls. The test suite confirms zero external
  requests.
