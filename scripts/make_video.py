"""Build a silent video that scrolls down through the Studio screenshots.

    pip install -e ".[video]"
    python scripts/make_video.py                 # writes docs/media/audiowave-tour.mp4 and .gif

Each screenshot is held for HOLD seconds, then the view scrolls to the next one. There is no audio track.
The GIF is the same tour, smaller, because GitHub plays a GIF inline in a README but not a repository .mp4.
"""

import subprocess
import sys
from pathlib import Path

import imageio_ffmpeg
import numpy as np
from PySide6.QtGui import QImage

ROOT = Path(__file__).resolve().parent.parent
SHOTS = ROOT / "docs" / "screenshots"
OUT = ROOT / "docs" / "media" / "audiowave-tour.mp4"
GIF = OUT.with_suffix(".gif")
GIF_WIDTH, GIF_FPS = 1000, 10

#: Order of the tour: the old 0.1 UI first for contrast, then what Studio can do, then how it looks.
ORDER = [
    'current-ui', "studio-player", "studio-mp3", "studio-spectrogram", "studio-spectrum", "studio-scope",
    "studio-compare", "studio-record", "studio-stream", "studio-styles", "studio-player-light",
]  # fmt: skip

#: Smaller screenshots (the old UI) are centred on a canvas of this colour: Studio's own background.
PAD_COLOR = (0x0B, 0x0C, 0x0A)
FPS = 30
HOLD = 3.0  # seconds each screenshot stays on screen
SCROLL = 0.7  # seconds taken to scroll to the next one


def load(name: str) -> np.ndarray:
    """A screenshot as a height x width x 3 uint8 array."""
    image = QImage(str(SHOTS / f"{name}.png")).convertToFormat(QImage.Format.Format_RGB888)
    if image.isNull():
        sys.exit(f"missing screenshot: {name}.png (run scripts/screenshots.py first)")
    stride = image.bytesPerLine()
    raw = np.frombuffer(image.constBits(), np.uint8, count=stride * image.height())
    # .copy(): the array would otherwise point into the QImage's buffer, which is freed when this returns.
    return (
        raw.reshape(image.height(), stride)[:, : image.width() * 3]
        .reshape(image.height(), image.width(), 3)
        .copy()
    )


def pad_to(shot: np.ndarray, height: int, width: int) -> np.ndarray:
    """Centre ``shot`` on a ``PAD_COLOR`` canvas of the given size. The image is never scaled, so it stays sharp."""
    h, w = shot.shape[:2]
    if h > height or w > width:
        sys.exit(f"a screenshot ({w}x{h}) is larger than the video frame ({width}x{height})")
    canvas = np.empty((height, width, 3), np.uint8)
    canvas[:] = PAD_COLOR
    top, left = (height - h) // 2, (width - w) // 2
    canvas[top : top + h, left : left + w] = shot
    return canvas


def make_gif(video: Path, gif: Path) -> None:
    """Re-encode ``video`` as a small looping GIF with a shared palette (dither off keeps flat UI areas clean)."""
    graph = (
        f"fps={GIF_FPS},scale={GIF_WIDTH}:-2:flags=lanczos,split[a][b];"
        "[a]palettegen=max_colors=96:stats_mode=diff[p];[b][p]paletteuse=dither=none:diff_mode=rectangle"
    )
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(video),
            "-vf",
            graph,
            str(gif),
        ],
        check=True,
    )


def ease(t: float) -> float:
    """Ease in and out (smoothstep), so the scroll starts and stops gently."""
    return t * t * (3 - 2 * t)


def main() -> int:
    shots = [load(name) for name in ORDER]
    height, width = (
        max(s.shape[0] for s in shots),
        max(s.shape[1] for s in shots),
    )  # the largest sets the frame
    shots = [pad_to(s, height, width) for s in shots]
    strip = np.concatenate(shots, axis=0)  # one tall image; the video is a window sliding down it

    hold_frames, scroll_frames = round(HOLD * FPS), round(SCROLL * FPS)
    offsets: list[int] = []
    for i in range(len(shots)):
        top = i * height
        offsets += [top] * hold_frames
        if i < len(shots) - 1:
            offsets += [
                top + round(ease((f + 1) / scroll_frames) * height) for f in range(scroll_frames)
            ]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    writer = imageio_ffmpeg.write_frames(
        str(OUT), (width, height), fps=FPS, codec="libx264", pix_fmt_in="rgb24", pix_fmt_out="yuv420p",
        quality=7, macro_block_size=1, output_params=["-an", "-movflags", "+faststart"],
    )  # fmt: skip
    writer.send(None)  # start the encoder
    for y in offsets:
        writer.send(np.ascontiguousarray(strip[y : y + height]))
    writer.close()
    print(f"wrote {OUT} ({len(offsets) / FPS:.1f} s, {width}x{height}, {FPS} fps, no audio)")
    make_gif(OUT, GIF)
    print(f"wrote {GIF} ({GIF.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
