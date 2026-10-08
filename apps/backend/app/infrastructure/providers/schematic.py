from __future__ import annotations

import subprocess
from typing import Any

from app.config import get_settings

settings = get_settings()

# Minimal 5x7 bitmap font for the characters used in mock video labels.
_FONT = {
    "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "B": ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
    "C": ["01111", "10000", "10000", "10000", "10000", "10000", "01111"],
    "D": ["11110", "10001", "10001", "10001", "10001", "10001", "11110"],
    "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    "F": ["11111", "10000", "10000", "11110", "10000", "10000", "10000"],
    "G": ["01111", "10000", "10000", "10111", "10001", "10001", "01111"],
    "H": ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
    "I": ["11111", "00100", "00100", "00100", "00100", "00100", "11111"],
    "J": ["00111", "00010", "00010", "00010", "00010", "10010", "01100"],
    "K": ["10001", "10010", "10100", "11000", "10100", "10010", "10001"],
    "L": ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    "M": ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
    "N": ["10001", "11001", "10101", "10011", "10001", "10001", "10001"],
    "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    "P": ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
    "Q": ["01110", "10001", "10001", "10001", "10101", "10010", "01101"],
    "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    "U": ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
    "V": ["10001", "10001", "10001", "10001", "10001", "01010", "00100"],
    "W": ["10001", "10001", "10001", "10101", "10101", "10101", "01010"],
    "X": ["10001", "10001", "01010", "00100", "01010", "10001", "10001"],
    "Y": ["10001", "10001", "01010", "00100", "00100", "00100", "00100"],
    "Z": ["11111", "00001", "00010", "00100", "01000", "10000", "11111"],
    "0": ["01110", "10001", "10011", "10101", "11001", "10001", "01110"],
    "1": ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
    "2": ["01110", "10001", "00001", "00110", "01000", "10000", "11111"],
    "3": ["11110", "00001", "00001", "01110", "00001", "00001", "11110"],
    "4": ["00010", "00110", "01010", "10010", "11111", "00010", "00010"],
    "5": ["11111", "10000", "11110", "00001", "00001", "00001", "11110"],
    "6": ["01110", "10000", "10000", "11110", "10001", "10001", "01110"],
    "7": ["11111", "00001", "00010", "00100", "01000", "01000", "01000"],
    "8": ["01110", "10001", "10001", "01110", "10001", "10001", "01110"],
    "9": ["01110", "10001", "10001", "01111", "00001", "00001", "01110"],
    "-": ["00000", "00000", "00000", "11111", "00000", "00000", "00000"],
    ":": ["00000", "00100", "00100", "00000", "00100", "00100", "00000"],
    "/": ["00001", "00010", "00010", "00100", "01000", "01000", "10000"],
    ".": ["00000", "00000", "00000", "00000", "00000", "01100", "01100"],
    " ": ["00000"] * 7,
}


def _draw_text(pixels, W, H, x, y, text, color, scale=2):
    chars = list(text.upper())
    cursor = x
    for ch in chars:
        glyph = _FONT.get(ch, _FONT[" "])
        for row, bits in enumerate(glyph):
            for col, bit in enumerate(bits):
                if bit == "1":
                    for dy in range(scale):
                        for dx in range(scale):
                            px = cursor + col * scale + dx
                            py = y + row * scale + dy
                            if 0 <= px < W and 0 <= py < H:
                                pixels[py * W + px] = color
        cursor += 6 * scale + scale


