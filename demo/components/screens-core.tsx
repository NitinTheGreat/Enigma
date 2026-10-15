"use client";

import { useEffect, useMemo, useState } from "react";
import { ArrowDown, ArrowUp, Info, Pause, Play, SkipBack, SkipForward } from "lucide-react";
import type { DemoData, RegimeKey, Trace } from "@/lib/data";
import { configurationFor, mechanism } from "@/lib/data";
import { AFFILIATION, AUTHORS, GUIDE, REGIME_LABEL } from "@/lib/copy";
import { exactZero, fixed, percent, shortId, signed } from "@/lib/format";
import { Source, Term } from "./shared";

const ORDERED_REGIMES: RegimeKey[] = ["clear", "ambiguous", "sparse", "unknown_attack"];

function narrate(trace: Trace, step: number): string {
  const rounds = trace.iterations;
  if (step >= rounds.length) {
    const verdict = trace.verdict === "abstained" ? "not sure" : "named an attack";
    if (trace.right_call) return `Verdict: ${verdict}. Right call for this kind of case.`;
    return trace.should_conclude
      ? `Verdict: ${verdict}. Wrong call: clear evidence deserved an answer.`
      : `Verdict: ${verdict}. Wrong call: this case should have stayed open.`;
  }
  const round = rounds[step];
  const unsure = fixed(round.unknown_confidence, 2);
  if (step === 0) return `Round 1: the AI proposed ${round.hypotheses.length} ideas. ‘Not sure’ starts at ${unsure}.`;
  const before = new Set(rounds[step - 1].hypotheses.map((h) => h.id));
  const kept = round.hypotheses.filter((h) => before.has(h.id)).length;
  if (kept === 0) {
    return step === 1
      ? `Round 2: the AI wrote new ideas. Every one got a new ID, so none can count as ‘still leading’.`
      : `Round ${step + 1}: new IDs again. ‘Not sure’ is at ${unsure}, and the score stays at ${fixed(round.convergence_score, 2)}.`;
  }
  return `Round ${step + 1}: ${kept} idea${kept === 1 ? "" : "s"} kept an ID. ‘Not sure’ is at ${unsure}.`;
}

function Gauge({ value, threshold }: { value: number; threshold: number }) {
  const angle = (v: number) => Math.PI * (1 - Math.min(Math.max(v, 0), 1));
  const point = (v: number, r: number) => [80 + r * Math.cos(angle(v)), 86 - r * Math.sin(angle(v))];
  const [nx, ny] = point(value, 56);
  const [t1x, t1y] = point(threshold, 50);
  const [t2x, t2y] = point(threshold, 72);
  return (
    <svg className="gauge" viewBox="0 0 160 112" role="img" aria-label={`Confidence score ${fixed(value, 2)}, needs ${fixed(threshold, 2)}`}>
      <path d="M14 86a66 66 0 0 1 132 0" className="gauge-arc" />
      <path d={`M${t1x} ${t1y}L${t2x} ${t2y}`} className="gauge-threshold" />
      <path d={`M80 86L${nx} ${ny}`} className="gauge-needle" />
      <circle cx="80" cy="86" r="4" className="gauge-hub" />
      <text x="80" y="108" textAnchor="middle" className="gauge-value">{fixed(value, 2)}</text>
    </svg>
  );
}

