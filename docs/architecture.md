# Architecture

## Goals

1. `audiowave` is a **standalone library**. It must not import the app, and the app may only use its public API.
2. Every module has one reason to change, and new behaviour is added by writing new code rather than editing old.
3. Nothing blocks the UI thread and nothing needs a lock: there are no threads.

## Layout

```
src/audiowave/
  core/          numpy only. AudioClip, wavio, format, peaks (pyramid), live peaks, analysis (spectrogram, bands,
                 stereo, silence), loudness (BS.1770), edit (cut/fade/normalise/...), annotations
  appearance.py  Appearance, Palette, Gravity: immutable, JSON-serialisable, Qt-free
  audio/         QtMultimedia. AudioPlayer, AudioRecorder, AudioDecoder (mp3 & co), PcmSource, devices, permissions
  widgets/       QtWidgets. TimelineView -> WaveformView / SpectrogramView; OverviewView, LiveWaveformView,
                 VectorscopeView, SpectrumView, LevelMeter; painters/ (one class per style); LaneRenderer; Viewport; ruler
  binding.py     bind_player(): the only place a player is connected to views
studio/          the demo app
  main.py        composition root: builds every concrete object and wires them together
  session.py     shared state and services (player, recorder, takes, loop, markers, silences, loudness, edits, viewport)
  editing.py     maps UI edit actions to library operations and their preconditions (pure, testable)
  tasks.py       BackgroundTasks: run pure work off the UI thread, deliver on it, drop superseded results
  models/        AppearanceModel, TakesModel (with undo history), PresetStore, RecentFiles: state with no widgets
  pages/         Player, Record, Stream, Style Lab: one widget per mode
  stream/        protocol, StreamSender, StreamReceiver, FrameLogModel (TCP, Qt sockets)
  widgets/       UI kit (segmented control, sliders, toggle...), transport, takes strip, style picker
  theme/         tokens (dark, light), stylesheet builder, fonts, icons
tests/           mirrors the source tree
```

### Dependency rule

```
core  <-  appearance  <-  widgets  <-  binding
  ^                          ^            |
  '------------  audio  ------------------'
                              studio uses all of the above, never the reverse
```

`audio` and `widgets` do not import each other; `binding` is the seam. The `Loop` and `Marker` value types live
in `core` precisely so `audio` can use them without importing widgets.

## How the principles show up

| Principle | Where |
|-----------|-------|
| **Single responsibility** | A style paints one colour and nothing else (`WavePainter`); `LaneRenderer` alone decides played/unplayed compositing and caching; `Viewport` alone owns the visible time window; `PeakPyramid` alone answers "min/max/RMS of this range" |
| **Open/closed** | A new waveform style is one `@register` class ([`examples/custom_style.py`](../examples/custom_style.py)); the registry, renderer, inspector-visibility flags (`uses_bar_shape`, `uses_gravity`) and the Style Lab pick it up without edits |
| **Liskov** | Every `TimelineView` subclass (waveform, spectrogram) shares seek, loop, zoom and the playhead, so `bind_player` treats them alike; every `WavePainter` honours the same `PaintJob` contract |
| **Interface segregation** | Views expose two or three signals (`seekRequested`, `loopChanged`) and setters; they never see a player. The player exposes signals and knows nothing of widgets |
| **Dependency inversion** | Pages receive a `Session` rather than constructing services; `main.build_window` is the only place concrete classes are chosen, so tests inject a temp preset path and a silent player |
| **DRY** | `extents()` and `column_x()` are the shared geometry of every bar-like style; `layout_lanes()` is used by both the waveform and the channel strip so they line up; `TimelineView` is written once for the waveform and the spectrogram; `paint_preview` draws inspector thumbnails, Style Lab tiles and takes from the same painters |
| **Immutability** | `AudioClip` and `Appearance` are immutable, so caches keyed on them cannot go stale and changing one channel's look is `appearance.with_(...)` |

## Formats and decoding

WAV is read by the Qt-free core (`wavio`), which handles float and extensible headers that the standard `wave` module cannot.
Everything else goes through `AudioDecoder`, a thin wrapper over Qt's FFmpeg-backed `QAudioDecoder`: no extra dependency and
any codec the platform build supports. It decodes asynchronously with progress and cancellation, and `Session.open_file` falls
back to it for WAV variants the core does not understand.

