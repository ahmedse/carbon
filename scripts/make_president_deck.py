"""AASTMT president brief — 10 slides.
Focus: Pulse as a next-generation coworker + Data Trust as the data-quality
solver that hosts domain apps AND AI apps/engines.
"""
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

# ── palette ──────────────────────────────────────────────────────────────
INK     = RGBColor(0x0B, 0x12, 0x20)   # titles
SLATE   = RGBColor(0x33, 0x41, 0x55)   # body
MUTED   = RGBColor(0x6B, 0x78, 0x90)   # secondary
LINE    = RGBColor(0xE4, 0xE9, 0xF1)   # hairline
SHADOW  = RGBColor(0xDD, 0xE3, 0xEE)   # soft shadow
PAPER   = RGBColor(0xFF, 0xFF, 0xFF)
CANVAS  = RGBColor(0xF5, 0xF8, 0xFC)   # panel
PRIMARY = RGBColor(0x25, 0x63, 0xEB)   # blue
DEEP    = RGBColor(0x17, 0x2B, 0x63)   # deep navy-blue
INDIGO  = RGBColor(0x43, 0x38, 0xCA)
TEAL    = RGBColor(0x0E, 0x94, 0x88)
AMBER   = RGBColor(0xD9, 0x77, 0x06)
GREEN   = RGBColor(0x15, 0x9E, 0x5B)
RED     = RGBColor(0xB4, 0x23, 0x18)
CHIP    = RGBColor(0xEC, 0xF1, 0xFE)
DARKCARD= RGBColor(0x16, 0x22, 0x40)
LIGHTB  = RGBColor(0xB9, 0xCB, 0xEE)
FAINT   = RGBColor(0x9D, 0xB8, 0xF0)

EMU_W, EMU_H = Inches(13.333), Inches(7.5)
FONT = "Calibri"

prs = Presentation()
prs.slide_width = EMU_W
prs.slide_height = EMU_H
BLANK = prs.slide_layouts[6]
TOTAL = 10


def _solid(shp, color, line=None, line_w=None):
    shp.fill.solid()
    shp.fill.fore_color.rgb = color
    if line is None:
        shp.line.fill.background()
    else:
        shp.line.color.rgb = line
        shp.line.width = line_w or Pt(1)
    shp.shadow.inherit = False


def rectp(slide, x, y, w, h, color, line=None, line_w=None, round_=False):
    shp = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE if round_ else MSO_SHAPE.RECTANGLE, x, y, w, h)
    _solid(shp, color, line, line_w)
    return shp


def card(slide, x, y, w, h, fill=PAPER, line=LINE, round_=True, soft=True):
    if soft:
        off = Pt(5)
        sh = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE if round_ else MSO_SHAPE.RECTANGLE,
            x + off, y + off, w, h)
        _solid(sh, SHADOW)
    return rectp(slide, x, y, w, h, fill, line=line, line_w=Pt(1), round_=round_)


def text(slide, x, y, w, h, paras, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP,
         gap=6, ls=1.0):
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    for m in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
        setattr(tf, m, 0)
    for i, para in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(gap)
        p.space_before = Pt(0)
        p.line_spacing = ls
        for (t, sz, col, bold) in para:
            r = p.add_run()
            r.text = t
            r.font.size = Pt(sz)
            r.font.color.rgb = col
            r.font.bold = bold
            r.font.name = FONT
    return tb


def bullet_list(slide, x, y, w, items, size=15, gap=13, dot=PRIMARY, body=SLATE):
    tb = slide.shapes.add_textbox(x, y, w, Inches(4.5))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = 0
    tf.margin_top = 0
    for i, it in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(gap)
        p.line_spacing = 1.05
        d = p.add_run(); d.text = "\u25CF  "
        d.font.size = Pt(size - 4); d.font.color.rgb = dot; d.font.bold = True
        d.font.name = FONT
        for j, seg in enumerate(it.split("**")):
            if not seg:
                continue
            r = p.add_run(); r.text = seg
            r.font.size = Pt(size); r.font.color.rgb = body
            r.font.bold = (j % 2 == 1); r.font.name = FONT
    return tb


