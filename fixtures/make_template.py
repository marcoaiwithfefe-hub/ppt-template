# Builds a made-up HK company template: navy bar, orange accent, Traditional Chinese title font, footer with company name.
import sys
from pptx import Presentation
from pptx.util import Emu, Pt
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE

NAVY = RGBColor(0x0B, 0x2A, 0x4A)
ORANGE = RGBColor(0xF2, 0x8C, 0x28)
out = sys.argv[1]
prs = Presentation()
prs.slide_width, prs.slide_height = Emu(12192000), Emu(6858000)
master = prs.slide_masters[0]
W, H = prs.slide_width, prs.slide_height
# python-pptx cannot add shapes to a master, so draw them on a scratch slide and move the XML into the master's shape tree.
scratch = prs.slides.add_slide(prs.slide_layouts[6])

bar = scratch.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, W, Emu(520000))
bar.fill.solid(); bar.fill.fore_color.rgb = NAVY; bar.line.fill.background()
acc = scratch.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, Emu(520000), W, Emu(60000))
acc.fill.solid(); acc.fill.fore_color.rgb = ORANGE; acc.line.fill.background()
foot = scratch.shapes.add_textbox(Emu(400000), H - Emu(420000), Emu(6000000), Emu(300000))
p = foot.text_frame.paragraphs[0]; r = p.add_run(); r.text = "匯通物流有限公司 Wui Tung Logistics Ltd.  |  內部文件"
r.font.size = Pt(11); r.font.color.rgb = NAVY; r.font.name = "Microsoft JhengHei"

tree = master.shapes._spTree
for el in [bar._element, acc._element, foot._element]:
    tree.append(el)
sld_ids = prs.slides._sldIdLst
rid = sld_ids[0].rId
prs.part.drop_rel(rid)
sld_ids.remove(sld_ids[0])

for layout in prs.slide_layouts:
    for ph in layout.placeholders:
        for para in ph.text_frame.paragraphs:
            for run in para.runs:
                run.font.name = "Microsoft JhengHei"
for ph in master.placeholders:
    tf = ph.text_frame
    for para in tf.paragraphs:
        para.font.name = "Microsoft JhengHei"
        para.font.color.rgb = NAVY

s = prs.slides.add_slide(prs.slide_layouts[0])
s.shapes.title.text = "匯通物流 2027 年度計劃"
s.placeholders[1].text = "營運部 · 內部簡報"
s2 = prs.slides.add_slide(prs.slide_layouts[1])
s2.shapes.title.text = "重點"
s2.placeholders[1].text = "示範內容"
prs.save(out)
print("saved", out)
