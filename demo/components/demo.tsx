"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { ArrowLeft, ArrowRight } from "lucide-react";
import { useDemoData } from "@/lib/data";
import { useMotion } from "@/lib/motion";
import { NOTES, SCREENS, WHY } from "@/lib/copy";
import { NotesPanel, TopBar, WhyDrawer } from "./shared";
import { QuestionScreen, StartScreen, SystemScreen } from "./screens-intro";
import { CaseScreen, ClockScreen, FindingsScreen, FlipScreen } from "./screens-core";

gsap.registerPlugin(useGSAP);

const LAST = SCREENS.length - 1;

function screenFromHash(): number {
  if (typeof window === "undefined") return 0;
  const n = Number(window.location.hash.replace("#", ""));
  return Number.isInteger(n) && n >= 0 && n <= LAST ? n : 0;
}

export default function Demo() {
  const { data, error } = useDemoData();
  const { enabled: motion, toggle: toggleMotion } = useMotion();
  const [screen, setScreen] = useState(0);
  const [notes, setNotes] = useState(false);
  const [why, setWhy] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  const stage = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const sync = () => { setScreen(screenFromHash()); setWhy(false); };
    sync();
    window.addEventListener("hashchange", sync);
    return () => window.removeEventListener("hashchange", sync);
  }, []);
  useEffect(() => { document.documentElement.dataset.motion = motion ? "full" : "reduced"; }, [motion]);

  const go = useCallback((index: number) => {
    const next = Math.min(Math.max(index, 0), LAST);
    setScreen(next);
    setWhy(false);
    window.history.replaceState(null, "", `#${next}`);
  }, []);

  const toggleFullscreen = useCallback(() => {
    if (document.fullscreenElement) document.exitFullscreen().catch(() => undefined);
    else document.documentElement.requestFullscreen().catch(() => undefined);
  }, []);

  useEffect(() => {
    const sync = () => setFullscreen(Boolean(document.fullscreenElement));
    document.addEventListener("fullscreenchange", sync);
    return () => document.removeEventListener("fullscreenchange", sync);
  }, []);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.ctrlKey || event.metaKey || event.altKey) return;
      const target = event.target as HTMLElement | null;
      if (target && ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)) return;
      if (event.key === "ArrowRight" || event.key === "PageDown") { event.preventDefault(); go(screen + 1); return; }
      if (event.key === "ArrowLeft" || event.key === "PageUp") { event.preventDefault(); go(screen - 1); return; }
      if (/^[0-6]$/.test(event.key)) { go(Number(event.key)); return; }
      if (event.key === "f" || event.key === "F") { toggleFullscreen(); return; }
      if (event.key === "p" || event.key === "P") { setNotes((n) => !n); return; }
      if (event.key === "Escape") { setWhy(false); setNotes(false); }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [screen, go, toggleFullscreen]);

  useGSAP(() => {
    if (!motion || !stage.current) return;
    gsap.fromTo(stage.current, { opacity: 0, y: 12 }, { opacity: 1, y: 0, duration: .55, ease: "power2.out", clearProps: "all" });
  }, { dependencies: [screen, motion, data], revertOnUpdate: true });

  return (
    <div className={`demo ${notes ? "has-notes" : ""}`} data-screen={screen}>
      <TopBar screen={screen} onJump={go} notesOpen={notes} onNotes={() => setNotes((n) => !n)}
        fullscreen={fullscreen} onFullscreen={toggleFullscreen} motion={motion} onMotion={toggleMotion} />
      <main className="stage-wrap" id="main">
        <div className="stage" ref={stage} key={screen} data-testid={`screen-${screen}`}>
          {error && <p className="load-error">Could not load the measured results: {error}</p>}
          {!error && !data && <p className="loading">Loading measured results</p>}
          {data && screen === 0 && <StartScreen onStart={() => go(1)} />}
          {data && screen === 1 && <QuestionScreen data={data} />}
          {data && screen === 2 && <SystemScreen data={data} />}
          {data && screen === 3 && <CaseScreen data={data} />}
          {data && screen === 4 && <FlipScreen data={data} />}
          {data && screen === 5 && <ClockScreen data={data} />}
          {data && screen === 6 && <FindingsScreen data={data} />}
        </div>
      </main>
      <footer className="footbar">
        <div className="footbar-left">
          <WhyDrawer lines={WHY[screen]} open={why} onToggle={() => setWhy((w) => !w)} />
          <span className="mono muted counter">{screen} / {LAST}</span>
        </div>
        <div className="pager">
          <button className="button button-outline pager-button" onClick={() => go(screen - 1)} disabled={screen === 0} aria-label="Previous screen">
            <ArrowLeft size={15} />Back
          </button>
          <button className="button button-dark pager-button" onClick={() => go(screen + 1)} disabled={screen === LAST} aria-label="Next screen">
            Next<ArrowRight size={15} />
          </button>
        </div>
      </footer>
      <NotesPanel open={notes} screen={screen} note={NOTES[screen]} onClose={() => setNotes(false)} />
    </div>
  );
}