def header(slide, n, tag, title, takeaway, accent=PRIMARY):
    rectp(slide, Inches(0.0), Inches(0.0), Inches(0.22), EMU_H, accent)
    text(slide, Inches(0.7), Inches(0.42), Inches(9.5), Inches(0.32),
         [[(tag, 12.5, accent, True)]], gap=0)
    text(slide, Inches(11.35), Inches(0.42), Inches(1.3), Inches(0.32),
         [[(f"{n:02d} / {TOTAL:02d}", 12.5, MUTED, True)]], align=PP_ALIGN.RIGHT, gap=0)
    text(slide, Inches(0.7), Inches(0.78), Inches(12.0), Inches(0.95),
         [[(title, 29, INK, True)]], gap=0, ls=0.98)
    card(slide, Inches(0.7), Inches(1.66), Inches(11.9), Inches(0.6),
         fill=CANVAS, line=None, soft=False)
    rectp(slide, Inches(0.7), Inches(1.66), Pt(4), Inches(0.6), accent)
    text(slide, Inches(0.95), Inches(1.66), Inches(11.5), Inches(0.6),
         [[("Bottom line:  ", 13, accent, True), (takeaway, 13, SLATE, False)]],
         anchor=MSO_ANCHOR.MIDDLE, gap=0)


def newslide(dark=False):
    s = prs.slides.add_slide(BLANK)
    rectp(s, 0, 0, EMU_W, EMU_H, INK if dark else PAPER)
    return s


def valuebar(slide, y, lead, rest, accent=PRIMARY):
    card(slide, Inches(0.7), y, Inches(11.9), Inches(0.62), fill=CHIP, line=None, soft=False)
    rectp(slide, Inches(0.7), y, Pt(4), Inches(0.62), accent)
    text(slide, Inches(0.95), y, Inches(11.5), Inches(0.62),
         [[(lead, 13.5, DEEP, True), (rest, 13.5, SLATE, False)]],
         anchor=MSO_ANCHOR.MIDDLE, gap=0)


def flow(slide, x, y, w, h, head, sub, col, headcol=PAPER):
    card(slide, x, y, w, h, fill=PAPER, round_=True)
    rectp(slide, x, y, w, Inches(0.5), col, round_=True)
    rectp(slide, x, y + Inches(0.25), w, Inches(0.28), col)
    text(slide, x + Inches(0.1), y, w - Inches(0.2), Inches(0.5),
         [[(head, 12.5, headcol, True)]], align=PP_ALIGN.CENTER,
         anchor=MSO_ANCHOR.MIDDLE, gap=0)
    text(slide, x + Inches(0.14), y + Inches(0.62), w - Inches(0.28), h - Inches(0.7),
         [[(sub, 11.5, SLATE, False)]], align=PP_ALIGN.CENTER, gap=0, ls=1.03)


def arrow(slide, x, y, w, col=PRIMARY):
    a = slide.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, x, y, w, Inches(0.3))
    _solid(a, col)


# ══════════════════════════════════════════ Slide 1 — Title
s = newslide(dark=True)
rectp(s, 0, 0, Inches(5.2), EMU_H, DEEP)
rectp(s, Inches(5.2), 0, Pt(5), EMU_H, TEAL)
text(s, Inches(0.7), Inches(0.65), Inches(4.3), Inches(0.4),
     [[("AASTMT \u00b7 DATA TRUST PLATFORM", 13, FAINT, True)]], gap=0)
text(s, Inches(0.7), Inches(1.9), Inches(4.3), Inches(3.2),
     [[("Pulse", 62, PAPER, True)],
      [("a next-generation", 24, LIGHTB, False)],
      [("coworker", 40, TEAL, True)]], gap=2, ls=0.98)
rectp(s, Inches(0.72), Inches(5.25), Inches(2.2), Pt(3), TEAL)
text(s, Inches(0.7), Inches(5.5), Inches(4.3), Inches(1.4),
     [[("on the Data Trust platform \u2014", 13.5, LIGHTB, False)],
      [("the base that fixes data quality", 13.5, LIGHTB, False)],
      [("and hosts every app.", 13.5, LIGHTB, False)]], gap=2, ls=1.05)
