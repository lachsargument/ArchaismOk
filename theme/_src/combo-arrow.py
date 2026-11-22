#!/usr/bin/env python3
"""Write the Clearlooks combo box arrow (two stacked chevrons) as SVG.

GTK3 cannot run the Clearlooks engine, so its drawing code is ported here
and baked into images. The geometry follows clearlooks_draw_combo_arrow()
and clearlooks_draw_normal_arrow() in gtk-engines 2.18.4
(engines/clearlooks/src/clearlooks_draw.c), and the colours follow the
Clearlooks gtkrc with bg_color #EDECEB.

Usage:
    python3 combo-arrow.py && make
"""

import math
from pathlib import Path

# The only input not fixed by the source: GtkArrow draws into an extent
# of floor(arrow-size * 0.7), where GtkComboBox raises arrow-size (default
# 15) to the font height, so the arrow grows with the font. 13 is what
# Fedora 12 used at its default font; the odd size also puts the arrow
# axis on a pixel centre.
EXTENT = 13

FG = '#000000'  # fg[NORMAL], also used for PRELIGHT and ACTIVE
FG_INSENSITIVE = '#a9a5a2'  # darker(bg_color) = shade 0.7
EMBOSS = '#ffffff'  # shade[0] = shade 1.15 of bg_color, clipped to white


def normal_arrow(width: float, height: float) -> str:
    """Path of clearlooks_draw_normal_arrow() before its translate."""
    aw = min(height * 2.0 + max(1.0, math.ceil(height * 2.0 / 6.0 * 2.0) / 2.0) / 2.0, width)
    lw2 = max(1.0, math.ceil(aw / 6.0 * 2.0) / 2.0) / 2.0
    ah = aw / 2.0 + lw2
    r = 2 * lw2
    cy = ah - 2 * lw2 - 2 * lw2 * math.sqrt(2)
    s = r / math.sqrt(2)
    # cairo_arc_negative from 135 to 45 degrees is a counter-clockwise
    # (sweep 0) arc through the bottom of the circle.
    d = (
        f'M {-aw / 2} {lw2} L {-aw / 2 + lw2} 0 '
        f'L {-s} {cy + s} A {r} {r} 0 0 0 {s} {cy + s} '
        f'L {aw / 2 - lw2} 0 L {aw / 2} {lw2} L 0 {ah} Z'
    )
    # the function translates by -arrow_height / 2 before drawing
    return f'<path transform="translate(0 {-ah / 2})" d="{d}"/>'


def combo_arrow(tx: float, ty: float, color: str) -> str:
    """Both chevrons of clearlooks_draw_combo_arrow(), centred on tx, ty."""
    aw = min(EXTENT * 2 / 3.0, EXTENT)
    ah = aw / 2.0
    off = (ah + ah) / 2.0  # gap_size equals arrow_height
    arrow = normal_arrow(aw, ah)
    return (
        f'<g fill="{color}">'
        f'<g transform="translate({tx} {ty - off}) rotate(180)">{arrow}</g>'
        f'<g transform="translate({tx} {ty + off})">{arrow}</g>'
        '</g>'
    )


def svg(body: str) -> str:
    """Wrap shapes in an EXTENT-sized SVG document."""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{EXTENT}" height="{EXTENT}" '
        f'viewBox="0 0 {EXTENT} {EXTENT}">{body}</svg>\n'
    )


def main() -> None:
    here = Path(__file__).resolve().parent
    c = EXTENT / 2.0
    (here / 'combo-arrow.svg').write_text(svg(combo_arrow(c, c, FG)))
    # insensitive arrows get a light emboss half a pixel down-right first
    (here / 'combo-arrow-insensitive.svg').write_text(
        svg(combo_arrow(c + 0.5, c + 0.5, EMBOSS) + combo_arrow(c, c, FG_INSENSITIVE))
    )


if __name__ == '__main__':
    main()
