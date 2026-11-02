# Egyptian Voice Sender — Design System

Source of truth: `src/ui_theme.py` (tokens + component helpers) and
`.streamlit/config.toml` (base theme). Every styled element references a token;
no raw colour, size or easing appears in `app.py`.

## Principles

1. **One screen, three steps.** Write → Voice → Send. Each step has a numbered
   header; the primary action of each step is the only gradient button in view.
2. **Status at a glance, secrets never.** Chips show presence of keys and provider
   readiness. Values are never rendered.
3. **Futuristic, not noisy.** Dark glass surfaces, one accent gradient, slow
   ambient motion. Motion is decorative only and disabled under
   `prefers-reduced-motion`.
4. **Arabic first.** The message fields are RTL with an Arabic typeface at a larger
   size and line height.

## Tokens

| Group | Token | Value | Use |
|-------|-------|-------|-----|
| Surface | `--bg` | `#070B14` | Page background |
| | `--surface` | `rgba(15,23,42,.72)` | Cards, expanders |
| | `--surface-2` | `rgba(30,41,59,.55)` | Chips, secondary buttons, active tab |
| | `--border` | `rgba(148,163,184,.16)` | Default borders |
| | `--border-strong` | `rgba(34,211,238,.45)` | Hover / focus borders |
| Text | `--text` | `#E6EDF7` | Body |
| | `--text-muted` | `#94A3B8` | Captions, hints |
| | `--text-dim` | `#64748B` | KPI labels |
| Brand | `--accent` | `#22D3EE` | Primary, focus ring, live dot |
| | `--accent-2` | `#8B5CF6` | Gradient end |
| | `--accent-3` | `#F472B6` | Hero glow only |
| Semantic | `--success` | `#34D399` | Ready |
| | `--warning` | `#FBBF24` | Needs attention |
| | `--danger` | `#FB7185` | Missing / failed |
| Type | `--font-ui` | Sora | Headings, labels, buttons |
| | `--font-arabic` | Tajawal | Message text areas |
| | `--font-mono` | JetBrains Mono | Paths, ids |
| Radius | `--radius-sm/md/lg` | 10 / 16 / 24 px | Controls / cards / hero |
| Shadow | `--shadow-1` | soft drop | Cards |
| | `--shadow-glow` | cyan ring + glow | Primary buttons, step badges |
| Motion | `--dur-fast/base` | 140 / 260 ms | Hover / enter |
| | `--ease` | `cubic-bezier(.2,.8,.2,1)` | All transitions |

Type scale: hero 30–44 px (fluid), step title 20 px, KPI value 22 px, body 15 px,
chip 12.5 px, eyebrow 12 px uppercase with 0.14 em tracking.

Spacing: 8 px grid. Card padding 18/20, hero padding 28/32, step header margin 26
top / 10 bottom, chip padding 6/12.

## Components

### Hero (`hero(title, subtitle, eyebrow)`)
Glass panel with a slow conic glow. Eyebrow carries a pulsing live dot. One per page.

### Chip (`chips([(label, state, detail)])`)
| State | Dot | Use |
|-------|-----|-----|
| `ok` | success | Key present, provider ready |
| `warn` | warning | Configured but not ready, or soft issue |
| `off` | danger | Missing |
Optional `detail` renders in mono at reduced contrast. Chips wrap; never truncate.

### Step header (`step(n, title, hint)`)
Gradient numbered badge + title + hint. Numbers restart per tab. Exactly one primary
button belongs to each step.

### KPI card (`kpis([(label, value)])`)
Equal-width glass cards, uppercase label, 22 px value. Max four per row.

### Buttons (Streamlit)
| Variant | Style | When |
|---------|-------|------|
| Primary | accent gradient, glow, dark text | The step's main action |
| Secondary | surface-2, border | Alternatives, utilities |
| Disabled | 45 % opacity, no lift | Preconditions unmet |
Hover lifts 1 px and strengthens the border. Primary hover brightens 7 %.

### Inputs
Dark inset field, 10 px radius. Focus: strong border + 3 px accent ring.
Arabic scopes (`st.container(key="arabic_scope")`) switch to RTL, Tajawal, 17 px.

### Tabs
Underlined list; active tab gets surface-2 background and accent text.

### Feedback
Toasts for successful saves/generation; inline `st.error` for failures next to the
control that caused them; `st.warning` for readiness gaps.

## Accessibility

* Contrast: body text on `--bg` ≥ 12:1; muted text ≥ 5:1; primary button text
  `#04131A` on the gradient ≥ 7:1.
* Focus ring on every input; buttons keep Streamlit's keyboard focus styles.
* State is never colour-only: chips pair the dot with text, alerts carry text.
* `prefers-reduced-motion` removes the glow spin, pulse and rise animations.
* Layout collapses to one column below 760 px with 16 px gutters.

## Do / Don't

| Do | Don't |
|----|-------|
| Add new colours as tokens in `TOKENS` | Hard-code hex values in `app.py` |
| Use `step()` for any new section | Use bare `st.subheader` in the Studio tab |
| Put secrets presence in a chip | Print any part of a key, even masked |
| Keep one primary button per step | Stack several gradient buttons together |
