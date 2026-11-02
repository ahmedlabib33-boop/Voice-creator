"""Design system for the Egyptian Voice Sender UI.

Tokens live in ``TOKENS`` and are emitted as CSS custom properties; every
styled element in the app references those variables, never a raw value.
See DESIGN_SYSTEM.md for the documented components and states.
"""

from __future__ import annotations

import html

import streamlit as st

TOKENS = {
    # color: surfaces
    "bg": "#070B14",
    "surface": "rgba(15, 23, 42, 0.72)",
    "surface-2": "rgba(30, 41, 59, 0.55)",
    "border": "rgba(148, 163, 184, 0.16)",
    "border-strong": "rgba(34, 211, 238, 0.45)",
    # color: text
    "text": "#E6EDF7",
    "text-muted": "#94A3B8",
    "text-dim": "#64748B",
    # color: brand + semantic
    "accent": "#22D3EE",
    "accent-2": "#8B5CF6",
    "accent-3": "#F472B6",
    "success": "#34D399",
    "warning": "#FBBF24",
    "danger": "#FB7185",
    # typography
    "font-ui": "'Sora', 'Segoe UI', system-ui, sans-serif",
    "font-arabic": "'Tajawal', 'Noto Naskh Arabic', 'Segoe UI', sans-serif",
    "font-mono": "'JetBrains Mono', 'Cascadia Code', Consolas, monospace",
    # radius / shadow / motion
    "radius-sm": "10px",
    "radius-md": "16px",
    "radius-lg": "24px",
    "shadow-1": "0 1px 0 rgba(255,255,255,0.03) inset, 0 10px 30px rgba(2, 6, 23, 0.45)",
    "shadow-glow": "0 0 0 1px rgba(34,211,238,0.35), 0 12px 40px rgba(34,211,238,0.18)",
    "ease": "cubic-bezier(.2,.8,.2,1)",
    "dur-fast": "140ms",
    "dur-base": "260ms",
}


def _css_vars() -> str:
    return "\n".join(f"  --{name}: {value};" for name, value in TOKENS.items())