def _render_frame(pixels, W, H, frame, total_frames, scene):
    """Draw a simple schematic floor plan with moving 'character' blocks."""
    bg = (24, 26, 34)
    for i in range(W * H):
        pixels[i] = bg

    t = frame / max(total_frames - 1, 1)

    # Floor plan outline
    for x in range(20, W - 20):
        pixels[30 * W + x] = (70, 74, 90)
        pixels[(H - 60) * W + x] = (70, 74, 90)
    for y in range(30, H - 60):
        pixels[y * W + 20] = (70, 74, 90)
        pixels[y * W + W - 20] = (70, 74, 90)

    # Divider wall
    for y in range(30, H - 60):
        pixels[y * W + W // 2] = (55, 58, 72)

    # Door gap in divider (center)
    for y in range(H // 2 - 40, H // 2 + 40):
        pixels[y * W + W // 2] = (24, 26, 34)

    # Scene objects
    characters = scene.get("characters", [])
    for c in characters:
        sx, sy = c["start"]
        ex, ey = c["end"]
        x = int(sx + (ex - sx) * t)
        y = int(sy + (ey - sy) * t)
        col = c.get("color", (200, 90, 90))
        for dy in range(-14, 15):
            for dx in range(-9, 10):
                px = x + dx
                py = y + dy
                if 0 <= px < W and 0 <= py < H and (abs(dx) <= 9 and abs(dy) <= 14):
                    pixels[py * W + px] = col
        _draw_text(pixels, W, H, x - 20, y - 32, c.get("label", ""), (230, 230, 235), scale=1)

    # Static objects (locations)
    for o in scene.get("objects", []):
        ox, oy = o["pos"]
        col = o.get("color", (120, 120, 130))
        for dy in range(-6, 7):
            for dx in range(-6, 7):
                px = ox + dx
                py = oy + dy
                if 0 <= px < W and 0 <= py < H:
                    pixels[py * W + px] = col
        _draw_text(pixels, W, H, ox - 20, oy + 10, o.get("label", ""), (200, 200, 210), scale=1)

    # Unknown region overlay
    if scene.get("unknown_region"):
        for o in scene["unknown_region"]:
            ox, oy = int(o["x"]), int(o["y"])
            w, h = int(o["w"]), int(o["h"])
            for py in range(oy, oy + h):
                for px in range(ox, ox + w):
                    if 0 <= px < W and 0 <= py < H:
                        pixels[py * W + px] = tuple(min(255, 24 + int(40 * (0.5 + 0.5 * (t % 0.5) * 2))) for _ in range(3))

    # Bottom label bar
    for y in range(H - 56, H):
        for x in range(W):
            pixels[y * W + x] = (15, 17, 24)

    _draw_text(pixels, W, H, 30, H - 50, "BAKKE  |  " + scene.get("label", ""), (240, 240, 245), scale=2)
    _draw_text(pixels, W, H, 30, H - 26, "3D ANIMATED SCENARIO VISUALIZATION - NOT RECORDED FOOTAGE", (180, 180, 190), scale=1)


def _write_ppm(path: str, pixels, W: int, H: int) -> None:
    with open(path, "w") as f:
        f.write("P3\n")
        f.write(f"{W} {H}\n255\n")
        for color in pixels:
            f.write(f"{color[0]} {color[1]} {color[2]} ")


def _encode_video(frames_dir: str, output_path: str, fps: int = 24) -> None:
    import os

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-framerate",
            str(fps),
            "-i",
            f"{frames_dir}/frame_%04d.ppm",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            output_path,
        ],
        capture_output=True,
        check=True,
    )


def render_schematic_video(scene: dict[str, Any], output_path: str, duration_seconds: float = 4.0, width: int = 640, height: int = 360) -> str:
    """Render a schematic 3D-style animated floor-plan video (MOCK video generation).

    Generates a real MP4 using procedural frames. Output is clearly labelled as
    an animated scenario visualization, not recorded footage.
    """
    import os
    import tempfile

    fps = 12
    total_frames = max(int(duration_seconds * fps), fps)
    with tempfile.TemporaryDirectory() as tmp:
        for frame in range(total_frames):
            pixels = [(0, 0, 0)] * (width * height)
            _render_frame(pixels, width, height, frame, total_frames, scene)
            _write_ppm(f"{tmp}/frame_{frame + 1:04d}.ppm", pixels, width, height)
        _encode_video(tmp, output_path, fps)
    return output_path