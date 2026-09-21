# AudioWave docs

```
docs/
├── README.md               this index
├── architecture.md         layers, dependency rule, design decisions, rendering, playback, streaming, testing
├── screenshots/
│   ├── studio-*.png        the real app, used by the root README (regenerate with scripts/screenshots.py)
│   └── current-ui.png      the 0.1 demo UI, for comparison
├── design/
│   ├── ui-proposal.md      the UI proposal, with a status section on what was built
│   ├── 01..05-*.png        proposal mockups
│   ├── render.sh           regenerates the mockup PNGs
│   └── mockups/studio.html the mockup source (HTML/CSS/canvas)
└── legacy/                 notes carried over from 0.1
```

- **Using the library and the app:** the root [README](../README.md) (a visual tour, keyboard and mouse reference, ten
  tested code recipes) and [`examples/`](../examples).
- **Understanding the design:** [architecture.md](architecture.md).
- **Where the UI came from:** [design/ui-proposal.md](design/ui-proposal.md). The mockups are pictures of intent;
  the running app is the source of truth.
