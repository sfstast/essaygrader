import os
from pathlib import Path

import streamlit as st
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

MODEL = "claude-haiku-5-5"
APP_DIR = Path(__file__).resolve().parent
PENGUIN_PATH = APP_DIR / "assets" / "pip-penguin.jpg"

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600;9..144,700&family=Nunito:wght@500;600;700;800&display=swap');

html, body, [class*="st-"], [data-testid="stAppViewContainer"] {
  font-family: "Nunito", sans-serif;
}

[data-testid="stHeader"] {
  background: transparent;
}

[data-testid="stToolbar"] {
  visibility: hidden;
}

.stApp {
  background:
    radial-gradient(ellipse at 0% 0%, #ffe7c8 0%, transparent 42%),
    radial-gradient(ellipse at 100% 8%, #d8eef2 0%, transparent 40%),
    #f6efe4;
}

[data-testid="stSidebar"] {
  background: #1c2a38;
}

[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] .stMarkdown {
  color: #f6efe4;
}

[data-testid="stSidebar"] .stCaption,
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {
  color: #c9d4de !important;
}

[data-testid="stSidebar"] [data-testid="stSelectbox"] div[data-baseweb="select"] > div {
  background: #243648;
  border: 1px solid #3d5368;
}

[data-testid="stSidebar"] input {
  background: #243648 !important;
  color: #f6efe4 !important;
}

h1, h2, h3, .hero-title {
  font-family: "Fraunces", serif !important;
  letter-spacing: -0.02em;
}

.hero-card {
  display: flex;
  align-items: center;
  gap: 1.4rem;
  background: #fff8f0;
  border: 3px solid #1c2a38;
  border-radius: 28px;
  padding: 1.1rem 1.4rem 1.1rem 1.1rem;
  box-shadow: 8px 8px 0 #1c2a38;
  margin-bottom: 1.4rem;
}

.hero-copy h1 {
  margin: 0 0 0.35rem 0;
  font-size: 2.15rem;
  color: #1c2a38;
}

.hero-copy p {
  margin: 0;
  font-size: 1.05rem;
  color: #3d4f5f;
  line-height: 1.45;
}

.speech {
  display: inline-block;
  margin-top: 0.7rem;
  background: #1c2a38;
  color: #fff8f0;
  padding: 0.45rem 0.8rem;
  border-radius: 16px 16px 16px 4px;
  font-weight: 700;
  font-size: 0.92rem;
}

.section-label {
  font-weight: 800;
  color: #1c2a38;
  margin-bottom: 0.2rem;
}

div[data-testid="stTextArea"] textarea {
  border: 2px solid #1c2a38 !important;
  border-radius: 16px !important;
  background: #fffdf9 !important;
}

div[data-testid="stExpander"] {
  border: 2px solid #1c2a38 !important;
  border-radius: 16px !important;
  background: #fff8f0;
}

.stButton > button[kind="primary"] {
  background: #e07a3d !important;
  color: #fff8f0 !important;
  border: 3px solid #1c2a38 !important;
  border-radius: 999px !important;
  font-weight: 800 !important;
  box-shadow: 4px 4px 0 #1c2a38 !important;
  padding: 0.55rem 1.4rem !important;
}

.stButton > button[kind="primary"]:hover {
  background: #c9652c !important;
  transform: translate(1px, 1px);
  box-shadow: 3px 3px 0 #1c2a38 !important;
}

[data-testid="stAlert"] {
  border-radius: 16px;
}
"""

GRADE_LEVELS = [
    "Grade 6",
    "Grade 7",
    "Grade 8",
    "Grade 9",
    "Grade 10",
    "Grade 11",
    "Grade 12",
    "College first-year",
    "College upper-division",
    "Graduate",
]

CLASS_LEVELS = [
    "On-level / regular",
    "Honors",
    "AP English Language",
    "AP English Literature",
    "IB English",
    "College composition",
    "Disciplinary seminar",
]

# What strong analytical writing does, synthesized from CER practice, CCSS/analytic
# writing rubrics, AP Lang/Lit evidence-and-commentary scoring, STAAR analytical
# writing, and research on the shift from assertion-based to evidence-based analysis.
CORE_ANALYTICAL_CRITERIA = """
What counts as strong analytical writing (apply these; do not treat them as a fill-in template):

1. A defensible, non-obvious point. The paragraph takes a position about the source that a careful reader could dispute. Summary, topic restatement, or "the author talks about X" is not analysis.
2. Well-chosen evidence. Support is specific, accurate, and actually relevant to the point being made — a telling detail, quotation, data point, or structural feature — not a vague paraphrase or a quote dump.
3. Commentary that does interpretive work. After the evidence, the writer explains how it produces the point. The weakest analysis repeats the quote in other words. Stronger analysis shows the inference: what in the detail licenses the claim.
4. A line of reasoning. Sentences pull in one direction. New evidence develops the same idea instead of starting a new, unconnected observation.
5. Faithful reading. The source is not twisted, cherry-picked without acknowledgment, or stripped of context that would change the meaning.
6. Stakes, where the level calls for them. The paragraph answers "so what?" in a way that fits the assignment: why this observation matters for meaning, purpose, argument, or implication.
7. Complexity at higher levels. Stronger work notices tension, limitation, alternative reading, or a qualified claim. Do not invent this demand for younger or on-level writers.

Do not force Toulmin labels, CER sentence slots, or a five-paragraph skeleton. Follow the student's shape. Still notice missing warrants: places where the jump from evidence to point is assumed rather than shown.
""".strip()

GRADE_CALIBRATION = {
    "Grade 6": """Calibrate to mid-middle-school.
Reward a clear claim and relevant support. Reasoning may be brief or partly restatement; treat an honest "this shows…" attempt as on-track, then push for one clearer because.
Do not require nuance, counterargument, literary terminology, or sophisticated syntax.
A strong piece at this level: arguable claim, specific evidence, a visible attempt to say why the evidence matters.
Flag plot summary and unsupported opinion, but keep the tone coaching.""",
    "Grade 7": """Calibrate to late middle school.
Expect a focused claim and evidence that is more specific than a general retell. Commentary should begin to explain the link, not only restate the detail.
Do not require AP-style sophistication or disciplinary theory.
A strong piece: claim + chosen evidence + a reason that is not just "this proves my claim."
Name missing warrants in plain language and offer one model sentence.""",
    "Grade 8": """Calibrate to the end of middle school / early high school.
Expect an arguable claim, relevant textual or factual support, and reasoning that tries to connect them. Credit organization that a reader can follow.
Do not penalize missing counterclaims, implications, or stylistic flair.
A strong piece goes beyond literal retell and shows why a detail supports the idea.
Still teach the warrant: if they quote and then restate the quote, that is the main gap.""",
    "Grade 9": """Calibrate to 9th-grade analytical writing.
The claim should be arguable, not a topic sentence of summary. Evidence should be specific. Commentary should explain the connection; formula is acceptable if the link is real.
Accuracy of reading matters. Quote-and-run is below standard.
Do not require exploring tensions, limitations, or rhetorical situation unless the class type demands it.
A 7/10 here is a solid high-school start, not college-ready prose.""",
    "Grade 10": """Calibrate to 10th-grade analytical writing.
Expect a through-line, not isolated claim-evidence pairs that do not add up. Commentary should do more than paraphrase.
Well-chosen evidence beats more evidence. Misreading and dropped context are real problems at this level.
Do not require consistent sophistication (nuance, implications, counterargument) for a high score unless class type is AP/IB/honors.
A strong piece: defensible idea, apt support, explained inference.""",
    "Grade 11": """Calibrate to 11th-grade analytical writing.
Expect a defensible thesis-like point and commentary that consistently explains how evidence supports a line of reasoning (the core of AP-style evidence/commentary, even if this is not an AP class).
Reward going beyond a literal reading. Formulaic "this shows that" is adequate only if the explanation is actually doing work.
Complexity (tension, limitation, implication) is a plus, not a requirement for on-level.
Score relative to a capable 11th grader, not a published critic.""",
    "Grade 12": """Calibrate to 12th-grade analytical writing.
Expect control of a line of reasoning, precise evidence, and commentary that interprets rather than summarizes. The paragraph should sound like a thought, not a worksheet.
Mild qualification or awareness of another reading is welcome; do not demand a full counterargument essay in one paragraph.
A high score means college-ready analysis for this class type, not graduate-seminar originality.""",
    "College first-year": """Calibrate to first-year college composition / intro literature or rhetoric.
The paragraph should enter a conversation with the source: a motive (what is not obvious), a claim, and analysis of evidence rather than a book report or five-paragraph leftover.
Warrants and assumptions should be visible. "The author uses diction" without saying what the diction does is weak.
Reward stakes and precise source use. Do not require original contribution to a scholarly field.
A 7/10 is a competent college paragraph; 9–10 is unusually sharp for first year.""",
    "College upper-division": """Calibrate to upper-division undergraduate work in a reading-heavy course.
Expect a non-obvious claim, evidence handled with disciplinary care, and commentary that could survive a skeptical classmate.
Engage complexity: qualification, counterevidence, alternative explanation, or implication. Surface-level theme statements are below standard.
Warrants should be explicit enough that the inference is inspectable.
Score as a professor would on a short close-reading or argument paragraph, not as a high-school coach.""",
    "Graduate": """Calibrate to graduate-level analytical prose.
Expect precision, a real interpretive or argumentative stake, and methodological self-awareness (what kind of claim this is, what would count against it).
Missing warrants, overclaiming, and loose paraphrase of the source are serious.
Do not praise school-essay moves (generic "the author wants the reader to feel"). Demand that the analysis earn its conclusion.
A middle score means "fine but not yet a seminar contribution." """,
}

CLASS_CALIBRATION = {
    "On-level / regular": """Class type: on-level / regular.
Prioritize coaching the next developmental step. Do not dock for missing honors/AP extras (sophistication point, counterargument, dense terminology).
Feedback should be concrete and teachable. A high score means strong for this class, not for AP.""",
    "Honors": """Class type: honors.
Expect tighter commentary, more precise evidence, and less filler. The claim should be sharper than on-level.
Reward control and ambition, but still grade the paragraph they wrote, not the essay they might write.
Missing warrants and paraphrase-as-analysis are fair deductions.""",
    "AP English Language": """Class type: AP English Language.
Lean on AP Lang priorities without turning the paragraph into a 6-point exam score unless it is clearly an FRQ response:
- Defensible thesis/point that actually analyzes (rhetorical choices, argument, or source-based claim — whichever the paragraph is doing).
- Specific evidence plus commentary that explains how the evidence supports a line of reasoning.
- Understanding of rhetorical situation when the task is rhetorical analysis: purpose, audience, choices that do work.
- Sophistication (nuance, tension, implications, limitations) is distinguished work, not the floor for a good score.
Do not award "sophistication" for a canned "in society today" opener or a single complex sentence.""",
    "AP English Literature": """Class type: AP English Literature.
The paragraph should interpret how literary features (diction, imagery, structure, character, figurative language, etc.) produce meaning — not retell plot.
Evidence should be specific; commentary should explain the effect or significance of the details.
A theme statement with no attention to craft is weak. Sophistication means complexity of interpretation, not extra adjectives.""",
    "IB English": """Class type: IB English.
Expect close reference to the text, analysis of authorial choices, and some evaluative or interpretive depth (what the choices do, with what implications).
Reward precision and insight; do not require a full Paper 1/2 structure in one paragraph.
Unjustified leaps and paraphrase without analysis are the main problems.""",
    "College composition": """Class type: college composition (FYW / academic argument).
Treat this as academic analytical prose: motive, claim, source integration, and reasoning a skeptical peer could follow.
They-say/I-say moves are good when they are real engagement, not templates.
Quote sandwiches that never interpret are weak. Assumptions should be named when the argument depends on them.""",
    "Disciplinary seminar": """Class type: disciplinary seminar (history, philosophy, political theory, science-in-context, etc.).
Grade with field-appropriate analysis: what counts as a warrant here may be textual, historical, conceptual, or empirical.
Do not impose literary-device hunting unless the source and claim call for it.
Expect the student to show why this evidence answers this question, including limits of the source.""",
}


def default_grade_index() -> int:
    return GRADE_LEVELS.index("Grade 11")


def default_class_index() -> int:
    return CLASS_LEVELS.index("On-level / regular")


def build_system_prompt(grade: str, class_level: str, extra: str) -> str:
    parts = [
        "You are a rigorous writing tutor grading one analytical paragraph against a source text.",
        "Match your strictness, vocabulary, and next-step advice to the stated grade and class. A 8/10 at Grade 7 is not an 8/10 in a college seminar.",
        "Focus on reasoning quality more than polish (grammar only if it blocks meaning).",
        CORE_ANALYTICAL_CRITERIA,
        "Grade-level calibration:\n" + GRADE_CALIBRATION[grade],
        "Class-level calibration:\n" + CLASS_CALIBRATION[class_level],
        """Feedback format:
1. State the grade and class you graded against.
2. Score overall analytical reasoning 1–10 for that level, with a one- or two-sentence justification.
3. Briefly say what the paragraph is trying to show, in the student's terms.
4. Comment on claim quality, evidence choice, commentary/inference, reading accuracy, and (only if it matters at this level) complexity or stakes.
5. Flag missing or weak warrants/assumptions where they actually hurt the argument. Explain why the source does not license the jump and what would need to be shown. Skip this if the inference is already licensed.
6. End with 2–4 concrete revision moves pitched to this student (not a full rewrite unless a short example sentence helps).

Be specific. Quote brief phrases from the source and the paragraph. Do not invent source details. Do not condescend; do not inflate.""",
    ]
    extra = extra.strip()
    if extra:
        parts.append("Additional instructions from the user:\n" + extra)
    return "\n\n".join(parts)


def get_api_key() -> str:
    sidebar_key = st.session_state.get("api_key_input", "").strip()
    if sidebar_key:
        return sidebar_key
    try:
        secret = st.secrets.get("ANTHROPIC_API_KEY", "")
        if secret:
            return str(secret).strip()
    except Exception:
        pass
    return os.getenv("ANTHROPIC_API_KEY", "").strip()


def build_user_message(grade: str, class_level: str, source_text: str, paragraph: str) -> str:
    return (
        f"Grade this as {grade}, class: {class_level}.\n\n"
        "## Source text\n\n"
        f"{source_text.strip()}\n\n"
        "## Analytical paragraph\n\n"
        f"{paragraph.strip()}"
    )


def grade_paragraph(
    api_key: str,
    system_prompt: str,
    grade: str,
    class_level: str,
    source_text: str,
    paragraph: str,
) -> str:
    client = Anthropic(api_key=api_key)
    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=system_prompt.strip(),
        messages=[
            {
                "role": "user",
                "content": build_user_message(grade, class_level, source_text, paragraph),
            }
        ],
    )
    parts = []
    for block in response.content:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    return "\n\n".join(parts).strip() or "(No text returned.)"


st.set_page_config(
    page_title="Pip's reasoning desk",
    page_icon=str(PENGUIN_PATH) if PENGUIN_PATH.exists() else "🐧",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)

with st.sidebar:
    if PENGUIN_PATH.exists():
        st.image(str(PENGUIN_PATH), width=140)
    st.markdown("### Pip's classroom")
    grade = st.selectbox("Grade level", GRADE_LEVELS, index=default_grade_index())
    class_level = st.selectbox("Class level", CLASS_LEVELS, index=default_class_index())
    st.caption("Pip scores the paragraph for this student, not against a college seminar unless you pick one.")
    st.divider()
    st.markdown("### API key")
    st.text_input(
        "Anthropic key",
        type="password",
        key="api_key_input",
        help="Uses this value if set; otherwise ANTHROPIC_API_KEY from .env or Streamlit secrets.",
        placeholder="sk-ant-...",
        label_visibility="collapsed",
    )
    if get_api_key():
        st.success("Key found — Pip is ready.")
    else:
        st.warning("Add an Anthropic key so Pip can grade.")
    st.caption("Paste here, or put ANTHROPIC_API_KEY in a .env file.")

hero_left, hero_right = st.columns([1, 3], vertical_alignment="center")
with hero_left:
    if PENGUIN_PATH.exists():
        st.image(str(PENGUIN_PATH), width=220)
with hero_right:
    st.markdown(
        """
<div class="hero-card">
  <div class="hero-copy">
    <h1>Pip's reasoning desk</h1>
    <p>A slightly stern penguin who cares more about your thinking than your adjectives. Paste a source and a paragraph; Pip grades the analysis for the level you picked.</p>
    <span class="speech">Warrants first. Waddle later.</span>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

extra = st.text_area(
    "Anything else Pip should know?",
    height=90,
    placeholder="e.g. This is a rhetorical analysis of diction. Ignore spelling.",
    help="Appended to the built-in grading procedure.",
)

with st.expander("How Pip grades this level"):
    st.markdown(f"**{grade}** · **{class_level}**")
    st.markdown("**Core criteria**")
    st.text(CORE_ANALYTICAL_CRITERIA)
    st.markdown("**Grade calibration**")
    st.text(GRADE_CALIBRATION[grade])
    st.markdown("**Class calibration**")
    st.text(CLASS_CALIBRATION[class_level])

col_source, col_para = st.columns(2, gap="large")
with col_source:
    st.markdown('<p class="section-label">Source text</p>', unsafe_allow_html=True)
    source_text = st.text_area(
        "Source text",
        height=300,
        placeholder="Paste the passage, excerpt, or data here.",
        label_visibility="collapsed",
    )
with col_para:
    st.markdown('<p class="section-label">Your analytical paragraph</p>', unsafe_allow_html=True)
    paragraph = st.text_area(
        "Analytical paragraph",
        height=300,
        placeholder="Paste the paragraph you want Pip to grade.",
        label_visibility="collapsed",
    )

clicked = st.button("Ask Pip to grade", type="primary", use_container_width=True)

if clicked:
    api_key = get_api_key()
    missing = []
    if not api_key:
        missing.append("an Anthropic API key")
    if not source_text.strip():
        missing.append("source text")
    if not paragraph.strip():
        missing.append("an analytical paragraph")
    if missing:
        st.error("Pip needs " + ", ".join(missing) + ".")
    else:
        system_prompt = build_system_prompt(grade, class_level, extra)
        with st.spinner("Pip is circling your warrants..."):
            try:
                result = grade_paragraph(
                    api_key, system_prompt, grade, class_level, source_text, paragraph
                )
                st.markdown("### Pip's notes")
                with st.container(border=True):
                    st.markdown(result)
            except Exception as exc:
                st.error(f"Pip could not reach Claude: {exc}")

