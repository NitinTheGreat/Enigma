import type { Metadata, Viewport } from "next";
import "@fontsource-variable/archivo";
import "@fontsource/instrument-serif/latin-400-italic.css";
import "@fontsource/ibm-plex-mono/latin-400.css";
import "./globals.css";
import "./demo.css";

export const metadata: Metadata = {
  title: "Specified but Not Enacted, a reviewer walkthrough",
  description: "An offline walkthrough of the Enigma guardrail audit.",
};

export const viewport: Viewport = { width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en-GB"><body>{children}</body></html>;
}
