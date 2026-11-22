OUTDIR = ../gtk-3.0/img
SVGS = $(wildcard *.svg)
PNGS = $(SVGS:%.svg=$(OUTDIR)/%.png) $(SVGS:%.svg=$(OUTDIR)/%@2.png)

all: $(PNGS)

clean:
	-rm -f $(PNGS)

# The arrow SVGs are in CSS pixels, so render them 1:1 with rsvg-convert;
# Inkscape at 90 dpi would shrink them to 12px.
COMBO = $(wildcard combo-arrow*.svg)
$(COMBO:%.svg=$(OUTDIR)/%.png): $(OUTDIR)/%.png: %.svg
	rsvg-convert -z 1 $< -o $@
$(COMBO:%.svg=$(OUTDIR)/%@2.png): $(OUTDIR)/%@2.png: %.svg
	rsvg-convert -z 2 $< -o $@

$(OUTDIR)/%.png: %.svg
	inkscape $< --export-type=png --export-filename=$@ --export-dpi=90 --export-background-opacity=0

$(OUTDIR)/%@2.png: %.svg
	inkscape $< --export-type=png --export-filename=$@ --export-dpi=180 --export-background-opacity=0
