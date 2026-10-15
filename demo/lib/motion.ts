"use client";

import { useSyncExternalStore } from "react";

const KEY = "enigma-demo-motion";

function preference() {
  try {
    const choice = localStorage.getItem(KEY);
    if (choice) return choice === "full";
  } catch {
    return !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }
  return !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function subscribe(notify: () => void) {
  const media = window.matchMedia("(prefers-reduced-motion: reduce)");
  media.addEventListener("change", notify);
  window.addEventListener(KEY, notify);
  return () => {
    media.removeEventListener("change", notify);
    window.removeEventListener(KEY, notify);
  };
}

export function useMotion() {
  const enabled = useSyncExternalStore(subscribe, preference, () => false);
  const toggle = () => {
    const next = !preference();
    try {
      localStorage.setItem(KEY, next ? "full" : "reduced");
    } catch {
      return;
    }
    window.dispatchEvent(new Event(KEY));
  };
  return { enabled, toggle };
}