pill = [("PULSE", "A coworker for staff and students", TEAL),
        ("DATA TRUST", "One base \u2014 clean data, all apps, AI engines", PRIMARY),
        ("DOMAIN APPS", "Incl. AI apps & engines \u00b7 Carbon (live) \u00b7 Performarc", AMBER)]
for i, (h, b, c) in enumerate(pill):
    y = Inches(1.5 + i * 1.55)
    card(s, Inches(5.8), y, Inches(6.85), Inches(1.3), fill=DARKCARD, line=None)
    rectp(s, Inches(5.8), y, Pt(6), Inches(1.3), c, round_=True)
    text(s, Inches(6.1), y, Inches(6.4), Inches(1.3),
         [[(h, 18, PAPER, True)], [(b, 13, LIGHTB, False)]],
         anchor=MSO_ANCHOR.MIDDLE, gap=3)
text(s, Inches(5.8), Inches(6.7), Inches(6.8), Inches(0.4),
     [[("A 10-minute brief for the President", 12.5, MUTED, False)]], gap=0)

# ══════════════════════════════════════════ Slide 2 — Pulse: what it is
s = newslide()
header(s, 2, "PULSE \u00b7 THE COWORKER", "A coworker that does the work, not a chatbot",
       "It runs whole business processes on our own data, recovers when a step fails, and gets better with use.",
       accent=TEAL)
sub = [
    ("Knows our world", "Works from AASTMT's own approved data and rules \u2014 not the open internet.", TEAL),
    ("Runs real workflows", "Executes multi-step tasks and specific business processes, end to end.", PRIMARY),
    ("Learns and grows", "Remembers context, learns our terms, and improves with every use.", INDIGO),
    ("Resilient and safe", "Recovers when a step fails; suggests and lets a person approve.", GREEN),
]
cw, gap = Inches(2.86), Inches(0.24)
for i, (h, b, c) in enumerate(sub):
    x = Inches(0.7) + i * (cw + gap)
    card(s, x, Inches(2.65), cw, Inches(3.7))
    rectp(s, x, Inches(2.65), cw, Inches(0.14), c, round_=True)
    disc = s.shapes.add_shape(MSO_SHAPE.OVAL, x + Inches(0.24), Inches(2.95),
                              Inches(0.7), Inches(0.7)); _solid(disc, c)
    text(s, x + Inches(0.24), Inches(2.95), Inches(0.7), Inches(0.7),
         [[(str(i + 1), 22, PAPER, True)]], align=PP_ALIGN.CENTER,
         anchor=MSO_ANCHOR.MIDDLE, gap=0)
    text(s, x + Inches(0.26), Inches(3.85), cw - Inches(0.5), Inches(0.6),
         [[(h, 16.5, INK, True)]], gap=0)
    text(s, x + Inches(0.26), Inches(4.45), cw - Inches(0.5), Inches(1.8),
         [[(b, 13, SLATE, False)]], gap=0, ls=1.08)

# ══════════════════════════════════════════ Slide 3 — Pulse value for staff
s = newslide()
header(s, 3, "PULSE \u00b7 VALUE FOR STAFF", "Give staff back a day a week",
       "The repetitive desk work is done for them \u2014 they spend time on people, not paperwork.",
       accent=TEAL)
bullet_list(s, Inches(0.7), Inches(2.7), Inches(6.5), [
    "**Answers routine questions** from our rules and data \u2014 no more repeating replies.",
    "**Runs whole processes** \u2014 multi-step tasks done end to end, not just answers.",
    "**Drafts reports and letters** from real data; a person reviews and approves.",
    "**Resilient and safe** \u2014 recovers from failures; every action needs a human yes.",
], size=15.5, gap=15, dot=TEAL)
card(s, Inches(7.55), Inches(2.7), Inches(5.05), Inches(3.7), fill=CANVAS)
text(s, Inches(7.8), Inches(2.9), Inches(4.6), Inches(0.4),
     [[("THE SAME TASK, TWO WAYS", 12, MUTED, True)]], gap=0)
