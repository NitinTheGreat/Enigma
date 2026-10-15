"use client";

import { useState } from "react";
import { ArrowRight, RotateCcw } from "lucide-react";
import type { DemoData, Mechanism } from "@/lib/data";
import { mechanism } from "@/lib/data";
import { SCREENS } from "@/lib/copy";
import { fixed, percent, signed } from "@/lib/format";
import { Source, Term } from "./shared";

export function StartScreen({ onStart }: { onStart: () => void }) {
  return (
    <div className="screen start">
      <span className="eyebrow"><i />Enigma &middot; a guardrail audit</span>
      <h1 className="start-title">Specified but <em>not enacted</em></h1>
      <p className="start-question">
        When an AI security system&rsquo;s safety check does nothing, is it weak, or not connected at all?
      </p>
      <button className="button button-primary start-button" onClick={onStart}>
        Start <ArrowRight size={16} />
      </button>
      <ol className="start-steps" aria-label="Six steps">
        {SCREENS.slice(1).map((s, i) => (
          <li key={s.key}><span>{i + 1}</span>{s.short}</li>
        ))}
      </ol>
    </div>
  );
}

function Meter({ reading, tested, cut }: { reading: string; tested: boolean; cut: boolean }) {
  return (
    <svg className="circuit" viewBox="0 0 440 220" role="img"
      aria-label={cut ? "Guardrail with a cut wire, connected to a meter" : "Guardrail wired to a meter"}>
      <rect x="18" y="72" width="128" height="76" rx="2" className={`circuit-guard ${tested ? "is-removed" : ""}`} />
      <text x="82" y="116" textAnchor="middle" className="circuit-label">Guardrail</text>
      {cut ? (
        <>
          <path d="M146 110H196" className="circuit-wire" />
          <path d="M228 110H282" className="circuit-wire" />
          <path d="M204 98l16 24M220 98l-16 24" className="circuit-cut" />
        </>
      ) : (
        <path d="M146 110H282" className="circuit-wire" />
      )}
      <path d="M290 160a70 70 0 0 1 140 0" className="meter-arc" />
      <path d="M360 160V100" className={`meter-needle ${tested ? "is-tested" : ""}`} />
      <circle cx="360" cy="160" r="5" className="meter-hub" />
      <text x="360" y="196" textAnchor="middle" className="meter-reading">{tested ? reading : "–"}</text>
      <text x="360" y="214" textAnchor="middle" className="meter-caption">change</text>
    </svg>
  );
}

export function QuestionScreen({ data }: { data: DemoData }) {
  const [tested, setTested] = useState(false);
  const p = mechanism(data, "P");
  return (
    <div className="screen question">
      <span className="eyebrow"><i />1 &middot; The question <span className="tag">Illustration</span></span>
      <h2 className="screen-title">Two <Term term="guardrail">guardrails</Term>. One test.</h2>
      <div className="circuits">
        <figure className="circuit-card">
          <span className="tag">Wired, but weak</span>
          <Meter reading={fixed(0)} tested={tested} cut={false} />
        </figure>
        <figure className="circuit-card">
          <span className="tag tag-defect">Wire cut</span>
          <Meter reading={fixed(p.effect.value)} tested={tested} cut />
        </figure>
        {tested && <div className="stamp" role="status">Same result. Different reason.</div>}
      </div>
      <div className="question-actions">
        <button className="button button-dark" onClick={() => setTested((t) => !t)} data-testid="remove-guardrail">
          {tested ? <>Put it back <RotateCcw size={16} /></> : <>Remove guardrail <ArrowRight size={16} /></>}
        </button>
        <p className="question-line">A normal test cannot tell these apart. We check the wiring first.</p>
      </div>
    </div>
  );
}

type BlockKey = "traffic" | "sensor" | "grouping" | "barrier" | "loop" | "verdict" | "U" | "S" | "A" | "P" | "inertia";

type Callout = { title: string; sentence: string; number: string; caption: string; source?: { source: string; field: string }; fields?: string[]; badge?: Mechanism };

