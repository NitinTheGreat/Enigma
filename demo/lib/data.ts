"use client";

import { useEffect, useState } from "react";

export type Sourced<T = number> = { value: T; source: string; field: string };

export type Mechanism = {
  key: "U" | "S" | "A" | "P" | "flag" | "inertia";
  name: string;
  verdict: string;
  wired: boolean;
  plain: string;
  effect: Sourced;
  sd?: Sourced;
  effect_guardrails_off?: Sourced;
};

export type RegimeKey = "clear" | "ambiguous" | "sparse" | "unknown_attack";

export type Configuration = {
  configuration: string;
  removed: string[];
  kept: string[];
  overall: { abstention_rate: Sourced; premature_convergence_rate: Sourced };
  per_regime: Record<RegimeKey, { abstention_rate: Sourced; premature_convergence_rate: Sourced }>;
};

export type ClockMode = {
  quiet_fraction: Sourced;
  abstention_rate: Sourced;
  correct_conclusion_rate: Sourced;
  clear_regime_correct_rate: Sourced;
  trend_labels_seen: Sourced;
};

export type TraceHypothesis = { id: string; confidence: number; status: string; text: string };

export type TraceIteration = {
  iteration: number;
  evidence_count: number;
  unknown_confidence: number;
  convergence_score: number;
  dominant_hypothesis_id: string;
  dominant_iterations: number;
  terminated: boolean;
  termination_reason: string | null;
  hypotheses: TraceHypothesis[];
};

export type Trace = {
  regime: RegimeKey;
  situation_id: string;
  scenario_id: string;
  evidence_count_at_end: number;
  should_conclude: boolean;
  verdict: "abstained" | "concluded";
  right_call: boolean;
  termination_reason: string;
  iterations: TraceIteration[];
};

export type SensorModel = {
  key: string;
  label: string;
  accuracy: Sourced;
  macro_f1: Sourced;
  false_positive_rate: Sourced;
  unknown_attack_auroc: Sourced;
};

export type DemoData = {
  verdicts: { mechanisms: Mechanism[]; verdict_text_source: string };
  configurations: { threshold: number; configurations: Configuration[] };
  regime_effects: { effects: Record<"U" | "S", Record<RegimeKey, { effect: Sourced; sd: Sourced }>> };
  clock: { bug_off: string; bug_on: string; modes: Record<string, ClockMode> };
  repair: {
    threshold: number;
    baseline: { recurrence: Sourced; convergence_fraction: Sourced; max_convergence: Sourced };
    repair: { recurrence: Sourced; convergence_fraction: Sourced; max_convergence: Sourced };
  };
  sensor: { models: SensorModel[] };
  system: {
    scenarios: Sourced;
    signals: Sourced;
    situations: Sourced;
    sensor_unsure_fraction: Sourced;
    suite_hash: Sourced<string>;
    barrier_fields: Sourced<string[]>;
    max_rounds: Sourced;
  };
  traces: { source: string; rule: string; traces: Trace[] };
};

const FILES = ["verdicts", "configurations", "regime_effects", "clock", "repair", "sensor", "system", "traces"] as const;

export function useDemoData() {
  const [data, setData] = useState<DemoData | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    Promise.all(FILES.map((name) => fetch(`data/${name}.json`).then((r) => {
      if (!r.ok) throw new Error(`data/${name}.json returned ${r.status}`);
      return r.json();
    })))
      .then((parts) => {
        if (!active) return;
        const assembled = Object.fromEntries(FILES.map((name, i) => [name, parts[i]])) as DemoData;
        setData(assembled);
      })
      .catch((reason: unknown) => {
        if (active) setError(reason instanceof Error ? reason.message : String(reason));
      });
    return () => { active = false; };
  }, []);
  return { data, error };
}

export function configurationFor(data: DemoData, removed: string[]): Configuration {
  const name = removed.length === 0 ? "allon" : ["U", "S", "A", "P"].filter((s) => removed.includes(s)).join("");
  const found = data.configurations.configurations.find((c) => c.configuration === name);
  if (!found) throw new Error(`configuration ${name} missing from data`);
  return found;
}

export function mechanism(data: DemoData, key: Mechanism["key"]): Mechanism {
  const found = data.verdicts.mechanisms.find((m) => m.key === key);
  if (!found) throw new Error(`mechanism ${key} missing from data`);
  return found;
}
