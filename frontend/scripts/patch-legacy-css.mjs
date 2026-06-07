import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const dist = join(root, "dist");
const indexPath = join(dist, "index.html");
const legacyCssPath = join(dist, "legacy-compat.css");

const legacyCss = `/* DataAgent legacy CSS fallback — injected only when browser lacks oklch() support.
   PostCSS already provides @supports-guarded rgb() fallbacks for all colors.
   This file handles the remaining cases:
     - dynamic color-mix() (currentcolor / var() cannot be resolved at build time)
     - backdrop-filter glass effects → solid bg fallback
     - inline-style var() references that bypass CSS cascade
   Keep this file concrete: no custom properties, no modern color functions. */

html,
body,
#root {
  height: 100%;
  min-height: 100%;
  margin: 0;
}

* {
  box-sizing: border-box;
}

body {
  background: #fbfaf7;
  color: #0f0e0c;
  font-family: Inter, "Noto Sans SC", "PingFang SC", "Microsoft YaHei", Arial, sans-serif;
}

button,
input,
textarea,
select {
  font-family: Inter, "Noto Sans SC", "PingFang SC", "Microsoft YaHei", Arial, sans-serif;
}

button {
  border: 0;
  background: transparent;
  color: #2c2a25;
}

input,
textarea {
  color: #0f0e0c;
}

img,
svg {
  max-width: 100%;
}

.block { display: block !important; }
.inline-block { display: inline-block !important; }
.hidden { display: none !important; }
.fixed { position: fixed !important; }
.absolute { position: absolute !important; }
.relative { position: relative !important; }
.inset-0 { top: 0 !important; right: 0 !important; bottom: 0 !important; left: 0 !important; }
.inset-x-0 { right: 0 !important; left: 0 !important; }
.inset-y-0 { top: 0 !important; bottom: 0 !important; }
.top-0 { top: 0 !important; }
.right-0 { right: 0 !important; }
.bottom-0 { bottom: 0 !important; }
.left-0 { left: 0 !important; }
.top-1\\/2 { top: 50% !important; }
.top-full { top: 100% !important; }
.bottom-full { bottom: 100% !important; }
.z-20 { z-index: 20 !important; }
.z-30 { z-index: 30 !important; }
.z-40 { z-index: 40 !important; }
.z-50 { z-index: 50 !important; }

.flex {
  display: -webkit-box !important;
  display: -ms-flexbox !important;
  display: flex !important;
}

.inline-flex {
  display: -webkit-inline-box !important;
  display: -ms-inline-flexbox !important;
  display: inline-flex !important;
}

.flex-col {
  -webkit-box-orient: vertical !important;
  -webkit-box-direction: normal !important;
  -ms-flex-direction: column !important;
  flex-direction: column !important;
}

.flex-row {
  -webkit-box-orient: horizontal !important;
  -webkit-box-direction: normal !important;
  -ms-flex-direction: row !important;
  flex-direction: row !important;
}

.flex-1 {
  -webkit-box-flex: 1 !important;
  -ms-flex: 1 1 0% !important;
  flex: 1 1 0% !important;
}

.flex-shrink-0 {
  -ms-flex-negative: 0 !important;
  flex-shrink: 0 !important;
}

.items-center {
  -webkit-box-align: center !important;
  -ms-flex-align: center !important;
  align-items: center !important;
}

.items-start {
  -webkit-box-align: start !important;
  -ms-flex-align: start !important;
  align-items: flex-start !important;
}

.justify-center {
  -webkit-box-pack: center !important;
  -ms-flex-pack: center !important;
  justify-content: center !important;
}

.justify-between {
  -webkit-box-pack: justify !important;
  -ms-flex-pack: justify !important;
  justify-content: space-between !important;
}

.flex-wrap {
  -ms-flex-wrap: wrap !important;
  flex-wrap: wrap !important;
}

.grid {
  display: -ms-grid !important;
  display: grid !important;
}

.h-full { height: 100% !important; }
.min-h-full { min-height: 100% !important; }
.h-screen { height: 100vh !important; }
.min-h-screen { min-height: 100vh !important; }
.size-full { width: 100% !important; height: 100% !important; }
.w-full { width: 100% !important; }
.h-px { height: 1px !important; }
.w-px { width: 1px !important; }
.h-4 { height: 16px !important; }
.w-4 { width: 16px !important; }
.h-5 { height: 20px !important; }
.w-5 { width: 20px !important; }
.h-6 { height: 24px !important; }
.w-6 { width: 24px !important; }
.h-7 { height: 28px !important; }
.w-7 { width: 28px !important; }
.h-8 { height: 32px !important; }
.w-8 { width: 32px !important; }
.h-9 { height: 36px !important; }
.w-9 { width: 36px !important; }
.h-10 { height: 40px !important; }
.w-10 { width: 40px !important; }
.h-11 { height: 44px !important; }
.w-11 { width: 44px !important; }
.h-12 { height: 48px !important; }
.w-12 { width: 48px !important; }
.w-\\[400px\\] { width: 400px !important; }
.max-w-\\[180px\\] { max-width: 180px !important; }
.max-w-\\[280px\\] { max-width: 280px !important; }
.max-w-\\[680px\\] { max-width: 680px !important; }
.max-w-\\[760px\\] { max-width: 760px !important; }
.max-w-\\[820px\\] { max-width: 820px !important; }
.max-w-\\[840px\\] { max-width: 840px !important; }
.min-w-\\[120px\\] { min-width: 120px !important; }
.min-w-\\[150px\\] { min-width: 150px !important; }
.min-w-\\[160px\\] { min-width: 160px !important; }
.min-w-\\[180px\\] { min-width: 180px !important; }
.h-\\[28vh\\] { height: 28vh !important; }
.h-\\[45vh\\] { height: 45vh !important; }
.min-w-0 { min-width: 0 !important; }
.min-h-0 { min-height: 0 !important; }
.max-w-full { max-width: 100% !important; }
.overflow-hidden { overflow: hidden !important; }
.overflow-auto { overflow: auto !important; }
.overflow-y-auto { overflow-y: auto !important; }
.overflow-x-auto { overflow-x: auto !important; }
.text-left { text-align: left !important; }
.text-center { text-align: center !important; }
.truncate {
  overflow: hidden !important;
  text-overflow: ellipsis !important;
  white-space: nowrap !important;
}
.whitespace-nowrap { white-space: nowrap !important; }
.bg-transparent { background: transparent !important; }
.border-0 { border: 0 !important; }
.border { border: 1px solid #ebe8e0 !important; }
.border-t { border-top: 1px solid #ebe8e0 !important; }
.border-r { border-right: 1px solid #ebe8e0 !important; }
.border-b { border-bottom: 1px solid #ebe8e0 !important; }
.border-l { border-left: 1px solid #ebe8e0 !important; }
.shadow-none { box-shadow: none !important; }

.rounded,
.rounded-md { border-radius: 6px !important; }
.rounded-lg { border-radius: 8px !important; }
.rounded-xl { border-radius: 12px !important; }
.rounded-2xl { border-radius: 16px !important; }
.rounded-full { border-radius: 999px !important; }

.p-1 { padding: 4px !important; }
.p-2 { padding: 8px !important; }
.p-3 { padding: 12px !important; }
.p-4 { padding: 16px !important; }
.p-5 { padding: 20px !important; }
.p-6 { padding: 24px !important; }
.p-8 { padding: 32px !important; }
.p-10 { padding: 40px !important; }
.px-2 { padding-left: 8px !important; padding-right: 8px !important; }
.px-3 { padding-left: 12px !important; padding-right: 12px !important; }
.px-4 { padding-left: 16px !important; padding-right: 16px !important; }
.px-5 { padding-left: 20px !important; padding-right: 20px !important; }
.px-6 { padding-left: 24px !important; padding-right: 24px !important; }
.px-8 { padding-left: 32px !important; padding-right: 32px !important; }
.px-10 { padding-left: 40px !important; padding-right: 40px !important; }
.py-1 { padding-top: 4px !important; padding-bottom: 4px !important; }
.py-2 { padding-top: 8px !important; padding-bottom: 8px !important; }
.py-3 { padding-top: 12px !important; padding-bottom: 12px !important; }
.py-4 { padding-top: 16px !important; padding-bottom: 16px !important; }
.py-8 { padding-top: 32px !important; padding-bottom: 32px !important; }
.py-20 { padding-top: 80px !important; padding-bottom: 80px !important; }
.pt-1 { padding-top: 4px !important; }
.pt-2 { padding-top: 8px !important; }
.pt-3 { padding-top: 12px !important; }
.pt-4 { padding-top: 16px !important; }
.pt-7 { padding-top: 28px !important; }
.pt-10 { padding-top: 40px !important; }
.pb-1 { padding-bottom: 4px !important; }
.pb-2 { padding-bottom: 8px !important; }
.pb-3 { padding-bottom: 12px !important; }
.pb-4 { padding-bottom: 16px !important; }
.pb-6 { padding-bottom: 24px !important; }
.pb-8 { padding-bottom: 32px !important; }
.pb-20 { padding-bottom: 80px !important; }
.pl-2 { padding-left: 8px !important; }
.pl-3 { padding-left: 12px !important; }
.pr-2 { padding-right: 8px !important; }
.pr-3 { padding-right: 12px !important; }
.m-0 { margin: 0 !important; }
.mx-auto { margin-left: auto !important; margin-right: auto !important; }
.ml-auto { margin-left: auto !important; }
.mt-auto { margin-top: auto !important; }
.my-1 { margin-top: 4px !important; margin-bottom: 4px !important; }
.my-2 { margin-top: 8px !important; margin-bottom: 8px !important; }
.mx-2 { margin-left: 8px !important; margin-right: 8px !important; }
.mb-1 { margin-bottom: 4px !important; }
.mb-2 { margin-bottom: 8px !important; }
.mb-3 { margin-bottom: 12px !important; }
.mb-4 { margin-bottom: 16px !important; }
.mt-1 { margin-top: 4px !important; }
.mt-2 { margin-top: 8px !important; }
.mt-3 { margin-top: 12px !important; }
.mt-4 { margin-top: 16px !important; }

.gap-0\\.5 > * + * { margin-left: 2px !important; }
.gap-1 > * + * { margin-left: 4px !important; }
.gap-1\\.5 > * + * { margin-left: 6px !important; }
.gap-2 > * + * { margin-left: 8px !important; }
.gap-2\\.5 > * + * { margin-left: 10px !important; }
.gap-3 > * + * { margin-left: 12px !important; }
.flex-col.gap-1 > * + *,
.flex-col.gap-1\\.5 > * + *,
.flex-col.gap-2 > * + *,
.flex-col.gap-2\\.5 > * + *,
.flex-col.gap-3 > * + * {
  margin-left: 0 !important;
}
.flex-col.gap-1 > * + * { margin-top: 4px !important; }
.flex-col.gap-1\\.5 > * + * { margin-top: 6px !important; }
.flex-col.gap-2 > * + * { margin-top: 8px !important; }
.flex-col.gap-2\\.5 > * + * { margin-top: 10px !important; }
.flex-col.gap-3 > * + * { margin-top: 12px !important; }

.-translate-y-1\\/2,
.-translate-x-1\\/2 {
  -ms-transform: translate(-50%, -50%) !important;
  -webkit-transform: translate(-50%, -50%) !important;
  transform: translate(-50%, -50%) !important;
}

/* App-level surfaces. These selectors intentionally avoid CSS variables so
   older engines still get a readable product shell. */
aside {
  background: #f5f3ee !important;
  border-right: 1px solid #ebe8e0 !important;
  color: #2c2a25 !important;
}

main {
  background: #fbfaf7 !important;
  color: #0f0e0c !important;
}

aside button:hover,
main button:hover {
  background: rgba(15, 14, 12, 0.04);
}

textarea,
input {
  background: transparent;
}

[style*="background: var(--bg)"] { background: #fbfaf7 !important; }
[style*="background: var(--bg-sidebar)"] { background: #f5f3ee !important; }
[style*="background: var(--bg-elevated)"] { background: #ffffff !important; }
[style*="background: var(--bg-subtle)"] { background: #f0eee7 !important; }
[style*="background: var(--ink-900)"] { background: #0f0e0c !important; }
[style*="background: var(--brand)"] { background: #5b4ee8 !important; }
[style*="background: var(--brand-soft)"] { background: #eeedff !important; }
[style*="color: var(--ink-900)"] { color: #0f0e0c !important; }
[style*="color: var(--ink-800)"] { color: #1b1916 !important; }
[style*="color: var(--ink-700)"] { color: #2c2a25 !important; }
[style*="color: var(--ink-500)"] { color: #6e6a5f !important; }
[style*="color: var(--ink-400)"] { color: #9a958a !important; }
[style*="color: var(--brand)"] { color: #5b4ee8 !important; }
[style*="var(--border)"] { border-color: #ebe8e0 !important; }
[style*="var(--shadow-xs)"] { box-shadow: 0 1px 2px rgba(15, 14, 12, 0.05) !important; }
[style*="var(--shadow-sm)"] { box-shadow: 0 2px 8px rgba(15, 14, 12, 0.08) !important; }
[style*="var(--shadow-md)"],
[style*="var(--shadow-lg)"] { box-shadow: 0 16px 40px -12px rgba(15, 14, 12, 0.16) !important; }

[role="dialog"],
.doc-download-menu,
.custom-scrollbar {
  background: #ffffff !important;
  color: #0f0e0c !important;
  border: 1px solid #ebe8e0 !important;
  box-shadow: 0 16px 40px -12px rgba(15, 14, 12, 0.12), 0 4px 12px rgba(15, 14, 12, 0.04) !important;
}

.da-markdown,
.da-doc-artifact {
  color: #0f0e0c !important;
}

/* ── Dynamic color-mix() fallbacks ──────────────────────────────────────────
   color-mix(in oklab, currentcolor 50%, transparent) and similar cannot be
   resolved at build time. On Chrome <111, the value is invalid → transparent.
   Provide explicit fallbacks for the most visible affected selectors. */

/* Focus rings: color-mix() → opaque ring color */
*:focus-visible {
  outline: 2px solid #5b4ee8 !important;
  outline-offset: 2px !important;
}

/* Shadcn/ui ring (box-shadow based): override transparent ring */
.ring,
[class*="ring-"] {
  --tw-ring-color: rgba(91, 78, 232, 0.3);
}

/* Input focus border */
input:focus,
textarea:focus,
select:focus {
  border-color: #5b4ee8 !important;
  box-shadow: 0 0 0 2px rgba(91, 78, 232, 0.2) !important;
}

/* ── backdrop-filter glass effects → solid background fallback ───────────────
   Chrome 58–75 ignores backdrop-filter entirely. Ensure panels are readable. */
[class*="backdrop-blur"],
.supports-backdrop-blur {
  background-color: rgba(255, 255, 255, 0.96) !important;
}

/* Shadcn command palette / popover backdrop */
[data-radix-popper-content-wrapper] {
  -webkit-backdrop-filter: blur(8px);
}

/* ── Sidebar specific overrides (uses oklch @layer theme vars) ───────────────
   After PostCSS the vars resolve correctly, but sidebar has its own set.
   Belt-and-suspenders: provide direct background for the sidebar surface. */
[data-slot="sidebar"],
aside[class*="sidebar"] {
  background: #f5f3ee !important;
  border-right: 1px solid #ebe8e0 !important;
}
`;