flow(s, Inches(7.85), Inches(3.45), Inches(2.1), Inches(1.55),
     "TODAY", "Hours in emails, forms, and repeated reports.", RED)
arrow(s, Inches(10.02), Inches(4.05), Inches(0.5), TEAL)
flow(s, Inches(10.6), Inches(3.45), Inches(1.85), Inches(1.55),
     "WITH PULSE", "Review one clean draft. Done.", GREEN)
text(s, Inches(7.85), Inches(5.25), Inches(4.6), Inches(1.0),
     [[("Value:  ", 14, TEAL, True),
       ("most repeated-question and report time returns as time for real work.",
        14, SLATE, False)]], gap=0, ls=1.08)

# ══════════════════════════════════════════ Slide 4 — Pulse student coach
s = newslide()
header(s, 4, "PULSE \u00b7 A COACH FOR STUDENTS", "The right answer, at the right moment",
       "A guided coach on our website \u2014 the President can test it personally.", accent=TEAL)
bullet_list(s, Inches(0.7), Inches(2.7), Inches(6.6), [
    "**Answers any time** \u2014 admissions, courses, deadlines, rules \u2014 in plain language.",
    "**Guides step by step** instead of leaving students lost in menus.",
    "**Hands off to the right office** when a person is needed.",
    "**Fewer dropped applications**, lighter load on advising staff.",
], size=15.5, gap=15, dot=TEAL)
px, py = Inches(8.25), Inches(2.65)
card(s, px, py, Inches(3.75), Inches(3.85), fill=INK, line=None)
rectp(s, px + Inches(0.16), py + Inches(0.33), Inches(3.43), Inches(3.2), PAPER, round_=True)
rectp(s, px + Inches(1.45), py + Inches(0.14), Inches(0.85), Inches(0.1), DARKCARD, round_=True)
rectp(s, px + Inches(1.05), py + Inches(0.55), Inches(2.4), Inches(0.7), CHIP, round_=True)
text(s, px + Inches(1.15), py + Inches(0.55), Inches(2.2), Inches(0.7),
     [[("Which courses do I need next term?", 10.5, DEEP, True)]],
     anchor=MSO_ANCHOR.MIDDLE, gap=0, ls=1.0)
rectp(s, px + Inches(0.3), py + Inches(1.4), Inches(2.55), Inches(1.05),
      RGBColor(0xEC, 0xFD, 0xF5), round_=True)
text(s, px + Inches(0.4), py + Inches(1.4), Inches(2.35), Inches(1.05),
     [[("3 core courses. Deadline: May 2.", 11, RGBColor(0x0B, 0x5C, 0x45), False)]],
     anchor=MSO_ANCHOR.MIDDLE, gap=0, ls=1.03)
rectp(s, px + Inches(0.3), py + Inches(2.65), Inches(3.15), Inches(0.6), TEAL, round_=True)
text(s, px + Inches(0.3), py + Inches(2.65), Inches(3.15), Inches(0.6),
     [[("\u2192  Go to enrolment", 12, PAPER, True)]], align=PP_ALIGN.CENTER,
     anchor=MSO_ANCHOR.MIDDLE, gap=0)

# ══════════════════════════════════════════ Slide 5 — Why next-gen
s = newslide(dark=True)
rectp(s, 0, 0, Inches(0.22), EMU_H, TEAL)
text(s, Inches(0.7), Inches(0.42), Inches(9), Inches(0.32),
     [[("PULSE \u00b7 WHY IT IS NEXT-GENERATION", 12.5, TEAL, True)]], gap=0)
text(s, Inches(11.35), Inches(0.42), Inches(1.3), Inches(0.32),
     [[(f"05 / {TOTAL:02d}", 12.5, MUTED, True)]], align=PP_ALIGN.RIGHT, gap=0)