function calloutFor(data: DemoData, key: BlockKey): Callout {
  const sys = data.system;
  const allOn = data.configurations.configurations.find((c) => c.configuration === "allon");
  if (key === "traffic") return {
    title: "Network traffic", sentence: "Recorded attack and normal traffic is replayed, one flow at a time.",
    number: String(sys.signals.value), caption: `signals in ${sys.scenarios.value} test scenarios`, source: sys.signals,
  };
  if (key === "sensor") return {
    title: "ML sensor", sentence: `Flags traffic it is unsure about. It is unsure on ${percent(sys.sensor_unsure_fraction.value)} of signals.`,
    number: percent(sys.sensor_unsure_fraction.value), caption: `of signals marked unsure (${fixed(sys.sensor_unsure_fraction.value)})`,
    source: sys.sensor_unsure_fraction,
  };
  if (key === "grouping") return {
    title: "Grouping", sentence: "Signals about the same machine become one case.",
    number: String(sys.situations.value), caption: "cases to reason about", source: sys.situations,
  };
  if (key === "barrier") return {
    title: "Information barrier", sentence: "Only these ten summary numbers reach the AI. The unsure mark is not one of them.",
    number: String(sys.barrier_fields.value.length), caption: "fields cross", source: sys.barrier_fields,
    fields: sys.barrier_fields.value,
  };
  if (key === "loop") return {
    title: "AI reasoning loop", sentence: "An AI model proposes explanations. Guardrails test them, round by round.",
    number: String(sys.max_rounds.value), caption: "rounds at most", source: sys.max_rounds,
  };
  if (key === "verdict") return {
    title: "Verdict", sentence: "It names an attack, or it says ‘not sure’.",
    number: fixed(allOn?.overall.abstention_rate.value ?? 0), caption: "of cases end in ‘not sure’",
    source: allOn?.overall.abstention_rate,
  };
  const m = mechanism(data, key);
  return {
    title: `${m.name} (${m.key === "inertia" ? "brake" : m.key})`, sentence: m.plain,
    number: signed(m.effect.value), caption: m.key === "inertia" ? "change in settling when removed" : "change in ‘not sure’ when removed",
    source: m.effect, badge: m,
  };
}

function Node({ x, y, w, h, label, sub, k, selected, onSelect, mark }: {
  x: number; y: number; w: number; h: number; label: string; sub?: string; k: BlockKey;
  selected: BlockKey | null; onSelect: (k: BlockKey) => void; mark?: string;
}) {
  return (
    <g className={`node ${selected === k ? "is-selected" : ""}`} role="button" tabIndex={0}
      aria-label={`${label}${mark ? `, guardrail ${mark}` : ""}`} data-block={k}
      onClick={() => onSelect(k)} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect(k); } }}>
      <rect x={x} y={y} width={w} height={h} rx="2" />
      <text x={x + w / 2} y={y + (sub ? h / 2 - 4 : h / 2 + 6)} textAnchor="middle" className="node-label">{label}</text>
      {sub && <text x={x + w / 2} y={y + h / 2 + 16} textAnchor="middle" className="node-sub">{sub}</text>}
      {mark && <g className={`node-mark mark-${mark}`}><rect x={x + w - 26} y={y - 12} width="34" height="22" rx="2" /><text x={x + w - 9} y={y + 4} textAnchor="middle">{mark}</text></g>}
    </g>
  );
}