if (!existsSync(indexPath)) {
  throw new Error(`Missing ${indexPath}; run vite build first.`);
}

writeFileSync(legacyCssPath, legacyCss, "utf8");

const legacyDetector = `      <script data-da-legacy-css-detector>
        (function () {
          var forced   = /(?:^|[?&])daLegacyCss=1(?:&|$)/.test(location.search);
          var disabled = /(?:^|[?&])daLegacyCss=0(?:&|$)/.test(location.search);
          if (disabled) return;
          // Primary gate: does the browser support oklch()?
          // PostCSS has already generated @supports-guarded rgb() fallbacks,
          // but dynamic color-mix() and backdrop-filter still need JS-injected CSS.
          var supportsOklch = !!(window.CSS && CSS.supports && CSS.supports("color", "oklch(0 0 0)"));
          // Secondary gate: IE11 / legacy Edge / old mobile WebKit
          var ua = navigator.userAgent || "";
          var isLegacy = !!document.documentMode          // IE11
            || /MSIE|Trident/.test(ua)                    // IE <11
            || /Edge\\/([0-9]+)/.test(ua) && parseInt(RegExp.$1, 10) <= 18;
          var needsLegacy = forced || isLegacy || !supportsOklch;
          if (!needsLegacy) return;
          document.documentElement.classList
            ? document.documentElement.classList.add("da-legacy-css")
            : (document.documentElement.className += " da-legacy-css");
          var link = document.createElement("link");
          link.rel = "stylesheet";
          link.href = "/legacy-compat.css";
          link.setAttribute("data-da-legacy-compat", "");
          document.head.appendChild(link);
        }());
      </script>`;

let index = readFileSync(indexPath, "utf8");
index = index
  .replace(/\s*<link[^>]+data-da-legacy-compat[^>]*>\s*/gi, "\n")
  .replace(/\s*<script data-da-legacy-css-detector>[\s\S]*?<\/script>\s*/gi, "\n");
index = index.replace(/<\/head>/i, `${legacyDetector}\n    </head>`);
writeFileSync(indexPath, index, "utf8");

console.log("✓ Patched conditional legacy CSS fallback");
