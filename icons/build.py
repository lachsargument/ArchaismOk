#!/usr/bin/env python3
"""Build the ArchaismOk icon theme from the extracted Fedora 12 and Arch themes.

Selection rule, per icon name (lookup in icon themes is by name only, so
all sizes of one name always come from the same source):

1. Names listed in prefer-new.txt come from the new themes.
2. Otherwise the Fedora 12 chain wins: Mist.12, then gnome.12.
3. Names that Fedora 12 never had come from Mist.new, then gnome.new.

Usage:
    python3 build.py [--src sources] [--out ArchaismOk]

Also writes report.html next to the output, a side-by-side view of every
icon whose artwork differs between the old and new themes. Open it through
serve.py to pick icons by clicking. Picks are saved to prefer-new.txt.
"""

import argparse
import configparser
import hashlib
import html
import os
import shutil
from pathlib import Path

import numpy as np
from PIL import Image

OLD = ['Mist.12', 'gnome.12']
NEW = ['Mist.new', 'gnome.new']
EXTS = {'.png', '.svg', '.xpm', '.icon'}

HERE = Path(__file__).resolve().parent

# Icons taken from the new themes even though Fedora 12 has them, one name
# per line. Aliases (symlinks to the same file) are pulled in automatically.
PREFER_FILE = HERE / 'prefer-new.txt'


def load_prefer() -> set[str]:
    """Names listed in prefer-new.txt, ignoring blanks and # comments."""
    if not PREFER_FILE.exists():
        return set()
    lines = (line.split('#')[0].strip() for line in PREFER_FILE.read_text().splitlines())
    return {line for line in lines if line}


def sections(theme: Path) -> dict[str, dict[str, str]]:
    """Directory sections declared in the theme's index.theme."""
    cp = configparser.ConfigParser(interpolation=None, strict=False)
    cp.optionxform = str
    cp.read(theme / 'index.theme', encoding='utf-8')
    dirs = cp['Icon Theme']['Directories'].split(',')
    return {d: dict(cp[d]) for d in dirs if d in cp}


def scan(theme: Path) -> dict[str, list[str]]:
    """Map icon name to its files (paths relative to the theme).

    Directories missing from index.theme are skipped: icon lookup never
    sees them, so Fedora 12 never showed what is in them either.
    """
    declared = sections(theme)
    names: dict[str, list[str]] = {}
    for dp, _, fns in os.walk(theme):
        if str(Path(dp).relative_to(theme)) not in declared:
            continue
        for f in fns:
            p = Path(dp, f)
            if p.suffix not in EXTS or not p.exists():
                continue
            names.setdefault(p.stem, []).append(str(p.relative_to(theme)))
    return names


def aliases(theme: Path, files: dict[str, list[str]], name: str) -> set[str]:
    """Names in the theme whose files resolve to the same images as name."""
    targets = {(theme / f).resolve() for f in files[name]}
    return {n for n, fs in files.items() if any((theme / f).resolve() in targets for f in fs)}


def choose(src: Path, scans: dict[str, dict[str, list[str]]], prefer: set[str]) -> dict[str, str]:
    """Pick the source theme for every icon name."""
    pick: dict[str, str] = {}
    for theme in reversed(OLD + NEW):
        pick.update(dict.fromkeys(scans[theme], theme))
    for theme in reversed(NEW):
        for want in prefer:
            if want in scans[theme]:
                pick.update(dict.fromkeys(aliases(src / theme, scans[theme], want), theme))
    return pick


def fix_svg(data: bytes) -> bytes:
    """Repair SVG markup that modern librsvg refuses to load.

    Some Mist SVGs declare xmlns:s="http://inkscape.sourceforge.net/DTD/s
    odipodi-0.dtd" (a stray space). librsvg 2.x of Fedora 12 ignored it,
    but the current libxml2-based parser rejects the namespace URI and the
    whole icon fails to load, so plain folders lose their icon.
    """
    return data.replace(b'DTD/s odipodi-0.dtd', b'DTD/sodipodi-0.dtd')


def load(path: Path) -> bytes:
    """Read an icon file, repairing it if it is a broken SVG."""
    data = path.read_bytes()
    return fix_svg(data) if path.suffix == '.svg' else data


