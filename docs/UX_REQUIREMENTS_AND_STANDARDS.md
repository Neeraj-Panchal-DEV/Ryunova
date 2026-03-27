# RyuNova Platform – UX requirements and standards

**Application:** RyuNova Platform  
**Design direction:** Minimalist, **compact** admin workflow (Uber-inspired: clear hierarchy, low clutter) with a **modern delivery-app visual language** in implementation—**Plus Jakarta Sans**, **black primary actions**, **soft gray page background**, **rounded surfaces**, and a **dark fixed header** for global chrome (aligned with the public landing).

**Implementation reference:** `web/static/app.css` (global tokens, layout, tables, forms, buttons, snackbar), `web/templates/base.html` (font link, header/nav, footer), `web/static/taxonomy.css` + `taxonomy.js` (categories/brands: drawers, sortable table). New screens should reuse these patterns before introducing new components.

---

## 1. Design principles

| Principle | Requirement |
|-----------|-------------|
| **Minimalist** | Clean UI with no decorative clutter. Task-first; limited palette; purposeful whitespace between *groups*, dense within lists/tables. |
| **Compact** | Dense but readable: efficient tables and filters so staff see more rows without excessive scrolling. |
| **Scannable** | Clear headings, consistent alignment, hierarchy via size/weight/color (not color alone for meaning). |
| **Consistent** | Same patterns for lists, forms, filters, badges, and actions across Products, Categories, Brands, and future Listing/Order areas. |
| **Accessible** | WCAG 2.1 Level AA where practical: contrast, visible focus, keyboard use, semantics, labels. |

---

## 2. Visual design (as implemented)

### 2.1 Typography

| Element | Standard |
|---------|----------|
| **Primary font** | **Plus Jakarta Sans** (Google Fonts), with system-ui fallbacks: `-apple-system`, `BlinkMacSystemFont`, `"Segoe UI"`, `Roboto`, `sans-serif`. |
| **Single family** | Do not mix arbitrary display fonts; keep one sans stack for UI and forms. |
| **Base size** | **0.9375rem (15px)** on `.site-layout` for body; line-height **1.5**. |
| **Page title** | **1.75rem**, weight **700**, tight letter-spacing (**-0.03em**), black text. |
| **Table header labels** | **0.8125rem**, **600**, **uppercase**, increased letter-spacing (**0.04em**), secondary gray. |
| **Supporting / muted** | **0.875rem** for secondary table cells; **0.75rem** for badges where used. |

*Earlier drafts suggested Inter/system-only at 14px; the **implemented** standard is Plus Jakarta Sans at 15px base for readability while staying compact.*

### 2.2 Colour and surfaces (design tokens)

Implementation uses **CSS custom properties** in `:root` (`app.css`). New UI should use these tokens—not one-off hex values—unless adding a documented token.

| Token / role | Typical value | Use |
|--------------|---------------|-----|
| `--primary` | `#000000` | Primary buttons (filled black), key emphasis. |
| `--primary-hover` | `#333333` | Primary button hover. |
| `--primary-soft` | `rgba(0,0,0,0.08)` | Focus rings (`--focus-ring`). |
| `--text` | `#000000` | Main body and titles on light surfaces. |
| `--text-secondary` | `#6b6b6b` | Secondary labels, table header text. |
| `--text-muted` | `#757575` | Muted cells, placeholders, inactive rows. |
| `--bg-page` | `#f6f6f6` | Page background behind content. |
| `--bg-card` | `#ffffff` | Cards, table wrap, drawers, modals. |
| `--border` / `--border-strong` | `#e8e8e8` / `#d0d0d0` | Dividers, input outlines. |
| `--input-bg` | `#f6f6f6` | Input fills, subtle badge backgrounds. |
| `--danger` | `#e23744` | Destructive actions (e.g. delete). |
| **Header bar** | `#0a0a0a` (not a token) | Fixed top nav: logo + links on dark. |
| **Snackbar** | Dark / semantic greens, reds, blues | Flash messages (see §4.5). |

**Shadows:** `--shadow-sm`, `--shadow-md`, `--shadow-lg` for cards and elevated panels—use sparingly (calm, not heavy Material elevation).

**Radii:** `--radius` (12px), `--radius-sm` (8px), `--radius-pill` (9999px) for pills/buttons.

### 2.3 Global chrome