export function CaseScreen({ data }: { data: DemoData }) {
  const [regime, setRegime] = useState<RegimeKey>("unknown_attack");
  const [step, setStep] = useState(0);
  const [playing, setPlaying] = useState(false);
  const trace = data.traces.traces.find((t) => t.regime === regime) as Trace;
  const last = trace.iterations.length;
  const threshold = data.configurations.threshold;

  useEffect(() => {
    if (!playing) return;
    if (step >= last) { setPlaying(false); return; }
    const timer = window.setTimeout(() => setStep((s) => Math.min(s + 1, last)), 1700);
    return () => window.clearTimeout(timer);
  }, [playing, step, last]);

  const current = trace.iterations[Math.min(step, last - 1)];
  return (
    <div className="screen case">
      <div className="case-head">
        <div>
          <span className="eyebrow"><i />3 &middot; Watch one case <span className="tag">Real logged run</span></span>
          <h2 className="screen-title">One case, <em>three</em> rounds</h2>
        </div>
        <div className="tab-switch" role="tablist" aria-label="Kind of case">
          {ORDERED_REGIMES.map((r) => (
            <button key={r} role="tab" aria-selected={regime === r} data-regime={r}
              onClick={() => { setRegime(r); setStep(0); setPlaying(false); }}>{REGIME_LABEL[r]}</button>
          ))}
        </div>
      </div>
      <div className="case-body">
        <div className="rounds">
          {trace.iterations.map((round, i) => (
            <div key={round.iteration} className={`round ${i <= step ? "is-shown" : ""} ${i === Math.min(step, last - 1) ? "is-current" : ""}`}>
              <span className="round-name">Round {round.iteration}</span>
              <div className="chips">
                {i <= step && round.hypotheses.map((h) => (
                  <span key={h.id} className="chip" title={h.text || "Hypothesis"}>
                    <code>{shortId(h.id)}</code><b>{fixed(h.confidence, 2)}</b>
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
        <div className="meters">
          <div className="unknown-meter">
            <span className="meter-name"><Term term="unknown">UNKNOWN</Term></span>
            <div className="unknown-track"><div className="unknown-fill" style={{ height: `${current.unknown_confidence * 100}%` }} /></div>
            <span className="meter-value">{fixed(current.unknown_confidence, 2)}</span>
          </div>
          <div className="gauge-meter">
            <span className="meter-name"><Term term="convergence">Confidence score</Term></span>
            <Gauge value={current.convergence_score} threshold={threshold} />
            <span className="meter-sub">needs {fixed(threshold, 2)}</span>
          </div>
        </div>
      </div>
      <div className="case-foot">
        <p className={`narrator ${step >= last ? (trace.right_call ? "is-right" : "is-wrong") : ""}`} data-testid="narrator">{narrate(trace, step)}</p>
        <div className="player">
          <button className="icon-button" onClick={() => { setPlaying(false); setStep((s) => Math.max(s - 1, 0)); }} aria-label="Back one round"><SkipBack size={16} /></button>
          <button className="icon-button player-main" onClick={() => { if (step >= last) setStep(0); setPlaying((p) => !p); }} aria-label={playing ? "Pause" : "Play"}>
            {playing ? <Pause size={18} /> : <Play size={18} />}
          </button>
          <button className="icon-button" onClick={() => { setPlaying(false); setStep((s) => Math.min(s + 1, last)); }} aria-label="Step forward" data-testid="case-step"><SkipForward size={16} /></button>
        </div>
      </div>
    </div>
  );
}

type FlipKey = "U" | "S" | "A" | "P" | "flag";
const FLIP_ORDER: FlipKey[] = ["U", "S", "A", "P", "flag"];
const FLIP_NAME: Record<FlipKey, React.ReactNode> = {
  U: <>UNKNOWN <Term term="unknown"><Info size={13} aria-label="What UNKNOWN means" /></Term></>,
  S: "Sanity gate",
  A: "Decay",
  P: "Persistence",
  flag: "Sensor flag",
};
const FLIP_TEXT: Record<FlipKey, string> = { U: "UNKNOWN", S: "Sanity gate", A: "Decay", P: "Persistence", flag: "Sensor flag" };

export function FlipScreen({ data }: { data: DemoData }) {
  const [on, setOn] = useState<Record<FlipKey, boolean>>({ U: true, S: true, A: true, P: true, flag: true });
  const [regime, setRegime] = useState<"sparse" | "unknown_attack">("sparse");
  const [last, setLast] = useState<{ key: FlipKey; delta: number; turnedOff: boolean } | null>(null);

  const removed = (state: Record<FlipKey, boolean>) => (["U", "S", "A", "P"] as const).filter((k) => !state[k]);
  const rate = (state: Record<FlipKey, boolean>, r: RegimeKey) =>
    configurationFor(data, removed(state)).per_regime[r].abstention_rate;
  const value = rate(on, regime);
  const overall = configurationFor(data, removed(on)).overall.abstention_rate.value;

  function flip(key: FlipKey) {
    const next = { ...on, [key]: !on[key] };
    const delta = rate(next, regime).value - rate(on, regime).value;
    setOn(next);
    setLast({ key, delta, turnedOff: !next[key] });
  }

  const message = useMemo(() => {
    if (!last) return "Flip a switch.";
    const action = last.turnedOff ? "Removing" : "Restoring";
    if (Math.abs(last.delta) < 1e-9) {
      if (last.key === "P" || last.key === "flag") return "Nothing changed. Is it weak, or not connected? The audit says: not connected.";
      if (last.key === "A") return "Nothing changed. Decay is wired in, but too weak to show.";
      return `${action} ${FLIP_TEXT[last.key]} changed nothing here, because UNKNOWN is already off.`;
    }
    return `${action} ${FLIP_TEXT[last.key]} moved it by ${signed(last.delta)}.`;
  }, [last]);

  return (
    <div className="screen flip">
      <span className="eyebrow"><i />4 &middot; Flip a <Term term="guardrail">guardrail</Term> <span className="tag">Measured</span></span>
      <h2 className="screen-title">Switch one <em>off</em>.</h2>
      <div className="flip-body">
        <div className="switches" role="group" aria-label="Guardrails">
          {FLIP_ORDER.map((key) => {
            const m = mechanism(data, key);
            return (
              <div key={key} className={`switch-row ${on[key] ? "" : "is-off"}`}>
                <button role="switch" aria-checked={on[key]} className="switch" onClick={() => flip(key)} data-switch={key}>
                  <span className="switch-track"><span className="switch-thumb" /></span>
                  <span className="switch-name">{FLIP_NAME[key]}</span>
                </button>
                <span className={`badge ${m.wired ? "badge-works" : "badge-defect"}`} title={`Audit verdict: ${m.verdict}`}>{m.wired ? "Wired" : "Not wired"}</span>
              </div>
            );
          })}
        </div>
        <div className="readout">
          <div className="tab-switch" role="tablist" aria-label="Kind of case">
            {(["sparse", "unknown_attack"] as const).map((r) => (
              <button key={r} role="tab" aria-selected={regime === r} data-regime={r} onClick={() => { setRegime(r); setLast(null); }}>{REGIME_LABEL[r]}</button>
            ))}
          </div>
          <strong className="big-number" data-testid="flip-number">{fixed(value.value)}</strong>
          <div className="bar"><div className="bar-fill" style={{ width: `${value.value * 100}%` }} /></div>
          <span className="readout-caption">of cases end in <Term term="abstain">&lsquo;not sure&rsquo;</Term></span>
          <p className={`flip-message ${last && Math.abs(last.delta) < 1e-9 && (last.key === "P" || last.key === "flag") ? "is-defect" : ""}`} data-testid="flip-message" aria-live="polite">{message}</p>
          <span className="readout-foot">All cases: {fixed(overall)} <Source source={value.source} field={value.field} /></span>
        </div>
      </div>
    </div>
  );
}

export function ClockScreen({ data }: { data: DemoData }) {
  const [bug, setBug] = useState(false);
  const off = data.clock.modes[data.clock.bug_off];
  const onMode = data.clock.modes[data.clock.bug_on];
  const mode = bug ? onMode : off;
  return (
    <div className="screen clock">
      <span className="eyebrow"><i />5 &middot; A false win <span className="tag">Measured</span></span>
      <h2 className="screen-title">A bug that looks like <em>progress</em></h2>
      <button role="switch" aria-checked={bug} className={`clock-switch ${bug ? "is-on" : ""}`} onClick={() => setBug((b) => !b)} data-testid="clock-switch">
        <span className="switch-track"><span className="switch-thumb" /></span>
        <span>Clock bug {bug ? "on" : "off"}</span>
      </button>
      <div className="clock-stats">
        <div>
          <span className="eyebrow">Headline score</span>
          <strong className="stat" data-testid="clock-headline">{fixed(mode.correct_conclusion_rate.value, 2)}</strong>
          {bug && <span className="delta delta-up"><ArrowUp size={14} />looks like progress</span>}
          <p>All cases.</p>
        </div>
        <div>
          <span className="eyebrow">Clear evidence score</span>
          <strong className="stat" data-testid="clock-clear">{fixed(mode.clear_regime_correct_rate.value, 3)}</strong>
          {bug && <span className="delta delta-down"><ArrowDown size={14} />got worse</span>}
          <p>Cases needing an answer.</p>
        </div>
        <div>
          <span className="eyebrow">Cases marked quiet</span>
          <strong className="stat">{percent(mode.quiet_fraction.value)}</strong>
          <p>Cases that look finished.</p>
        </div>
      </div>
      <p className="clock-line">A standard report would have picked the broken version.</p>
    </div>
  );
}

export function FindingsScreen({ data }: { data: DemoData }) {
  const core = data.verdicts.mechanisms.filter((m) => ["U", "S", "A", "P"].includes(m.key));
  const working = core.filter((m) => m.verdict.startsWith("works"));
  const idle = core.filter((m) => !m.verdict.startsWith("works"));
  const unread = data.verdicts.mechanisms.filter((m) => m.key === "flag");
  const flag = unread[0];
  return (
    <div className="screen findings">
      <span className="eyebrow"><i />6 &middot; What we found</span>
      <div className="cards">
        <div className="card card-works">
          <strong>{working.length}</strong>
          <span>guardrails do the work</span>
          <small>UNKNOWN, sanity gate</small>
        </div>
        <div className="card card-inert">
          <strong>{idle.length}</strong>
          <span>do nothing measurable</span>
          <small>decay, persistence</small>
        </div>
        <div className="card card-defect">
          <strong>{unread.length}</strong>
          <span>safety signal is never read</span>
          <small>sensor flag, effect {exactZero(flag.effect.value)}</small>
        </div>
      </div>
      <p className="thesis">Check the wiring <em>before</em> you measure the effect.</p>
      <p className="limits">One system. Synthetic test suite. Five seeds.</p>
      <p className="credits">{AUTHORS.join(", ")} <span>&middot; Guide: {GUIDE} &middot; {AFFILIATION}</span></p>
    </div>
  );
}