export function SystemScreen({ data }: { data: DemoData }) {
  const [selected, setSelected] = useState<BlockKey | null>(null);
  const callout = selected ? calloutFor(data, selected) : null;
  return (
    <div className="screen system">
      <span className="eyebrow"><i />2 &middot; The system</span>
      <h2 className="screen-title">From traffic to a <em>verdict</em></h2>
      <div className="pipeline-wrap">
        <svg className="pipeline" viewBox="0 0 1200 400" role="group" aria-label="The pipeline, click a block">
          <defs>
            <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
              <path d="M0 0L10 5L0 10z" fill="currentColor" />
            </marker>
          </defs>
          <g className="wire wire-data">
            <path d="M150 140H192" markerEnd="url(#arrow)" />
            <path d="M342 140H384" markerEnd="url(#arrow)" />
            <path d="M534 140H646" markerEnd="url(#arrow)" />
          </g>
          <g className="wire wire-defect">
            <path d="M267 176V340H556" />
            <path d="M560 328l22 24M582 328l-22 24" className="cut" />
            <text x="414" y="328" textAnchor="middle" className="wire-label">unsure mark</text>
          </g>
          <g className="barrier" role="button" tabIndex={0} aria-label="Information barrier" data-block="barrier"
            onClick={() => setSelected("barrier")} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setSelected("barrier"); } }}>
            <rect x="572" y="14" width="44" height="372" className="barrier-hit" />
            <path d="M594 18V382" className={`barrier-line ${selected === "barrier" ? "is-selected" : ""}`} />
            <text x="594" y="398" textAnchor="middle" className="barrier-label">10 fields cross</text>
          </g>
          <g className="loop" data-block="loop">
            <rect x="634" y="62" width="404" height="256" rx="2" className="loop-box" onClick={() => setSelected("loop")} />
            <text x="652" y="88" className="loop-title" onClick={() => setSelected("loop")}>AI reasoning loop</text>
          </g>
          <Node x={0} y={104} w={150} h={72} label="Network traffic" k="traffic" selected={selected} onSelect={setSelected} />
          <Node x={192} y={104} w={150} h={72} label="ML sensor" sub={`unsure on ${percent(data.system.sensor_unsure_fraction.value)}`} k="sensor" selected={selected} onSelect={setSelected} />
          <Node x={384} y={104} w={150} h={72} label="Grouping" k="grouping" selected={selected} onSelect={setSelected} />
          <g className="wire wire-flow">
            <path d="M770 140H792" markerEnd="url(#arrow)" />
            <path d="M902 140H924" markerEnd="url(#arrow)" />
            <path d="M979 168V212" markerEnd="url(#arrow)" />
            <path d="M924 250H902" markerEnd="url(#arrow)" />
            <path d="M792 250H770" markerEnd="url(#arrow)" />
            <path d="M714 222V178" markerEnd="url(#arrow)" />
            <path d="M714 278V300H1130V186" markerEnd="url(#arrow)" />
          </g>
          <Node x={656} y={112} w={114} h={56} label="Read" k="barrier" selected={selected} onSelect={setSelected} />
          <Node x={792} y={112} w={110} h={56} label="Propose" k="U" mark="U" selected={selected} onSelect={setSelected} />
          <Node x={924} y={112} w={110} h={56} label="Doubt" k="S" mark="S" selected={selected} onSelect={setSelected} />
          <Node x={924} y={222} w={110} h={56} label="Weigh" k="A" mark="A" selected={selected} onSelect={setSelected} />
          <Node x={792} y={222} w={110} h={56} label="Brake" k="inertia" selected={selected} onSelect={setSelected} />
          <Node x={656} y={222} w={114} h={56} label="Settle" k="P" mark="P" selected={selected} onSelect={setSelected} />
          <Node x={1060} y={104} w={140} h={72} label="Verdict" k="verdict" selected={selected} onSelect={setSelected} />
        </svg>
      </div>
      <div className="callout" aria-live="polite" data-testid="system-callout">
        {callout ? (
          <>
            <div className="callout-text">
              <span className="eyebrow">{callout.title}
                {callout.badge && <span className={`badge ${callout.badge.wired ? "badge-works" : "badge-defect"}`}>{callout.badge.wired ? "Wired" : "Not wired"}</span>}
              </span>
              <p>{callout.sentence}</p>
              {callout.fields && <ul className="field-list">{callout.fields.map((f) => <li key={f}>{f}</li>)}</ul>}
            </div>
            <div className="callout-number">
              <strong>{callout.number}</strong>
              <span>{callout.caption}</span>
              {callout.source && <Source source={callout.source.source} field={callout.source.field} />}
            </div>
          </>
        ) : (
          <p className="callout-hint">Click a block.</p>
        )}
      </div>
    </div>
  );
}