CSS = """
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@400;500;600;700;800&family=Tajawal:wght@400;500;700&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
__VARS__
}

/* ---------- canvas ---------- */
[data-testid="stAppViewContainer"] {
  background:
    radial-gradient(1200px 600px at 10% -10%, rgba(139,92,246,0.18), transparent 60%),
    radial-gradient(900px 500px at 100% 0%, rgba(34,211,238,0.14), transparent 55%),
    var(--bg);
  color: var(--text);
  font-family: var(--font-ui);
}
[data-testid="stHeader"] { background: transparent; }
.block-container { padding-top: 1.6rem; padding-bottom: 4rem; max-width: 1240px; }

h1, h2, h3, h4, [data-testid="stMarkdownContainer"] h1, [data-testid="stMarkdownContainer"] h2, [data-testid="stMarkdownContainer"] h3,
[data-testid="stSidebar"] h3 { font-family: var(--font-ui) !important; letter-spacing: -0.01em; }
p, li, label, .stMarkdown, [data-testid="stMarkdownContainer"] p, [data-testid="stWidgetLabel"] p, .stCaption, [data-testid="stCaptionContainer"] { font-family: var(--font-ui) !important; }
.stAppDeployButton { display: none; }
code, pre, .stCode { font-family: var(--font-mono) !important; }

/* ---------- sidebar ---------- */
[data-testid="stSidebar"] {
  background: linear-gradient(180deg, rgba(15,23,42,0.96), rgba(7,11,20,0.98));
  border-right: 1px solid var(--border);
}
[data-testid="stSidebar"] .block-container { padding-top: 1.2rem; }

/* ---------- hero ---------- */
.evs-hero {
  position: relative; overflow: hidden;
  padding: 28px 32px; margin-bottom: 18px;
  border: 1px solid var(--border); border-radius: var(--radius-lg);
  background: linear-gradient(135deg, rgba(15,23,42,0.85), rgba(30,41,59,0.55));
  box-shadow: var(--shadow-1);
  backdrop-filter: blur(14px);
}
.evs-hero::before {
  content: ""; position: absolute; inset: -40% -20% auto auto; width: 520px; height: 520px;
  background: conic-gradient(from 180deg, rgba(34,211,238,0.35), rgba(139,92,246,0.35), rgba(244,114,182,0.25), rgba(34,211,238,0.35));
  filter: blur(80px); opacity: .55; animation: evs-spin 18s linear infinite;
}
.evs-hero > * { position: relative; }
.evs-eyebrow {
  display: inline-flex; gap: 8px; align-items: center;
  font-size: 12px; font-weight: 600; letter-spacing: .14em; text-transform: uppercase;
  color: var(--accent); margin-bottom: 10px;
}
.evs-eyebrow i { width: 8px; height: 8px; border-radius: 50%; background: var(--accent); box-shadow: 0 0 12px var(--accent); animation: evs-pulse 2.2s ease-in-out infinite; }
.evs-title {
  font-family: var(--font-ui) !important;
  font-size: clamp(30px, 4vw, 44px) !important; font-weight: 800 !important; line-height: 1.05 !important; margin: 0 0 8px !important; padding: 0 !important;
  background: linear-gradient(90deg, #FFFFFF 0%, #C7F9FF 45%, #C4B5FD 100%);
  -webkit-background-clip: text; background-clip: text; color: transparent;
}
.evs-sub { color: var(--text-muted) !important; font-size: 15px !important; margin: 0 !important; max-width: 720px; font-family: var(--font-ui) !important; }

/* ---------- chips ---------- */
.evs-chip {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 6px 12px; margin: 4px 6px 4px 0;
  border-radius: 999px; border: 1px solid var(--border);
  background: var(--surface-2); font-size: 12.5px; font-weight: 500; color: var(--text);
  font-family: var(--font-ui);
}
.evs-chip i { width: 8px; height: 8px; border-radius: 50%; flex: none; }
.evs-chip.ok i { background: var(--success); box-shadow: 0 0 10px var(--success); }
.evs-chip.warn i { background: var(--warning); box-shadow: 0 0 10px var(--warning); }
.evs-chip.off i { background: var(--danger); box-shadow: 0 0 10px var(--danger); }
.evs-chip code { font-size: 11.5px; background: transparent; color: var(--text-muted); padding: 0; }

/* ---------- step header ---------- */
.evs-step { display: flex; align-items: center; gap: 14px; margin: 26px 0 10px; }
.evs-step b {
  display: grid; place-items: center; width: 36px; height: 36px; border-radius: 12px;
  background: linear-gradient(135deg, var(--accent), var(--accent-2));
  color: #04131A; font-weight: 800; font-size: 15px; box-shadow: var(--shadow-glow);
}
.evs-step h3 { margin: 0 !important; padding: 0 !important; font-size: 20px !important; font-weight: 700 !important; font-family: var(--font-ui) !important; }
.evs-step span { color: var(--text-muted); font-size: 13.5px; font-family: var(--font-ui); }

/* ---------- cards ---------- */
.evs-card {
  padding: 18px 20px; border-radius: var(--radius-md);
  border: 1px solid var(--border); background: var(--surface);
  box-shadow: var(--shadow-1); backdrop-filter: blur(12px);
  transition: border-color var(--dur-base) var(--ease), transform var(--dur-base) var(--ease);
}
.evs-card:hover { border-color: var(--border-strong); }
.evs-kpi { display: flex; flex-direction: column; gap: 4px; }
.evs-kpi small { color: var(--text-dim); font-size: 11.5px; letter-spacing: .1em; text-transform: uppercase; font-family: var(--font-ui); }
.evs-kpi strong { font-size: 22px; font-weight: 700; font-family: var(--font-ui); }

/* ---------- streamlit widgets ---------- */
.stButton > button, .stDownloadButton > button, .stLinkButton > a, .stFormSubmitButton > button {
  border-radius: var(--radius-sm) !important; font-family: var(--font-ui) !important; font-weight: 600 !important;
  border: 1px solid var(--border) !important; background: var(--surface-2) !important; color: var(--text) !important;
  transition: transform var(--dur-fast) var(--ease), box-shadow var(--dur-base) var(--ease), border-color var(--dur-base) var(--ease) !important;
}
.stButton > button:hover, .stDownloadButton > button:hover, .stLinkButton > a:hover, .stFormSubmitButton > button:hover {
  transform: translateY(-1px); border-color: var(--border-strong) !important;
}
.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {
  background: linear-gradient(135deg, var(--accent), var(--accent-2)) !important;
  color: #04131A !important; border: none !important; box-shadow: var(--shadow-glow) !important;
}
.stButton > button[kind="primary"]:hover { filter: brightness(1.07); }
.stButton > button:disabled { opacity: .45; transform: none; box-shadow: none !important; }

[data-testid="stTextArea"] textarea, [data-testid="stTextInput"] input {
  border-radius: var(--radius-sm) !important; background: rgba(2,6,23,0.55) !important;
  border: 1px solid var(--border) !important; color: var(--text) !important;
  transition: border-color var(--dur-base) var(--ease), box-shadow var(--dur-base) var(--ease);
}
[data-testid="stTextArea"] textarea:focus, [data-testid="stTextInput"] input:focus {
  border-color: var(--border-strong) !important; box-shadow: 0 0 0 3px rgba(34,211,238,0.18) !important;
}
.st-key-arabic_scope textarea, .st-key-refined_scope textarea { direction: rtl; text-align: right; font-family: var(--font-arabic); font-size: 17px; line-height: 1.7; }

[data-baseweb="select"] > div, [data-testid="stSelectbox"] > div > div {
  border-radius: var(--radius-sm) !important; background: rgba(2,6,23,0.55) !important; border-color: var(--border) !important;
}
.stTabs [data-baseweb="tab-list"] { gap: 6px; border-bottom: 1px solid var(--border); }
.stTabs [data-baseweb="tab"] { border-radius: 10px 10px 0 0; padding: 10px 16px; font-family: var(--font-ui); font-weight: 600; }
.stTabs [aria-selected="true"] { background: var(--surface-2); color: var(--accent) !important; }
[data-testid="stExpander"] { border: 1px solid var(--border); border-radius: var(--radius-md); background: var(--surface); }
[data-testid="stExpander"] summary { font-family: var(--font-ui); font-weight: 600; }
[data-testid="stAlert"] { border-radius: var(--radius-md); border: 1px solid var(--border); }
[data-testid="stDataFrame"] { border-radius: var(--radius-md); overflow: hidden; border: 1px solid var(--border); }
audio { width: 100%; filter: invert(1) hue-rotate(180deg) saturate(.6); border-radius: 999px; }
hr { border-color: var(--border) !important; }

/* ---------- motion ---------- */
@keyframes evs-spin { to { transform: rotate(360deg); } }
@keyframes evs-pulse { 0%,100% { opacity: 1; transform: scale(1);} 50% { opacity: .55; transform: scale(.8);} }
@keyframes evs-rise { from { opacity: 0; transform: translateY(8px);} to { opacity: 1; transform: none;} }
.evs-rise { animation: evs-rise var(--dur-base) var(--ease) both; }
@media (prefers-reduced-motion: reduce) {
  .evs-hero::before, .evs-eyebrow i, .evs-rise { animation: none !important; }
  * { transition: none !important; }
}
@media (max-width: 760px) {
  .evs-hero { padding: 20px; }
  .block-container { padding-left: 16px; padding-right: 16px; }
}
"""


