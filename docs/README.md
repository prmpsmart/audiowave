# AudioWave docs

Working notes, screenshots and design proposals live here.

```
docs/
├── README.md               this index
├── screenshots/
│   └── current-ui.png      the existing demo UI (copy of tests/test.PNG)
└── design/
    ├── ui-proposal.md      the new UI proposal: screens, feature map, styles, build order
    ├── 01-player.png       player screen
    ├── 02-player-annotated.png
    ├── 03-stream.png       Mimi Wave stream screen
    ├── 04-stream-annotated.png
    ├── 05-style-lab.png    twelve waveform renderers
    ├── render.sh           regenerates the PNGs from the mockup
    └── mockups/
        └── studio.html     the design source (HTML/CSS/canvas)
```

## Design mockups

Start with [design/ui-proposal.md](design/ui-proposal.md).

To iterate on a design, edit `design/mockups/studio.html` and run `design/render.sh`. The same file renders each screen
through a query string (`?mode=stream`, `?mode=gallery`, `&annotate`), so you can also open it directly in a browser.
The mockup is a picture of the intended result, not code that ships. The Qt implementation is a separate step.
