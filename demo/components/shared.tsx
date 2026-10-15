"use client";

import { ChevronUp, Maximize, Minimize, NotebookText, Pause, Play, X } from "lucide-react";
import { GLOSSARY, SCREENS } from "@/lib/copy";

type GlossaryKey = keyof typeof GLOSSARY;

export function Term({ term, children }: { term: GlossaryKey; children: React.ReactNode }) {
  return (
    <span className="term" tabIndex={0} data-term={term}>
      {children}
      <span className="term-tip" role="tooltip">{GLOSSARY[term]}</span>
    </span>
  );
}

export function BrandMark({ className = "" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 44 44" fill="none" aria-hidden="true">
      <path d="M3 22h12" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" />
      <path d="M29 22h12" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" />
      <path d="M17 16l4 12M23 16l4 12" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" />
      <circle cx="3" cy="22" r="2.6" fill="currentColor" />
      <circle cx="41" cy="22" r="2.6" fill="currentColor" />
    </svg>
  );
}

export function TopBar({ screen, onJump, notesOpen, onNotes, fullscreen, onFullscreen, motion, onMotion }: {
  screen: number;
  onJump: (index: number) => void;
  notesOpen: boolean;
  onNotes: () => void;
  fullscreen: boolean;
  onFullscreen: () => void;
  motion: boolean;
  onMotion: () => void;
}) {
  return (
    <header className="topbar">
      <button className="brand" onClick={() => onJump(0)} aria-label="Back to start">
        <BrandMark className="brand-mark" />
        <span>Enigma <span className="brand-light">audit</span><small>SPECIFIED BUT NOT ENACTED</small></span>
      </button>
      <nav className="progress" aria-label="Demo steps">
        {SCREENS.slice(1).map((item, i) => {
          const index = i + 1;
          const state = index === screen ? "current" : index < screen ? "done" : "todo";
          return (
            <button key={item.key} className={`progress-step is-${state}`} onClick={() => onJump(index)}
              aria-current={index === screen ? "step" : undefined}>
              <span className="progress-number">{index}</span>
              <span className="progress-label">{item.short}</span>
            </button>
          );
        })}
      </nav>
      <div className="tools">
        <button className="tool" onClick={onMotion} aria-pressed={!motion} title="Motion on or off">
          {motion ? <Pause size={15} /> : <Play size={15} />}<span>Motion</span>
        </button>
        <button className="tool" onClick={onNotes} aria-pressed={notesOpen} title="Presenter notes (P)">
          <NotebookText size={15} /><span>Notes</span><kbd>P</kbd>
        </button>
        <button className="tool" onClick={onFullscreen} aria-pressed={fullscreen} title="Full screen (F)">
          {fullscreen ? <Minimize size={15} /> : <Maximize size={15} />}<span>Full screen</span><kbd>F</kbd>
        </button>
      </div>
    </header>
  );
}

export function WhyDrawer({ lines, open, onToggle }: { lines: string[]; open: boolean; onToggle: () => void }) {
  return (
    <>
      <button className="why-toggle" onClick={onToggle} aria-expanded={open} aria-controls="why-panel">
        <ChevronUp size={15} className={open ? "is-open" : ""} />Why this matters
      </button>
      <section id="why-panel" className="why-panel" hidden={!open} aria-label="Why this matters">
        <div className="why-head">
          <span className="eyebrow"><i />Why this matters</span>
          <button className="icon-button" onClick={onToggle} aria-label="Close"><X size={16} /></button>
        </div>
        <ul>{lines.map((line) => <li key={line}>{line}</li>)}</ul>
      </section>
    </>
  );
}

export function NotesPanel({ open, screen, note, onClose }: { open: boolean; screen: number; note: string; onClose: () => void }) {
  return (
    <aside className="notes" hidden={!open} aria-label="Presenter notes">
      <div className="notes-head">
        <span className="eyebrow">Presenter notes, screen {screen}</span>
        <button className="icon-button" onClick={onClose} aria-label="Close notes"><X size={16} /></button>
      </div>
      <p>{note}</p>
      <p className="notes-keys">Arrows move. 0 to 6 jump. F full screen. P hides these notes.</p>
    </aside>
  );
}

export function Source({ source, field }: { source: string; field: string }) {
  return <span className="source" title={`${source}\n${field}`}>{source}</span>;
}
