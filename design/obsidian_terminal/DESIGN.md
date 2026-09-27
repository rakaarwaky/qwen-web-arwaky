---
name: Obsidian Terminal
colors:
  surface: '#0f131c'
  surface-dim: '#0f131c'
  surface-bright: '#353942'
  surface-container-lowest: '#0a0e16'
  surface-container-low: '#181c24'
  surface-container: '#1c2028'
  surface-container-high: '#262a33'
  surface-container-highest: '#31353e'
  on-surface: '#dfe2ee'
  on-surface-variant: '#bdc8d1'
  inverse-surface: '#dfe2ee'
  inverse-on-surface: '#2c3039'
  outline: '#87929a'
  outline-variant: '#3e484f'
  surface-tint: '#7bd0ff'
  primary: '#8ed5ff'
  on-primary: '#00354a'
  primary-container: '#38bdf8'
  on-primary-container: '#004965'
  inverse-primary: '#00668a'
  secondary: '#c0c1ff'
  on-secondary: '#1000a9'
  secondary-container: '#3131c0'
  on-secondary-container: '#b0b2ff'
  tertiary: '#56e5a9'
  on-tertiary: '#003824'
  tertiary-container: '#30c88f'
  on-tertiary-container: '#004e34'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#c4e7ff'
  primary-fixed-dim: '#7bd0ff'
  on-primary-fixed: '#001e2c'
  on-primary-fixed-variant: '#004c69'
  secondary-fixed: '#e1e0ff'
  secondary-fixed-dim: '#c0c1ff'
  on-secondary-fixed: '#07006c'
  on-secondary-fixed-variant: '#2f2ebe'
  tertiary-fixed: '#6ffbbe'
  tertiary-fixed-dim: '#4edea3'
  on-tertiary-fixed: '#002113'
  on-tertiary-fixed-variant: '#005236'
  background: '#0f131c'
  on-background: '#dfe2ee'
  surface-variant: '#31353e'
typography:
  headline-lg:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.02em
  headline-lg-mobile:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.015em
  headline-md:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.01em
  headline-sm:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 24px
    letterSpacing: 0em
  body-lg:
    fontFamily: Inter
    fontSize: 15px
    fontWeight: '400'
    lineHeight: 22px
    letterSpacing: 0em
  body-md:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
    letterSpacing: 0em
  body-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
    letterSpacing: 0.01em
  label-lg:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '500'
    lineHeight: 18px
    letterSpacing: 0.02em
  label-md:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '500'
    lineHeight: 14px
    letterSpacing: 0.03em
  label-sm:
    fontFamily: JetBrains Mono
    fontSize: 10px
    fontWeight: '400'
    lineHeight: 12px
    letterSpacing: 0.04em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  gutter: 0.75rem
  margin: 1rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 0.75rem
  space-lg: 1rem
  space-xl: 1.5rem
---

## Brand & Style

This design system translates the density, high precision, and technical immediacy of modern command-line terminal interfaces into an ergonomic, mobile-first touch architecture. Designed for engineers orchestrating parallel LLM agents, background workers, and automated pipelines on the move, it prioritizes real-time status readability, telemetry density, and tactile execution control.

The visual style blends **cyber-technical minimalism** with refined **tactile telemetry**. It abandons skeletal desktop terminal emulation in favor of deep obsidian layers, hairline luminous separators, calibrated neon indicators, and monospace data readouts. The atmosphere is quiet, surgical, and responsive—engineered for deep-focus monitoring in dark environments without visual fatigue.

## Colors

The palette operates in strict dark mode, anchored by deep carbon and obsidian planes:

- **Base Surfaces**: `#0B0F17` provides the structural canvas, layered with `#111827` for elevated cards, modals, and navigation shelves. Subtle elevated nodes transition to `#1E293B`.
- **Primary Accent (`#38BDF8`)**: Electric cyan-blue designated for high-priority interactive states, primary action triggers, stream cursors, and active process markers.
- **Secondary Accent (`#6366F1`)**: Soft indigo used for secondary branching, parallel agent tags, auxiliary control vectors, and telemetry charts.
- **Tertiary Accent (`#10B981`)**: Emerald green dedicated to running tasks, operational health, completed inference cycles, and online daemon states.
- **System Diagnostics**: Warning (`#F59E0B`) and Critical Error (`#EF4444`) are used purely for state divergence, log anomalies, and task interruptions.
- **Hairlines and Contours**: Ghost borders rely on `rgba(56, 189, 248, 0.12)` to `rgba(255, 255, 255, 0.08)` to maintain structural integrity without excessive contrast.

## Typography