def inject_theme() -> None:
    """Emit the design tokens and component styles once per page render."""
    st.markdown(f"<style>{CSS.replace('__VARS__', _css_vars())}</style>", unsafe_allow_html=True)


def hero(title: str, subtitle: str, eyebrow: str = "Live") -> None:
    st.markdown(
        f'<section class="evs-hero evs-rise"><div class="evs-eyebrow"><i></i>{html.escape(eyebrow)}</div>'
        f'<h1 class="evs-title">{html.escape(title)}</h1><p class="evs-sub">{html.escape(subtitle)}</p></section>',
        unsafe_allow_html=True,
    )


def chip(label: str, state: str = "ok", detail: str = "") -> str:
    """Return chip HTML. ``state`` is ok | warn | off."""
    extra = f" <code>{html.escape(detail)}</code>" if detail else ""
    return f'<span class="evs-chip {state}"><i></i>{html.escape(label)}{extra}</span>'


def chips(items: list[tuple[str, str, str]]) -> None:
    st.markdown("".join(chip(label, state, detail) for label, state, detail in items), unsafe_allow_html=True)


def step(number: int, title: str, hint: str = "") -> None:
    st.markdown(
        f'<div class="evs-step evs-rise"><b>{number}</b><div><h3>{html.escape(title)}</h3>'
        f'<span>{html.escape(hint)}</span></div></div>',
        unsafe_allow_html=True,
    )


def kpi(label: str, value: str) -> str:
    return f'<div class="evs-card evs-kpi"><small>{html.escape(label)}</small><strong>{html.escape(value)}</strong></div>'


def kpis(items: list[tuple[str, str]]) -> None:
    cols = st.columns(len(items))
    for col, (label, value) in zip(cols, items):
        with col:
            st.markdown(kpi(label, value), unsafe_allow_html=True)