text(s, Inches(0.7), Inches(0.82), Inches(12), Inches(0.9),
     [[("The class of system top organisations now expect", 27, PAPER, True)]], gap=0)
text(s, Inches(0.7), Inches(1.75), Inches(12), Inches(0.5),
     [[("Built here, on our own systems \u2014 not a subscription that reads our private data.",
        13.5, LIGHTB, False)]], gap=0)
grid = [
    ("Grounded", "Works only from our approved data \u2014 with the source shown.", TEAL),
    ("Runs workflows", "Executes multi-step business processes end to end \u2014 agentic.", PRIMARY),
    ("Reasons & self-checks", "Checks its own work before acting \u2014 fewer wrong answers.", INDIGO),
    ("Learns & grows", "Remembers, learns our terms, and improves with use.", AMBER),
    ("Resilient", "Recovers from failures and keeps the task moving.", GREEN),
    ("Controlled & ours", "Human approval for sensitive actions; runs inside AASTMT.", RGBColor(0x0E, 0xA5, 0xC9)),
]
gw, gh, gx, gy = Inches(3.86), Inches(1.75), Inches(0.7), Inches(2.5)
gapx, gapy = Inches(0.25), Inches(0.3)
for i, (h, b, c) in enumerate(grid):
    col, row = i % 3, i // 3
    x = gx + col * (gw + gapx)
    y = gy + row * (gh + gapy)
    card(s, x, y, gw, gh, fill=DARKCARD, line=None, soft=False)
    rectp(s, x, y, Pt(6), gh, c, round_=True)
    text(s, x + Inches(0.28), y + Inches(0.2), gw - Inches(0.5), Inches(0.5),
         [[(h, 16.5, PAPER, True)]], gap=0)
    text(s, x + Inches(0.28), y + Inches(0.72), gw - Inches(0.5), Inches(1.0),
         [[(b, 12.5, LIGHTB, False)]], gap=0, ls=1.05)

# ══════════════════════════════════════════ Slide 6 — Data Trust quality solver
s = newslide()
header(s, 6, "DATA TRUST \u00b7 THE DATA-QUALITY SOLVER",
       "It fixes the data problems that break reports and AI",
       "Bad data is the root cause of wrong reports and unreliable AI \u2014 Data Trust removes it at the source.",
       accent=PRIMARY)
probs = [
    ("Scattered data", "One governed place \u2014 every dataset has an owner and a version."),
    ("No one trusts the numbers", "Automatic quality checks; a clear pass/fail on each dataset."),
    ("\u201cWhere did this come from?\u201d", "Full history \u2014 always able to show which data produced a result."),
    ("Duplicate, inconsistent codes", "Shared reference lists keep everyone on the same values."),
    ("Months lost cleaning data", "Approved datasets are reused, not rebuilt each time."),
    ("Stale data slips through", "Freshness rules flag data that is too old to use."),
]
cw2, gap2 = Inches(3.86), Inches(0.25)
for i, (p, sol) in enumerate(probs):
    col, row = i % 3, i // 3
    x = Inches(0.7) + col * (cw2 + gap2)
    y = Inches(2.7) + row * Inches(1.85)
    card(s, x, y, cw2, Inches(1.6))
    rectp(s, x, y, cw2, Pt(5), PRIMARY, round_=True)
    text(s, x + Inches(0.22), y + Inches(0.16), cw2 - Inches(0.4), Inches(0.55),
         [[("\u2715  " + p, 13.5, RED, True)]], gap=0)
    text(s, x + Inches(0.22), y + Inches(0.72), cw2 - Inches(0.4), Inches(0.85),
         [[("\u2192  ", 12.5, GREEN, True), (sol, 12.5, SLATE, False)]], gap=0, ls=1.05)

# ══════════════════════════════════════════ Slide 7 — Data Trust hosts apps + AI
s = newslide()
header(s, 7, "DATA TRUST \u00b7 ONE BASE FOR EVERY APP AND AI ENGINE",
       "Domain apps \u2014 including the AI apps and engines \u2014 all run on one trusted base",
       "Clean data is owned and checked once \u2014 every app and every AI reuses it, so nothing is built twice.",
       accent=PRIMARY)