## Loudness and editing

`core/loudness.py` implements ITU-R BS.1770-4: K-weighting, 400 ms blocks with 75 % overlap, absolute and relative gating,
and loudness range. K-weighting is an IIR filter; running it sample by sample in Python is far too slow, so its impulse
response (which dies away in milliseconds) is truncated and applied by block FFT convolution. It is validated against values
that follow from the standard itself (a 997 Hz stereo sine at -20 dBFS reads -20.0 LUFS; mono reads 3 LU lower) at four sample
rates, rather than against another implementation.

`core/edit.py` is a set of pure functions from clip to clip. Undo therefore costs nothing conceptually: Studio's `TakesModel`
keeps the previous clips (bounded to 10, since each is a full copy). Edits and loudness run on `BackgroundTasks`; results for a
clip that has since been replaced are dropped, and concurrent requests for the same clip share one measurement so no caller is
left waiting.

## Rendering

- **Peaks.** Drawing a waveform needs min/max/RMS per pixel column. `PeakPyramid` precomputes coarser levels once (like
  mip-maps) and answers any `query(start, stop, buckets)` from the nearest level, so zooming a 10-minute clip costs about
  the same as a 10-second one.
- **Layers.** For a fixed view, `LaneRenderer` renders the shape once in the "played" colour and once in "unplayed" into
  pixmaps. Advancing the playhead only re-blits them with a clip, so playback repaints stay cheap however elaborate the
  style. A style can define its own "played" region (radial uses a clockwise pie).
- **Live audio.** `LivePeaks` keeps fixed-size buckets, so appending a chunk is O(chunk) and finished buckets never change.

## Playback

`AudioPlayer` feeds a `QAudioSink` from `PcmSource`, a pull-mode `QIODevice` that can wrap a loop region inside a single
read, so loops are gapless. **Position comes from the device's processed-time counter, not from a UI timer**, so the playhead
cannot drift from what you hear. Changing speed, loop, output device or channel gains rebuilds the sink at the current
frame. Speed is varispeed: the device is told the stream runs at a scaled sample rate.

## Streaming

`studio/stream` sends audio between two studios over TCP on the Qt event loop.

```
message = [type: u8][length: u32 LE][payload]
HELLO (JSON: rate, channels, format)  ->  FRAME* (raw s16 PCM, 20 ms each)  ->  END
```

`FrameDecoder` reassembles messages from arbitrarily chopped TCP chunks (tested down to one byte at a time) and rejects
oversize or unknown messages. A receiver that connects while a stream is live is sent `HELLO` first.

One rule learned the hard way: socket signals are connected to **bound methods, never lambdas that capture `self`**. Qt
disconnects a destroyed QObject's bound slots automatically; a lambda keeps calling into a half-destroyed object during
teardown, which segfaulted a test run.

## Testing

| Area | How |
|------|-----|
| core | pure numpy tests: codec round trips for every sample format, peak pyramid vs brute force, extreme values surviving every zoom |
| painters and widgets | render to `QImage` and count pixels; real mouse and wheel events through `QTest`; the whole registry is exercised |
| decoding | a real MP3 (encoded once with LAME from the stereo test WAV and kept in `tests/assets`) is decoded and matched against the WAV it came from, allowing for the encoder's known delay |
| audio | `PcmSource` unit tests (frame alignment, gapless loop); the player runs on the real output device at volume 0 |
| streaming | protocol fuzzing by chunk size, then a real loopback socket transferring a clip |
| app | the assembled window: page switching, shortcuts, theme swap, appearance edits reaching lanes, loop/marker/zoom wiring, end-to-end send over loopback |
| examples and README | executed in subprocesses; every code block in the README marked as testable is run, silently |

## Extending

- **A style:** subclass `WavePainter`, set `name`/`label` and the capability flags, implement `paint`, decorate with `@register`.
- **An analysis view:** subclass `TimelineView` and implement `paint_content`; share the `Viewport` to stay in sync.
- **A theme:** add a `Theme` in `studio/theme/tokens.py`; every colour, including the waveform palette, comes from it.
