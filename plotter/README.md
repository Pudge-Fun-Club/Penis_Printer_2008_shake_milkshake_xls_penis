# `plotter`

Python backend — G-code generation, calibration, job management, and the
HTTP API served to the frontend.

The packages follow the data flow: `artwork` (input files) → `geometry`
(polyline math) → `gcode` (machine output), with `core` as shared plumbing.

```
plotter/
│
├── core/                Cross-cutting state & persistence
│   ├── config.py        App settings dataclasses (env / file backed)
│   ├── calibration.py   Calibration dataclass (origin, plot area, feeds, pen
│   │                    heights, obstacles, …) + data_dir()
│   ├── document.py      DocumentStore — paint pages/groups CRUD (JSON backed)
│   ├── jobmeta.py       Job sidecar (.meta.json) read/write
│   ├── storage.py       Path helpers: jobs_dir()
│   ├── state.py         Shared state store (file or Redis backed)
│   ├── position.py      Printer position tracking
│   └── events.py        In-process pub/sub hub for app events
│
├── geometry/            Pure polyline math, no I/O
│   ├── primitives.py    Point/Polyline/Polygon aliases, transforms, masks
│   ├── routing.py       Dijkstra travel routing around obstacle zones
│   ├── linemerge.py     Merge adjacent polylines to reduce pen lifts
│   └── oneline.py       Eulerian single-stroke path construction
│
├── gcode/               Polylines → G-code and its analysis
│   ├── scene.py         Page → G-code: page_polylines, scene_gcode,
│   │                    save_scene_job, page_thumbnail
│   ├── profile.py       vpype config, G-code header/footer, pen up/down,
│   │                    test patterns
│   ├── preview.py       G-code → preview polylines (2-D and 3-D viewers)
│   ├── safety.py        GcodeSafetyChecker — bed limits and obstacle zones
│   └── metrics.py       G-code quality metrics and plottability score
│
├── artwork/             Input files → plottable polylines
│   ├── pipeline.py      PlotterError, file conversion orchestration
│   │                    (PDF/Office/SVG via poppler, libreoffice, vpype)
│   ├── convert.py       Convert with calibration applied
│   ├── trace.py         Bitmap → polylines (contour/centerline tracing)
│   ├── drawing.py       Drawing class: SVG parsing, travel sort, placement
│   └── export.py        Calibration XML import/export
│
├── text/                Handwriting / single-line text rendering
│   └── singleline.py    text_polylines(): font → strokes with humanize/warp
│
├── web/                 FastAPI app: app.py factory + routes/ per domain
├── services/            Domain services used by routes (gallery, profiles,
│                        auth, printer, paper, fonts, sources, …)
├── printer/             Printer backends: serial worker, OctoPrint, discovery
├── mcp/                 MCP (Model Context Protocol) server endpoint
├── coloring_pages/      Generated coloring page artwork (mandala, rings, …)
├── ai_images/           AI image generation service
├── osm/  sudoku/ maze/  Map / puzzle artwork generators
├── stroke_fonts/        Recorded stroke-font model, storage and rendering
├── stream/              Live view streaming sessions
├── desktop/             pywebview desktop wrapper
│
├── fonts/               Bundled single-line fonts (used by text/)
├── cli.py               CLI entry point (`gcodescribe`)
└── vpype_config.toml    vpype optimisation preset used during conversion
```

## Key invariants

- `geometry/` has **no project imports outside itself** — safe to unit-test in
  isolation; `geometry/primitives.py` is imported only by `gcode/scene.py`.
- G-code is never written directly by route handlers; they always call
  `save_scene_job` or `convert`, which run `GcodeSafetyChecker` before saving.