apps = [("Carbon", TEAL, "live"), ("Performarc", PRIMARY, "planned"),
        ("Sustainability", AMBER, "planned"), ("Pulse AI engine", INDIGO, "live")]
aw, agap = Inches(2.78), Inches(0.2)
for i, (nm, c, st) in enumerate(apps):
    x = Inches(0.7) + i * (aw + agap)
    card(s, x, Inches(2.65), aw, Inches(1.25))
    rectp(s, x, Inches(2.65), aw, Pt(6), c, round_=True)
    tail = " \u00b7 AI engine" if "AI" in nm else " app"
    text(s, x, Inches(2.72), aw, Inches(1.15),
         [[(nm, 15.5, INK, True)], [(st + tail, 11, MUTED, False)]],
         align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, gap=2)
    rectp(s, x + aw / 2 - Pt(1.5), Inches(3.9), Pt(3), Inches(0.4), LINE)
card(s, Inches(0.7), Inches(4.35), Inches(11.9), Inches(1.7), fill=DEEP, line=None)
rectp(s, Inches(0.7), Inches(4.35), Inches(11.9), Pt(6), TEAL, round_=True)
text(s, Inches(1.0), Inches(4.5), Inches(11.3), Inches(0.5),
     [[("DATA TRUST  \u2014  clean \u00b7 approved \u00b7 versioned data", 18, PAPER, True)]], gap=0)
text(s, Inches(1.0), Inches(5.1), Inches(11.3), Inches(0.85),
     [[("Owner + quality checks + version on every dataset   \u00b7   domain apps INCLUDE the AI apps and engines   \u00b7   one source of truth for reports and AI",
        12.5, LIGHTB, False)]], gap=0, ls=1.05)
valuebar(s, Inches(6.25), "Value:  ",
         "add a new app cheaply, and trust every result \u2014 because the data underneath is already clean.",
         accent=PRIMARY)

# ══════════════════════════════════════════ Slide 8 — Carbon
s = newslide()
header(s, 8, "CARBON \u00b7 PROOF, ALREADY LIVE",
       "Defensible emissions numbers for rankings and accreditation",
       "The easiest value to see \u2014 it runs today and produces reports without manual rebuilding.",
       accent=AMBER)
bullet_list(s, Inches(0.7), Inches(2.7), Inches(6.4), [
    "**Tracks emissions** with a clear, recognised standard.",
    "**Evidence attached** to every number, with full history.",
    "**Reports for rankings & accreditation** \u2014 no manual rebuild.",
    "**Lower risk** of a wrong figure in an official submission.",
], size=15.5, gap=15, dot=AMBER)
flow(s, Inches(7.5), Inches(2.85), Inches(2.25), Inches(1.7),
     "SPREADSHEET", "Manual, scattered, an error waiting to happen.", RED)
arrow(s, Inches(9.82), Inches(3.55), Inches(0.55), AMBER)
flow(s, Inches(10.42), Inches(2.85), Inches(2.18), Inches(1.7),
     "CARBON APP", "One clean, sourced, defensible number.", GREEN)
card(s, Inches(7.5), Inches(4.8), Inches(5.1), Inches(1.55), fill=CANVAS)
text(s, Inches(7.75), Inches(4.98), Inches(4.6), Inches(1.3),
     [[("\u25CF LIVE TODAY", 15, GREEN, True)],
      [("Running for AASTMT now \u2014 the working proof that the base and the apps deliver.",
        13, SLATE, False)]], gap=6, ls=1.06)

# ══════════════════════════════════════════ Slide 9 — Next apps + rollout
s = newslide()
header(s, 9, "NEXT APPS & 12-MONTH ROLLOUT",
       "More value on the same base \u2014 staged and low-risk",
       "Each stage ends with a result you can see; we continue only if it delivered. No new hardware.",
       accent=PRIMARY)