The typography couples the fluid legibility of **Inter** for conversational narratives, system prompts, and UI controls with the structural rigor of **JetBrains Mono** for execution logs, token counts, model names, latency readings, and state flags.

All numbers, timestamps, system parameters, and model identifiers must be rendered in `label-*` tiers using `JetBrains Mono` with tabular figures enabled. Headers remain taut and slightly tracking-compressed to mirror modern developer tool consoles while maintaining clear readability on high-density mobile viewports.

## Layout & Spacing

The layout is built on a tight 4px baseline sub-grid that maximizes real estate for multi-agent streaming and status feeds without inducing visual clutter. 

- **Canvas Metrics**: Mobile frames enforce a uniform `1rem` outer horizontal margin (`margin`), tapering into `0.75rem` column gutters (`gutter`) for dual-column split telemetry blocks.
- **Rhythm & Density**: Micro-element spacing (`space-xs` and `space-sm`) handles badge clusters, inline terminal chips, and tabular telemetry metadata. Component interior padding defaults to `space-md` (`0.75rem`) to maintain mobile touch accessibility while maximizing information density.
- **Adaptive Breakpoints**:
  - `Mobile (<640px)`: Single-column stacked stream view; dock-anchored action bar; tabbed worker switcher.
  - `Tablet / Foldable (640px - 1024px)`: Two-column split layout with parallel terminal stream on the left (60%) and live metrics, thread inspectors, and system parameters on the right (40%).

## Elevation & Depth

This design system avoids heavy drop shadows, relying instead on **chromatic surface layering** coupled with **subtle edge luminosity**:

- **Layer 0 (Canvas)**: `#0B0F17` base background.
- **Layer 1 (Card/Container)**: `#111827` with a 1px border of `rgba(255, 255, 255, 0.06)`.
- **Layer 2 (Floating Modals / Bottom Sheets)**: `#151D2C` with a 1px border of `rgba(56, 189, 248, 0.22)` and a soft ambient glow: `box-shadow: 0 8px 32px -4px rgba(0, 0, 0, 0.75), 0 0 12px 0 rgba(56, 189, 248, 0.08)`.
- **Active Agent Focus**: Elements running active inference processes display a subtle pulsing rim illumination using `rgba(56, 189, 248, 0.4)` without hard edge dropouts.

## Shapes

The design system enforces a **Soft (`1`)** shape language to preserve the precision and discipline of terminal environments. Curvatures are kept compact:

- Standard controls, text fields, cards, and list rows use `0.25rem` (4px).
- Structural containers, persistent bottom sheets, and modal frames use `0.5rem` (8px).
- Status pills, operational pips, and cursor anchors remain crisp badges or circular beacons (`rounded-full`), balancing structural rectangular layouts with distinct data indicators.

## Components

### Buttons & Triggers
- **Primary Action (Run / Execute)**: Solid `#38BDF8` background, `#0B0F17` bold typography, `0.25rem` radius. Active state triggers a subtle scale down (`0.98`) with a cyan halo glow.
- **Secondary Action (Abort / Fork)**: `#111827` surface with a 1px `rgba(99, 102, 241, 0.35)` border and `#6366F1` text.
- **Ghost / TUI Command Buttons**: Monospaced labels wrapped in square brackets (`[kill -9]`, `[tail -f]`) rendered in muted slate with transparent backgrounds.

### Status Indicators & Chips
- **Worker / Agent Badges**: Compact pill structures containing a 6px status beacon. Running states use pulsating emerald green (`#10B981`) beacons with background fill `rgba(16, 185, 129, 0.12)`.
- **Token & Model Chips**: Micro-chips with `#1E293B` background, displaying model routing (`qwen-max`, `qwen-turbo`) and context consumption (`4.2k/8k tokens`) in `label-sm` font.

### Parallel Stream Cards
- Encapsulated cards featuring a monospaced terminal header bar: displays thread ID, live latency (`124ms`), and an execution state tag.
- Stream content area uses monospaced text with a blinking cyan cursor (`#38BDF8`) for streaming responses, styled with an inner hairline left border to denote output nesting.

### Input Fields & Command Bar
- Fixed bottom dock featuring a prompt-symbol indicator (`> `) in electric cyan.
- Dark field fill (`#111827`) bounded by a 1px border that shifts from neutral gray to glowing `#38BDF8` on focus.
- Monospace placeholder text with auto-suggest completions rendered in low-opacity slate (`#64748B`).

### Navigation & Tab Bar
- Bottom tab dock with high-blur frosted backing (`rgba(11, 15, 23, 0.85)`).
- Tabs feature high-contrast minimal glyphs paired with `label-sm` text. Active tab highlighted via an upper horizontal neon hairline accent in primary electric blue.