---
name: Mandarin
description: A quiet native desktop instrument organized around a citrus wheel.
colors:
  citrus-accent: "#c35416"
  citrus-soft: "#fae8da"
  wheel-light: "rgb(94%, 92.5%, 90%)"
  wheel-dark: "rgb(18%, 18%, 18%)"
  wheel-dark-hover: "rgb(34%, 23%, 16%)"
typography:
  title:
    fontSize: "26px"
    fontWeight: 700
  label:
    fontSize: "13px"
    fontWeight: 600
  job-name:
    fontWeight: 600
rounded:
  row: "8px"
  wheel-button: "12px"
  hub: "50%"
spacing:
  operation-gap: "4px"
  icon-label-gap: "5px"
  job-gap: "6px"
  small: "8px"
  form-gap: "10px"
  medium: "12px"
  inset: "16px"
  workspace: "20px"
  dialog-inset: "24px"
components:
  wheel-button:
    typography: "{typography.label}"
    rounded: "{rounded.wheel-button}"
    padding: "8px"
    width: "100px"
    height: "74px"
  wheel-hub:
    rounded: "{rounded.hub}"
    width: "110px"
    height: "110px"
  file-row:
    rounded: "{rounded.row}"
    padding: "8px"
  status:
    rounded: "{rounded.row}"
    padding: "8px 12px"
  status-compact:
    rounded: "{rounded.row}"
    padding: "6px 12px"
  job-row:
    padding: "12px"
---

# Design System: Mandarin

## Overview

**Creative North Star: "Quiet native desktop instrument"**

A quiet native desktop instrument organized around a citrus wheel: the radial menu is the distinctive element; file selection, editors and job feedback remain familiar GTK controls. The application belongs to the Ubuntu desktop, follows its font and color preferences, and keeps file names, destinations and recovery actions readable.

The existing code establishes the direction. The wheel uses warm orange interaction cues and neutral sectors; surrounding surfaces, suggested actions, fields and dialogs inherit GTK4/libadwaita. There is no approved visual comp or recorded FORM seed; this document captures the implemented system without asserting either.

**Key Characteristics:**

- Native desktop controls and user-selected typography.
- A stable circular hub with labeled, keyboard-accessible operation buttons.
- Quiet tonal separation, persistent status and reachable job actions.
- One operation model shared by the normal window, compact popup and list view.

## Colors

Warm citrus is reserved for identity and the wheel’s interaction cues. GTK owns the surrounding desktop palette.

### Primary

- **Citrus accent** (`colors.citrus-accent`): application title, drop-target outline and wheel-button hover/focus tint. The button tint uses the accent at 14% alpha.
- **Citrus soft** (`colors.citrus-soft`): hovered Cairo sector in light mode.

### Neutral

- **Warm wheel neutral** (`colors.wheel-light`): resting Cairo sectors in light mode.
- **Dark wheel neutral** (`colors.wheel-dark`): resting Cairo sectors in dark mode.
- **Warm dark hover** (`colors.wheel-dark-hover`): hovered Cairo sector in dark mode.
- **Native semantic colors:** window background/foreground, suggested actions, errors and native field states resolve from GTK/libadwaita. They are intentionally not frozen to the colors of one Ubuntu theme. Secondary text uses window foreground at 72% alpha; status fill uses 4.5%; file hover 5%; separators use 10–12%.

The first two frontmatter colors come from `mandarin/resources/style.css`; `mandarin/theme.py` parses the stylesheet for Cairo. The three remaining sector fills are literal RGB tuples in `Wheel.draw`. The stylesheet also declares ink, secondary, surface and line colors, but the current UI does not consume them; they are reserved definitions, not active visual roles. The sidecar’s synthesized tonal strips are panel display aids, not additional runtime palette steps; its HTML components are browser preview adapters for native widgets.

**The Native Theme Rule.** Use GTK/libadwaita semantic foreground, background, accent and error roles for native controls; custom wheel colors do not replace those roles.

## Typography

