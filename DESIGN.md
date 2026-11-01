# DESIGN — qwen-web-arwaky

## Design Overview

qwen-web-arwaky's TUI and CLI share a single design-token contract: a dark, high-density terminal surface that reads as a calm operational dashboard. The visual style couples Inter for conversational narratives and UI labels with JetBrains Mono for data readouts (token counts, model names, latencies, state flags), so human-facing prose and machine-facing telemetry stay visually distinct in the same pane.

## Design Requirements

### DS-QWEN-WEB-ARWAKY-001: Color Palette

| Variant | Use case | Token | Value |
| --- | --- | --- | --- |
| Base surface | Screen / canvas background | `bg` | `#171A1F` |
| Card surface | Cards, table rows, recessed strips | `surface` | `#22262C` |
| Hairline separator | Card borders, row dividers | `border` | `#2E343C` |
| Primary text | Headlines, body copy | `text` | `#E5E7EB` |
| Secondary text | Captions, placeholders | `text-muted` | `#9AA4B2` |
| Primary accent | Active selection, focus ring, active marker | `accent` | `#38BDF8` |
| Success state | ACTIVE / READY / DONE indicators | `success` | `#4ADE80` |
| Warning state | LIMITED / WARN / EXPIRED indicators | `warning` | `#FACC15` |
| Danger state | DELETE, error, FAILED indicators | `danger` | `#E5484D` |

### DS-QWEN-WEB-ARWAKY-002: Typography

| Variant | Use case | Token | Value |
| --- | --- | --- | --- |
| Headline | Pane title, primary section | `headline-lg` | Inter 32 / 40 / 600 |
| Headline (mobile) | Pane title on mobile frame | `headline-lg-mobile` | Inter 24 / 32 / 600 |
| Headline (mid) | Sub-headline | `headline-md` | Inter 20 / 28 / 600 |
| Headline (sm) | Small pane title | `headline-sm` | Inter 16 / 24 / 600 |
| Body (lg) | Conversational narrative | `body-lg` | Inter 15 / 22 / 400 |
| Body (md) | Card body copy | `body-md` | Inter 13 / 18 / 400 |
| Body (sm) | Compact card / chip copy | `body-sm` | Inter 12 / 16 / 400 |
| Label (lg) | Token-count / model-name readout | `label-lg` | JetBrains Mono 13 / 18 / 500 |
| Label (md) | Latency / status flag readout | `label-md` | JetBrains Mono 11 / 14 / 500 |
| Label (sm) | Compact chip / beacon text | `label-sm` | JetBrains Mono 10 / 12 / 400 |

### DS-QWEN-WEB-ARWAKY-003: Layout & Spacing

| Variant | Use case | Token | Value |
| --- | --- | --- | --- |
| Canvas margin | Uniform outer horizontal margin (mobile frame) | `margin` | `1rem` |
| Column gutter | Dual-column split telemetry blocks | `gutter` | `0.75rem` |
| Micro spacing | Badge clusters, inline terminal chips | `space-xs` | `0.25rem` |
| Component interior | Default card / component padding | `space-md` | `0.75rem` |
| Block rhythm | Between cards and major sections | `space-lg` | `1rem` |
| Section spacing | Between major layout zones | `space-xl` | `1.5rem` |

### DS-QWEN-WEB-ARWAKY-004: Elevation & Depth

| Variant | Use case | Token | Value |
| --- | --- | --- | --- |
| Layer 0 (canvas) | Base background | `bg` | `#171A1F` |
| Layer 1 (card / container) | Card / container surface with 1px hairline | `surface` + `border` | `#22262C` |
| Layer 2 (floating modal / bottom sheet) | Recessed strip with 1px focus-ring-tinted border | `bg-overlay` + `focus-ring` | `#1C2026` |
| Active agent focus | Subtle pulsating rim on active inference element | `focus-ring` | `#38BDF8` at reduced opacity |

### DS-QWEN-WEB-ARWAKY-005: Shapes

| Variant | Use case | Token | Value |
| --- | --- | --- | --- |
| Standard controls / text fields | Soft 4px radius | `rounded` | `0.25rem` |
| Structural containers / sheets | Soft 8px radius | `rounded-lg` | `0.5rem` |
| Status pills / operational pips | Crisp circular beacons | `rounded-full` | `9999px` |

## Reference

| Artifact | Purpose | Link |
| --- | --- | --- |
| PRD | Business goals, user stories, and scope | [PRD.md](PRD.md) |
| Backlog | Task tracking, epics, and implementation status | [BACKLOG.md](BACKLOG.md) |
| Roadmap | Timeline, phasing, and dependencies | [ROADMAP.md](ROADMAP.md) |
| Architecture | System boundaries, tech stack, and infra | [ARCHITECTURE.md](ARCHITECTURE.md) |