nxt = [("Performarc \u2014 Academic KPIs", PRIMARY,
        "One place for KPIs, on time \u2014 no chasing spreadsheets."),
       ("Sustainability \u2014 Goals", GREEN,
        "Goals tracked continuously \u2014 a report is always ready.")]
for i, (h, c, b) in enumerate(nxt):
    x = Inches(0.7) + i * Inches(6.1)
    card(s, x, Inches(2.6), Inches(5.85), Inches(1.35))
    rectp(s, x, Inches(2.6), Pt(6), Inches(1.35), c, round_=True)
    text(s, x + Inches(0.28), Inches(2.72), Inches(5.4), Inches(1.15),
         [[(h, 15.5, INK, True)], [(b, 12.5, SLATE, False)]],
         anchor=MSO_ANCHOR.MIDDLE, gap=3)
phases = [("MONTHS 1\u20134", TEAL, ["Student coach on the website", "Data Trust office started"]),
          ("MONTHS 5\u20138", PRIMARY, ["Staff coworker in 1\u20132 departments", "First research dataset reused"]),
          ("MONTHS 9\u201312", AMBER, ["Performarc & Sustainability", "A second team reuses the data"])]
pw, pgap = Inches(3.6), Inches(0.55)
for i, (h, c, its) in enumerate(phases):
    x = Inches(0.7) + i * (pw + pgap)
    y = Inches(4.35)
    card(s, x, y, pw, Inches(2.05))
    rectp(s, x, y, pw, Inches(0.55), c, round_=True)
    rectp(s, x, y + Inches(0.3), pw, Inches(0.27), c)
    text(s, x, y, pw, Inches(0.55), [[(h, 14.5, PAPER, True)]],
         align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, gap=0)
    bullet_list(s, x + Inches(0.26), y + Inches(0.72), pw - Inches(0.5), its,
                size=13, gap=8, dot=c)
    if i < 2:
        d = s.shapes.add_shape(MSO_SHAPE.DIAMOND, x + pw + Inches(0.07),
                               y + Inches(0.65), Inches(0.4), Inches(0.4))
        _solid(d, INK)

# ══════════════════════════════════════════ Slide 10 — The ask
s = newslide(dark=True)
rectp(s, 0, 0, Inches(5.0), EMU_H, DEEP)
rectp(s, Inches(5.0), 0, Pt(5), EMU_H, TEAL)
text(s, Inches(0.7), Inches(0.7), Inches(4), Inches(0.4),
     [[("THE ASK", 13, FAINT, True)]], gap=0)
text(s, Inches(0.7), Inches(1.7), Inches(4.1), Inches(2.2),
     [[("Approve", 34, LIGHTB, False)], [("to start.", 54, PAPER, True)]], gap=4, ls=0.98)
text(s, Inches(0.7), Inches(4.3), Inches(4.1), Inches(2.4),
     [[("We already own the platform", 15, LIGHTB, True)],
      [("and the computing.", 15, LIGHTB, True)],
      [("", 8, PAPER, False)],
      [("First working result within", 13.5, FAINT, False)],
      [("the first stage.", 13.5, FAINT, False)]], gap=4, ls=1.05)
asks = [("Start where it shows fast", "Student coach + Data Trust office first.", TEAL),
        ("One or two departments", "Partners for the staff coworker.", PRIMARY),
        ("Use the computing we own", "Access to existing systems for research.", AMBER),
        ("A small dedicated team", "No new hardware spend.", GREEN)]
for i, (h, b, c) in enumerate(asks):
    y = Inches(1.15 + i * 1.4)
    card(s, Inches(5.55), y, Inches(7.1), Inches(1.2), fill=DARKCARD, line=None)
    rectp(s, Inches(5.55), y, Pt(6), Inches(1.2), c, round_=True)
    text(s, Inches(5.9), y, Inches(6.6), Inches(1.2),
         [[(h, 17, PAPER, True)], [(b, 13, LIGHTB, False)]],
         anchor=MSO_ANCHOR.MIDDLE, gap=3)

out = "/home/ahmed/ws/carbon/docs/PRESIDENT-BRIEF-AASTMT.pptx"
prs.save(out)
print("SAVED", out)