The font family, body size, line height and native title/heading classes come from GTK and the user’s desktop settings. Use the platform Sans face and its scaling behavior; there are no downloaded fonts or independent web type system. Technical diagnostics may use platform monospace, but filenames stay in the normal desktop face.

The application title uses `typography.title`; wheel labels use `typography.label`; job titles use `typography.job-name`. The parameter dialog uses native `title-2`, the file panel uses native `title-3`, and list category headings use native `heading`. Other labels, controls and progress text keep the native hierarchy. The implementation does not impose a separate 14px body-label size or tabular-numeric feature.

**The Native Type Rule.** Keep the desktop font and text scaling. Apply only the title, wheel-label and job-name overrides recorded in the frontmatter.

## Layout

All measurements are GTK logical pixels. The normal window requests 1000 × 760; the current valid capture is 1000 × 770. A requested GTK window size is not an immutable allocation. A left file panel has a 240px width request, with 20px workspace padding and a 20px gap to the expanding operation column. The file panel has 8px top padding, 16px right/bottom padding and a thin native-foreground divider. Lists and the operation view own scrolling; the shared jobs area remains below the workspace.

Compact mode is explicit application state, not a CSS viewport breakpoint. It requests 480 × 720, hides the left panel, exposes the selected-files/output review button, uses 12px workspace padding and reduces center-column gaps from 12px to 8px. Its shared job scroller has a fixed 110px content allowance; normal mode allows 110–180px. The compact capture is actually 480 × 720. Review selected paths and change the destination through the same compact context dialog.

The wheel requests a minimum square of 420px normally and 340px in compact mode. It expands with available space. Its outer radius is capped at 192px and otherwise follows `(max(minimum_size, min(width, height)) - 36) / 2`; the inner drawn radius stays 72px. Sector gaps are 0.07 radians, and button centers sit at `137 × radius / 192` from the hub. At most eight sectors are visible. The 110 × 110 hub is centered using its measured allocation, so native metrics do not move its label off-center. Wheel-button requests in frontmatter describe GTK size requests, not immutable rendered dimensions.

The shared parameter window requests 500 × 560. Its form scrolls independently, with 24px side margins, 16px top/bottom margins, 10px form gaps, 8px vertical row padding and 5px label/control gaps. Image previews request 200px height with contained content. Cancel and Create copy stay outside the form scroller; their row has 12px gaps, 24px side margins and 20px bottom margin. Reused spacing is recorded in the frontmatter; the old proposed 32px step is not implemented.

## Elevation & Depth

The custom wheel is flat: tonal sectors, real gaps and a thin hub border carry its structure. Wheel buttons explicitly remove box shadows and borders at rest. Status uses a low-opacity foreground wash, file rows gain a subtle hover wash, and job rows use a thin top separator. The application does not define a custom shadow vocabulary. Native windows, popovers, dialogs and focus indicators keep platform elevation and contrast.

**The Quiet Depth Rule.** The wheel is flat and shadowless. Preserve the platform’s own elevation, focus rings and dialogs around it.

## Shapes

Rounded rows and status use `rounded.row`, operation buttons use `rounded.wheel-button`, and the hub uses `rounded.hub`. The circular sectors are Cairo paths rather than rounded cards. The hub’s border is 1px at 10% native foreground alpha. Native button and field radii remain theme-controlled. Scrollbar sliders have a 6px minimum in each axis and use the row radius, with foreground alpha rising from 35% to 55% on hover. The drop target uses a 2px accent outline inset by 4px.

## Components

### Native buttons and fields

GTK buttons, drop-downs, spin buttons, entries, check buttons, file dialogs and Adw windows own visual states, focus and accessibility. Create copy uses the native suggested-action style. Fields are associated with visible labels; validation remains inline. Native action heights vary with theme and desktop settings: the custom file row, wheel button and list operation button specify a 44px minimum, rather than imposing a universal 44px native-button rule.

### Wheel buttons and hub