| Element | Standard |
|---------|----------|
| **Header** | **Fixed** top bar, height **60px** (`--header-h`), background **#0a0a0a**, light border **#262626**, subtle bottom highlight. |
| **Header content** | Max-width **1280px**, horizontal padding **20px**; logo (image + wordmark) left; **pill-shaped** nav links right (semi-transparent hover). |
| **Main content** | Max-width **1280px**, padding **24px 20px 40px**, with **top padding** offset for fixed header (`calc(var(--header-h) + 24px)`). |
| **Nav labels** | Signed-in: Home, Products, Categories, Brands, plus **account control**: **profile photo** (or initials) top-right opens a small menu (**Profile**, **Sign out**). If the session has a token but profile cache failed, fall back to a plain **Sign out** link. Landing may hide some links—follow `base.html` patterns. |
| **Footer** | Slim footer: brand line shows **RYUNOVA PLATFORM** when signed out or when no organisation is scoped (e.g. platform “all organisations”); shows the **selected organisation name** when signed in with `organisation_id` set (+ copyright). |

### 2.4 Spacing and density

- **Tables:** Cell padding **14px 16px**; header row **sticky** with light gray background (**#fafafa**); row hover **#fafafa**; **inactive** rows (e.g. disabled catalog items) use **muted text** + **#fafafa** background (`.row-inactive`).
- **Filter bars:** Wrapped flex row with **12–14px** gaps; controls use shared **min-height 52px** where specified (`.input--filter-control`).
- **Forms (`.surface--form`):** **28–32px** internal padding—slightly roomier than tables for focus tasks.
- **Buttons (default):** **min-height 48px**, pill radius—favour **large tap targets** (delivery-app pattern), including for secondary/outline buttons.

---

## 3. Layout

### 3.1 Page structure

- **No sidebar in MVP1:** Navigation is **top bar only** (not a collapsible sidebar). Future deep admin may add one; keep tokens consistent.
- **Content width:** **1280px** max for main column—use full width up to that cap; avoid arbitrary narrow max-width for admin tables.
- **Toolbar:** `.toolbar`—page title left, primary action right (e.g. “Add product”), `flex-wrap` for small screens.

### 3.2 Lists and tables

- **Product list:** Wrapped in **`.table-wrap`** (white surface, border, radius, shadow). Thumbnail column **44×44px** images, rounded **8px**. **Badges** for status and enabled/disabled (`.badge`, `.badge--muted`).
- **Audit columns:** Where implemented (products, taxonomy API-fed columns), show **date added**, **last modified**, **added by**, **updated by** with **`.table-muted`** / secondary styling and **`.text-nowrap`** for ISO date snippets when needed.
- **Pagination:** **`.pagination`** bar below table—meta text + Previous/Next; page size comes from API (e.g. 10 / 20 / 50 / 100).

### 3.3 Taxonomy (categories & brands)

- **Table + JS:** List is **client-rendered** from API JSON; **sortable** column headers (`.taxonomy-th`, indicators ▲/▼).
- **Row click** opens **detail**; **Add** opens **right-hand drawer** (`.drawer-panel`, overlay `.drawer-overlay`). Drawers slide in with **transform** + backdrop **fade** (`taxonomy.css`).
- **Detail block:** **`.taxonomy-detail-dl`** / **`.taxonomy-detail-row`** for label/value pairs (name, slug, description, audit fields, parent for categories). Reuse this **dl** pattern for **product “Record details”** on edit where applicable.
- **Actions in drawer:** Use existing button classes; **`.btn--yellow`** is used for emphasis links (e.g. “Edit”) in taxonomy detail—keep usage rare and consistent.

### 3.4 Forms

- **Grid forms:** **`.form.form--grid`** with **`.form-grid`**—multi-column on wide viewports, single column on narrow.
- **Fields:** **`.field`** + **`.field__label`**; optional **`.field__optional`**; full-width rows **`.field--full`**.
- **Inputs:** **`.input`**—filled gray background (`--input-bg`), **no** heavy border; **52px** min-height on main inputs for touch/mouse comfort.
- **Primary submit:** **`.btn.btn--primary.btn--lg`** on main forms.
- **Product description:** **TinyMCE** (GPL build from CDN) on **`#product_description_html`**—toolbar for headings, lists, alignment, links, tables, **source code**. Content is persisted as **HTML** in `ryunova_product_master.description` for channel payloads (e.g. Shopify `body_html`). Helper copy uses **`.field__hint`**; treat description as **trusted admin content** (sanitize only if ever rendered on a public storefront).

### 3.5 Surfaces (cards)

- **`.surface`** — white card, border, **12px** radius, **sm** shadow.
- **`.surface--filter`** — filter bars above lists.
- **`.surface--form`** — stronger **md** shadow for primary forms.

---

## 4. Components and patterns

### 4.1 Buttons

| Class | Use |
|-------|-----|
| **`.btn`** | Default: outline-style (inset border), pill, **48px** min-height. |
| **`.btn--primary`** | Black fill, white text—**one** primary action per view where possible. |
| **`.btn--secondary`** | Lower-emphasis actions. |
| **`.btn--danger`** | Delete / destructive (red). |
| **`.btn--yellow`** | High-visibility secondary CTA (taxonomy detail link)—use sparingly. |
| **`.btn--small`** | Table row actions, compact toolbars. |
| **`.btn--lg`** | Primary form submit. |
| **`.btn--disabled`** | Non-interactive state. |

**Interaction:** Slight **scale(0.98)** on `:active` for tactile feedback; respect **`:focus-visible`** (outline via `--focus-ring` pattern where applied).

### 4.2 Filters and search

- **Pattern:** **`.filter-bar.surface.surface--filter`** with search, selects, checkboxes (e.g. “Include disabled”), optional row count dropdown.
- **Alignment:** Controls share a consistent **vertical size** (filter control min-heights).

### 4.3 Status and feedback

- **Badges:** **`.badge`** / **`.badge--muted`** for status strings (draft, active, yes/no).
- **Empty states:** Single centered row in table: short copy + **`.table-link`** CTA (e.g. add first product).
- **Django messages:** **Snackbar** top-right (`#snackbar`, `flash-messages.js`)—auto-dismiss with fade; variants **success / error / warning / info** with semantic backgrounds (green/red/amber/blue dark tones). **`role="status"`**, **`aria-live="polite"`**.

### 4.4 Links in tables

- **`.table-link`** — bold black link; on hover, underline animates; color may shift toward primary black emphasis.

### 4.5 Auth (login)

- **`.auth-card`** — centered, **max-width 440px**, **16px** radius, **lg** shadow—distinct from dense admin tables.
- **Stacked fields** — **`.form--stack`** with comfortable vertical rhythm between fields.

---

## 5. Key screens (UX expectations — MVP1 alignment)

| Screen | UX requirement (current + forward) |
|--------|-----------------------------------|
| **Product list** | Table: thumb, title (link), brand, SKU, price, qty, status, enabled, **audit columns**, actions. Filter bar: search, status, include inactive, **page size**. Pagination below. |
| **Product edit** | Grid form; image upload; **Record details** block (dl) when editing—dates + added/updated by labels from API. |
| **Categories / brands** | Sortable table; row → detail drawer; add → drawer form; link to legacy **edit** URL where present. |
| **Login** | Auth card; email/password; social stubs if shown—match compact but spacious card pattern. |
| **Dashboard** | Compact widgets / demo stats; same chrome as rest of app. |
| **Listings / orders / channels** | Not in MVP1 UI; when built, **reuse** table, filter bar, badges, and tokens above. |

---

## 6. Responsiveness

- **Desktop-first** for admin; **1280px** content max; tables **scroll horizontally** inside **`.table-wrap`** / **`.taxonomy-table-wrap`** when needed.
- **Snackbar:** On very small screens, **inset** left/right for readability.
- **Touch:** Default buttons **48px** tall; checkboxes **20px** with large hit area on labels.

---

## 7. Accessibility (standards)

- **Contrast:** Aim for WCAG 2.1 AA on light surfaces; dark header uses white/light gray text on **#0a0a0a**—verify focus and hover states remain visible.
- **Focus:** Keyboard focus on taxonomy rows (`outline` on `tr[data-taxonomy-row]:focus`); extend the same discipline to new interactive rows.
- **Semantics:** One **`<main>`**; header **`aria-label`** on nav; table **`<th>`** with **scope**; form labels tied to controls.
- **Motion:** Drawer/overlay transitions are short; respect **`prefers-reduced-motion`** for future enhancements (reduce transition duration or disable transform animation).

---

## 8. Reference and summary

- **Visual reference:** Delivery-app–inspired **RyuNova** UI—**black CTAs**, **soft gray** page, **white surfaces**, **Plus Jakarta Sans**, **dark top bar**, **pill buttons**, **rounded inputs**.
- **UX reference:** Still **Uber-like** in spirit: calm, task-focused, minimal chrome in the **content** area; global header is **high-contrast** for wayfinding.
- **Compact requirement:** Achieved through **tight tables**, **efficient filter rows**, and **sensible defaults** for pagination—not by shrinking tap targets below **48px** for primary actions.
- **Outcome:** One coherent system (tokens + components) so new pages stay on-brand and accessible.

---

*Document version: **2.0** — aligned with `web/static/app.css`, `base.html`, and `taxonomy.css` as of MVP1 catalog UI. Update this doc when tokens or global patterns change.*