def dedupe(out: Path) -> None:
    """Turn identical files in one directory back into symlinks.

    Files are copied dereferenced because a symlink in a source theme may
    point at a name that was taken from another theme; relinking here
    restores the small package size without that risk.
    """
    for dp, _, fns in os.walk(out):
        seen: dict[tuple[str, str], str] = {}
        for f in sorted(fns):
            p = Path(dp, f)
            key = (p.suffix, hashlib.sha1(p.read_bytes()).hexdigest())
            if key in seen:
                p.unlink()
                p.symlink_to(seen[key])
            else:
                seen[key] = f


def write_index(src: Path, out: Path, dirs: set[str]) -> None:
    """Write index.theme, reusing each directory's section from a source."""
    merged: dict[str, dict[str, str]] = {}
    for theme in reversed(OLD + NEW):
        merged.update(sections(src / theme))

    def order(d: str) -> tuple[int, str]:
        size = d.split('/')[0]
        return (10**6 if size == 'scalable' else int(size.split('x')[0]), d)

    ordered = sorted(dirs, key=order)
    lines = [
        '[Icon Theme]',
        'Name=ArchaismOk',
        'Comment=ArchaismOk icon theme, based on Fedora 12 (Mist and GNOME 2.28)',
        'Inherits=hicolor',
        'Example=folder',
        'Directories=' + ','.join(ordered),
        '',
    ]
    for d in ordered:
        lines.append(f'[{d}]')
        lines += [f'{k}={v}' for k, v in merged[d].items()]
        lines.append('')
    (out / 'index.theme').write_text('\n'.join(lines), encoding='utf-8')


def preview(theme: Path, files: list[str]) -> str | None:
    """Pick the file closest to 48px for display."""
    imgs = [f for f in files if Path(f).suffix in ('.png', '.svg')]

    def dist(f: str) -> int:
        size = f.split('/')[0]
        return 1 if size == 'scalable' else abs(int(size.split('x')[0]) - 48)

    return min(imgs, key=dist) if imgs else None


def diff_score(a: Path, b: Path, files_a: list[str], files_b: list[str]) -> float:
    """Worst mean pixel difference over same-directory PNG pairs (0-255)."""
    shared = [f for f in set(files_a) & set(files_b) if f.endswith('.png')]
    if not shared:
        return 255.0  # nothing comparable, so let a human look at it
    worst = 0.0
    for f in shared:
        x = np.asarray(Image.open(a / f).convert('RGBA'), dtype=float)
        y = np.asarray(Image.open(b / f).convert('RGBA'), dtype=float)
        if x.shape != y.shape:
            return 255.0
        # Premultiply so colour noise under transparent pixels is ignored;
        # re-encoded but otherwise identical PNGs then score near zero.
        px = np.dstack([x[..., :3] * x[..., 3:] / 255, x[..., 3:]])
        py = np.dstack([y[..., :3] * y[..., 3:] / 255, y[..., 3:]])
        worst = max(worst, float(np.abs(px - py).mean()))
    return worst


def write_report(src: Path, out: Path, scans, pick: dict[str, str]) -> None:
    """Write report.html comparing old and new artwork."""
    rel = Path(os.path.relpath(src, out.parent))

    def img(theme: str, name: str) -> str:
        f = preview(src / theme, scans[theme][name])
        return f'<img src="{html.escape(str(rel / theme / f))}" loading="lazy">' if f else ''

    changed, added = [], []
    for name in sorted(pick):
        old = next((t for t in OLD if name in scans[t]), None)
        new = next((t for t in NEW if name in scans[t]), None)
        if old and new:
            score = diff_score(src / old, src / new, scans[old][name], scans[new][name])
            if score > 1.0:
                changed.append((score, name, old, new))
        elif new:
            added.append((name, new))

    def cell(name: str, *imgs: str, attrs: str = '') -> str:
        label = html.escape(name)
        return f'<div class="c"{attrs}>{"".join(imgs)}<span>{label}</span></div>'

    def group(theme: str, name: str) -> str:
        # Aliases are symlinks to one real file, so its stem identifies the
        # group; the page uses it to highlight every alias of a pick.
        f = preview(src / theme, scans[theme][name])
        return (src / theme / f).resolve().stem if f else name

    body = [f'<h2>Old vs new artwork ({len(changed)}), most changed first</h2>']
    body.append('<div class="g">')
    # biggest redesigns first; the tail is mostly re-rendered lookalikes
    for _, name, old, new in sorted(changed, key=lambda c: (-c[0], c[1])):
        attrs = f' data-name="{html.escape(name)}" data-group="{html.escape(group(new, name))}"'
        body.append(cell(name, img(old, name), img(new, name), attrs=attrs))
    body.append(f'</div><h2>Added, not in Fedora 12 ({len(added)})</h2><div class="g">')
    body += [cell(name, img(t, name)) for name, t in added]
    body.append('</div>')
    (out.parent / 'report.html').write_text(
        REPORT.replace('{body}', '\n'.join(body)), encoding='utf-8')
    print(f'report: {len(changed)} changed, {len(added)} added')