Each sector has a native semantic button with a 20px symbolic icon, wrapped centered label, 5px icon/label gap and at most twelve label characters before wrapping. Wheel buttons remain transparent at rest; hover and keyboard focus use the same 14% accent tint while preserving native focus treatment. The hub is a normal labeled button: Add files at the root, Back inside a category. Its circular shape remains stable across content changes.

Navigation uses the same operation tree as the labeled list. Default category dwell is 250ms (user-adjustable from 150–600ms), checked every 50ms while dragging. A newly exposed level requires at least 8px fresh movement before it arms. Releasing after a category transition leaves the category available for click/keyboard continuation. Conversion leaves submit directly; tool leaves open the shared parameter form. Escape moves back or closes the compact popup at the root without creating output.

### File rows and compact context

File rows use the frontmatter inset and radius, a subtle native hover fill and a minimum 44px height. Names ellipsize in the middle and expose the full path in a tooltip; remove controls have a native symbolic icon and tooltip. Compact mode replaces the panel with a native button showing selection and output context; its text middle-ellipsizes at a maximum of 38 characters and opens a scrollable review dialog.

### Status and jobs

Status uses the frontmatter padding and radius, with 42px normal and 24px compact minimum content height. It remains visible when the operation view scrolls and switches to the native error role for failures. Shared job rows have 12px padding, 6px vertical gaps, a 12px title/action gap, a native progress bar, a middle-ellipsized semibold title and selectable wrapped details. Action text follows state: Cancel while running, Retry after recoverable failure/cancellation, Reveal when output exists; publishing disables the action. Errors remain in the job row.

### Parameter form and list navigation

The same parameter dialog serves conversions and tools. Preview changes debounce for 250ms, cancellation invalidates old work, and generation checks prevent stale previews from replacing current values. Forms keep destination/source-preservation context readable and native action controls reachable. List mode provides labeled operation buttons grouped by the same categories; each operation button has a minimum 44px height, with 4px gaps and 12px heading separation. No chip/tag component or decorative card system is implemented.

### Taskbar indicator

The existing citrus application icon also identifies the native Ayatana status indicator. Its menu is a separate GTK3 surface that inherits the desktop’s menu typography, colors, selection states, separators and focus behavior; the application’s GTK4 stylesheet does not restyle it. Reuse the original icon asset rather than treating its illustration colors as new interface tokens.

A disabled first row reads Mandarin is ready, or reports the live count of queued, running, validating and publishing conversions. The menu refreshes that state every two seconds. Its actions are Open Mandarin, Add files…, Conversion jobs, then a native separator and Quit Mandarin. Open Mandarin and Conversion jobs reveal the normal shared window; Add files… reveals that window and opens its native file picker. Conversion jobs does not introduce a separate job screen.

Closing the main window hides it only while the indicator is connected, keeping conversions and the native menu available. If that connection disappears while the window is hidden, the application presents the window again. Explicit Quit Mandarin prompts when conversions are active, using a native Adw confirmation with Keep working as the default and Cancel and quit as the explicit exit action. Without a connected indicator, closing retains the existing active-job confirmation instead of silently hiding the application. These behaviors extend the native controls and shared jobs model without adding custom menu dimensions, colors or typography.

## Do's and Don'ts

### Do:

- **Do** preserve native focus rings, desktop text scaling, high-contrast preferences and reduced-motion behavior.
- **Do** keep the same operations and parameter form available through the radial and keyboard list interfaces.
- **Do** keep selected files, the actual output destination and recovery actions accessible in compact mode.
- **Do** use symbolic native icons with text or a tooltip; keep filenames in the normal desktop face.
- **Do** keep engine details in diagnostics and show useful errors beside the task or persistent job state.

### Don't:

- **Don’t** force the warm light wheel palette onto native windows, fields or dialogs in dark mode.
- **Don’t** treat a recognized extension as proof that an operation is available.
- **Don’t** replace native controls with decorative web-style cards or remove native focus treatment.
- **Don’t** introduce entrance animation or substitute animation for meaningful progress.
- **Don’t** use icon-only controls without a tooltip and accessible name.
