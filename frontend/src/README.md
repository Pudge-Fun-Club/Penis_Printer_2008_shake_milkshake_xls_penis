# `frontend/src`

React/TypeScript SPA. The layout follows one rule: **everything belonging to a
feature lives under `features/<name>/`**; only genuinely shared code sits at
the top level.

```
src/
├── main.tsx          Entry point; picks the public page by pathname
│                     (/upload → Upload, /live → LiveViewer, else App)
├── App.tsx           Tab navigation, auth gate, keep-alive view host
│
├── features/         One directory per feature. Convention per feature:
│   │                   <View>.tsx    top-level view(s) / orchestrator
│   │                   components/   feature-private components
│   │                   hooks/        feature-private hooks
│   │                   lib/          pure logic (no React, no API calls)
│   ├── paint/        Drawing editor (Paint, PaintCanvas, PagePanel + panels)
│   ├── coloring/     Coloring editor overlay
│   ├── font-editor/  Stroke-font editor (glyph canvas, dialogs, font model)
│   ├── games/        Game-sheet generators (maze, sudoku, bingo, …)
│   ├── gallery/      Asset library (grid, detail, insert popup)
│   ├── convert/      Job list / file conversion view
│   ├── control/      Printer control, paper setup, calibration, live view
│   ├── stream/       Live-stream plumbing (registry, protocol, viewer)
│   ├── markdown/     Markdown-to-plot editor + layout engine
│   ├── ai-designer/  AI image designer
│   ├── stl/          STL import and 2D line rendering
│   ├── osm/          OpenStreetMap map editor
│   ├── settings/     Settings dialog
│   ├── upload/       Public competition upload page
│   └── auth/         (planned) auth components extracted from App.tsx
│
├── components/       Shared presentational components only:
│                     Modal, dialogs (useConfirm/usePrompt), Toasts, Segmented,
│                     PolylinePreview, ScoreBadge, PlotScore, Gcode3D,
│                     Gcode3DOverlay, StlView3D
├── hooks/            Shared hooks (useArrowKeys, …)
├── lib/              Shared non-React logic (format.ts)
│
├── api/              API layer: client/ (fetch wrappers per domain),
│                     types/ (mirrored response types), events.ts (WebSocket).
│                     Imported everywhere via the ../api barrel.
├── i18n/             Translations (en/de full; ba/es/fr partial) + provider
├── styles/           All CSS, loaded through a single entry point
└── test/             Vitest setup (jsdom polyfills)
```

Rules of thumb:

- `features/*/lib` must not import React components.
- Cross-feature imports are allowed but should point at a feature's top-level
  files, not deep into its `lib/`.
- New shared UI goes to `components/` only once a second feature needs it.
