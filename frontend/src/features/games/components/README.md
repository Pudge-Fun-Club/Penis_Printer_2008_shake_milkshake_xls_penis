# `src/features/games/components`

Sub-components of the Games view, extracted from `Games.tsx` to split
rendering logic from orchestration state.

```
components/
├── GameSettingsPanel.tsx   Per-game configuration panel rendered inside the
│                           detail sidebar. Covers all configurable games:
│                           Dots & Boxes, Battleships, Maze, Sudoku,
│                           Coloring Mandala, Coloring Pattern.
│                           Also contains three local helper components:
│                             SeedInputRow    — manual/auto seed toggle + input
│                             ComplexityControl — range slider with % readout
│                             SeedVisibilityToggle — on/off toggle for showing
│                                                    the seed on the printed page
│                           Exports the SeedInputState interface used to group
│                           seed-related state for each game type.
│
├── GamePreviewModal.tsx    Full-screen modal shown after a game is generated.
│                           Displays an SVG preview, chip summary (dimensions,
│                           line count), solution toggle for maze/sudoku, a
│                           "Regenerate" button, and a "Create page" action.
│                           Receives a live-stream handle so the preview can
│                           be broadcast while the modal is open.
│
└── PreviewSvg.tsx          SVG renderer for the generated-game modal preview.
```

## Conventions

- All components are fully controlled — state lives in `Games.tsx`.
- `GameSettingsPanel` imports pure template helpers from `../lib/templates`
  and constants from `../lib/constants` / `../lib/mazeTypes`.
- `GamePreviewModal` renders the `Modal` shell component and the
  `GamePreviewSvg` SVG renderer from `./PreviewSvg`.
