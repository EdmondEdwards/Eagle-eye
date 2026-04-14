from __future__ import annotations

import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

ICON_NAMES = [
    "commercial_jet",
    "heavy_jet",
    "cargo_plane",
    "turboprop",
    "general_aviation",
    "fighter_jet",
    "stealth_fighter",
    "awacs",
    "helicopter",
    "drone_uav",
]


def svg_inner_markup(path: Path) -> tuple[str, str]:
    tree = ET.parse(path)
    root = tree.getroot()
    view_box = root.attrib.get("viewBox", "0 0 128 128")
    children = "".join(ET.tostring(child, encoding="unicode") for child in root)
    return view_box, children


def write_preview_sheet(icon_dir: Path, preview_dir: Path) -> Path:
    cards: list[str] = []
    col_count = 2
    row_height = 240
    card_width = 520

    for index, name in enumerate(ICON_NAMES):
        label = name.replace("_", " ").title()
        col = index % col_count
        row = index // col_count
        x = 40 + col * (card_width + 24)
        y = 64 + row * row_height
        view_box, inner = svg_inner_markup(icon_dir / f"{name}.svg")
        background = "#09111b" if col == 0 else "#eef4fb"
        foreground = "#ffd54a" if col == 0 else "#101a28"
        accent = "#8aa0b6" if col == 0 else "#5c6775"
        cards.append(
            f"""
            <g transform="translate({x} {y})">
              <rect width="{card_width}" height="200" rx="24" fill="{background}" />
              <text x="28" y="38" font-family="IBM Plex Sans, Arial, sans-serif" font-size="22" font-weight="700" fill="{foreground}">{label}</text>
              <text x="28" y="68" font-family="IBM Plex Sans, Arial, sans-serif" font-size="14" fill="{accent}">{name}</text>
              <svg x="48" y="82" width="112" height="112" viewBox="{view_box}" color="{foreground}">{inner}</svg>
              <svg x="196" y="96" width="80" height="80" viewBox="{view_box}" color="{foreground}">{inner}</svg>
              <svg x="310" y="102" width="56" height="56" viewBox="{view_box}" color="{foreground}">{inner}</svg>
              <svg x="392" y="106" width="40" height="40" viewBox="{view_box}" color="{foreground}">{inner}</svg>
              <svg x="450" y="110" width="28" height="28" viewBox="{view_box}" color="{foreground}">{inner}</svg>
            </g>
            """
        )

    sheet = f"""
    <svg xmlns="http://www.w3.org/2000/svg" width="1144" height="1280" viewBox="0 0 1144 1280">
      <rect width="1144" height="1280" fill="#040b14" />
      <text x="40" y="36" font-family="IBM Plex Sans, Arial, sans-serif" font-size="28" font-weight="700" fill="#dbe7f4">Eagle Eye Aircraft Icon Preview Sheet</text>
      {''.join(cards)}
    </svg>
    """
    output = preview_dir / "preview-sheet.svg"
    output.write_text(sheet.strip() + "\n", encoding="utf-8")
    return output


def render_png(svg_path: Path, output_dir: Path, size: int) -> None:
    subprocess.run(
        ["qlmanage", "-t", "-s", str(size), "-o", str(output_dir), str(svg_path)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    generated = output_dir / f"{svg_path.name}.png"
    target = output_dir / f"{svg_path.stem}.png"
    if generated.exists():
        generated.replace(target)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    icon_dir = root / "src" / "assets" / "aircraft"
    preview_dir = icon_dir / "previews"
    preview_dir.mkdir(parents=True, exist_ok=True)

    sheet_path = write_preview_sheet(icon_dir, preview_dir)
    for name in ICON_NAMES:
        render_png(icon_dir / f"{name}.svg", preview_dir, 256)
    render_png(sheet_path, preview_dir, 2048)
    if sheet_path.exists():
        sheet_path.unlink()


if __name__ == "__main__":
    main()