REPORT = r"""<!doctype html><meta charset="utf-8"><title>ArchaismOk icon diff</title>
<style>
:root{--bg:#fff;--fg:#222;--hl:#ffe9a8}
@media (prefers-color-scheme:dark){:root{--bg:#1e1e1e;--fg:#ddd;--hl:#5a4a1a}}
body{background:var(--bg);color:var(--fg);font:13px sans-serif;margin:16px}
.g{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:6px}
.c{text-align:center;padding:6px;border-radius:4px;overflow-wrap:anywhere}
.c[data-name]{cursor:pointer}
.c[data-name]:hover{outline:1px solid var(--fg)}
.c.new{background:var(--hl)}
#status{position:sticky;top:0;background:var(--bg);padding:6px 0;font-weight:bold}
.c img{width:48px;height:48px;object-fit:contain;margin:2px}
.c span{display:block;font-size:11px}
</style>
<p>Left = Fedora 12, right = Arch. Click an icon to take the new artwork
(highlighted); click again to undo. Picks are saved to prefer-new.txt when
this page is opened through serve.py; rerun build.py to apply them.</p>
<div id="status">loading…</div>
{body}
<script>
const cells = [...document.querySelectorAll('.c[data-name]')];
const status = document.getElementById('status');
let chosen = new Set();

function paint() {
  const groups = new Set(
      cells.filter((c) => chosen.has(c.dataset.name)).map((c) => c.dataset.group));
  cells.forEach((c) => c.classList.toggle('new', groups.has(c.dataset.group)));
  status.textContent = `${chosen.size} picked`;
}

async function save() {
  const body = [...chosen].sort().join('\n') + '\n';
  const r = await fetch('prefer-new.txt', {method: 'POST', body}).catch(() => null);
  status.textContent += r && r.ok ? ' · saved' : ' · NOT saved, open via serve.py';
}

for (const c of cells) {
  c.onclick = () => {
    // Unpicking any alias unpicks the whole group, matching how build.py
    // expands a pick to all of its aliases.
    const picked = cells.filter(
        (x) => x.dataset.group === c.dataset.group && chosen.has(x.dataset.name));
    if (picked.length) {
      picked.forEach((x) => chosen.delete(x.dataset.name));
    } else {
      chosen.add(c.dataset.name);
    }
    paint();
    save();
  };
}

fetch('prefer-new.txt', {cache: 'no-store'})
    .then((r) => (r.ok ? r.text() : ''))
    .catch(() => '')
    .then((t) => {
      chosen = new Set(t.split('\n').map((s) => s.replace(/#.*/, '').trim()).filter(Boolean));
      paint();
    });
</script>
"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--src', type=Path, default=HERE / 'sources')
    ap.add_argument('--out', type=Path, default=HERE / 'ArchaismOk')
    ap.add_argument('--no-report', action='store_true')
    args = ap.parse_args()
    src, out = args.src.resolve(), args.out.resolve()

    scans = {t: scan(src / t) for t in OLD + NEW}
    pick = choose(src, scans, load_prefer())

    if out.exists():
        shutil.rmtree(out)
    dirs: set[str] = set()
    for name, theme in pick.items():
        for f in scans[theme][name]:
            dst = out / f
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(load(src / theme / f))
            dirs.add(str(Path(f).parent))
    dedupe(out)
    write_index(src, out, dirs)

    # self-check: relinking must not change any icon's content
    for name, theme in pick.items():
        for f in scans[theme][name]:
            assert (out / f).read_bytes() == load(src / theme / f), f

    counts = {t: sum(v == t for v in pick.values()) for t in OLD + NEW}
    print(f'{out}: {len(pick)} icons', counts)
    if not args.no_report:
        write_report(src, out, scans, pick)


if __name__ == '__main__':
    main()
