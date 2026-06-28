# Mobile Navigation Orientation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve mobile navigation orientation without duplicating the existing page-level breadcrumbs such as `Music / 艺人详情` or `Music / 专辑详情`.

**Architecture:** Add a pure route-context helper that maps the current pathname/search to a top-level nav owner. `Masthead` consumes that helper to make nested routes highlight their parent nav item, strengthen the mobile active chip, and auto-scroll the active item into view. Detail pages under `/music/*` keep using their existing in-page breadcrumb and do not receive an extra sticky context strip.

**Tech Stack:** React 19, React Router v7, TypeScript, Tailwind CSS v4, Vitest, existing CDP/Playwright smoke scripts.

---

## File Structure

- Create: `frontend/src/components/layout/routeContext.ts`
  - Pure route parsing and display metadata.
  - No React imports, no DOM access, easy unit tests.
- Create: `frontend/src/tests/masthead-route-context.test.ts`
  - Tests route ownership for top-level, nested, community detail, and music detail routes.
- Modify: `frontend/src/components/layout/Masthead.tsx`
  - Use `useLocation()`.
  - Use `getMastheadRouteContext()` for active parent nav state.
  - Use stronger mobile active chip styles.
  - Scroll active nav item into view on narrow screens.
  - Do not render a new `当前位置` strip.
- Modify: `frontend/src/tests/phase5-architecture.test.ts`
  - Keep existing overflow guardrails.
  - Add source-level guardrails for route context helper, active scroll, and no duplicate sticky breadcrumb.

## Design Decisions

- Keep the existing top sticky masthead and horizontal nav.
- Do not introduce a bottom nav or a second sticky navigation/context bar.
- Treat nested top-level sections as owned by their primary entry:
  - `/analysis/*` -> `/analysis`
  - `/billboard/*` -> `/billboard`
  - `/community/*` -> `/community`
- Treat `/music/*` as detail pages with no top-level owner. They already show `Music / 单曲详情`, `Music / 艺人详情`, or `Music / 专辑详情` inside the page hero, so the masthead should not repeat that information.
- The mobile improvement is therefore subtle: clearer active chip where a parent owner exists, plus active item auto-scroll.

## Acceptance Criteria

- On 390px mobile `/music/artists/21%20Savage`, the header does not show a duplicate sticky `音乐详情 / 艺人` strip, while the page body still shows the existing `Music / 艺人详情`.
- On 390px mobile `/billboard/records`, the Billboard nav item is visually active.
- On 390px mobile `/analysis/charts`, the Analysis nav item is visually active.
- On 390px mobile `/community/post/:postId`, the Community nav item is visually active.
- Active nav items scroll into view on mobile when a parent nav owner exists.
- Page-level horizontal overflow remains zero: `bodyScrollWidth <= viewportWidth` and `documentScrollWidth <= viewportWidth`.
- No new console errors or warnings in route smoke.
- Interactive controls keep accessible names and avoid nested interactive violations.

---

### Task 1: Add Pure Route Context Helper

**Files:**
- Create: `frontend/src/components/layout/routeContext.ts`
- Create: `frontend/src/tests/masthead-route-context.test.ts`

- [ ] **Step 1: Write failing tests**

Create `frontend/src/tests/masthead-route-context.test.ts`:

```ts
import { describe, expect, it } from 'vitest'

import { getMastheadRouteContext } from '../components/layout/routeContext'

describe('masthead route context', () => {
  it('marks top-level pages without a mobile context strip', () => {
    expect(getMastheadRouteContext('/', '')).toEqual({
      activeNavTo: '/',
      contextSegments: ['总览'],
      title: null,
      showMobileContext: false,
    })
  })

  it('maps nested analysis routes to the analysis nav item', () => {
    expect(getMastheadRouteContext('/analysis/charts', '?entity=artist')).toEqual({
      activeNavTo: '/analysis',
      contextSegments: ['分析', '排行榜'],
      title: null,
      showMobileContext: true,
    })
  })

  it('maps nested billboard routes to the billboard nav item', () => {
    expect(getMastheadRouteContext('/billboard/records', '')).toEqual({
      activeNavTo: '/billboard',
      contextSegments: ['Billboard', '纪录'],
      title: null,
      showMobileContext: true,
    })
  })

  it('keeps music artist detail routes as detail context without a fake nav owner', () => {
    expect(getMastheadRouteContext('/music/artists/21%20Savage', '')).toEqual({
      activeNavTo: null,
      contextSegments: ['音乐详情', '艺人'],
      title: '21 Savage',
      showMobileContext: false,
    })
  })

  it('uses album artist query text when available', () => {
    expect(getMastheadRouteContext('/music/albums/Midnights', '?artist=Taylor%20Swift')).toEqual({
      activeNavTo: null,
      contextSegments: ['音乐详情', '专辑'],
      title: 'Midnights · Taylor Swift',
      showMobileContext: false,
    })
  })

  it('maps community detail routes to the community nav item', () => {
    expect(getMastheadRouteContext('/community/post/abc123', '')).toEqual({
      activeNavTo: '/community',
      contextSegments: ['社区', '帖子'],
      title: null,
      showMobileContext: true,
    })
  })
})
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd frontend && npm test -- masthead-route-context
```

Expected: FAIL because `frontend/src/components/layout/routeContext.ts` does not exist.

- [ ] **Step 3: Implement route context helper**

Create `frontend/src/components/layout/routeContext.ts` with `MastheadNavTo`, `MastheadRouteContext`, and `getMastheadRouteContext(pathname, search)`. The helper must return parent active owners for `/analysis/*`, `/billboard/*`, and `/community/*`; it must return `activeNavTo: null` and `showMobileContext: false` for `/music/*`.

- [ ] **Step 4: Run route context tests**

Run:

```bash
cd frontend && npm test -- masthead-route-context
```

Expected: PASS.

---

### Task 2: Update Masthead Active State Without Adding a New Context Bar

**Files:**
- Modify: `frontend/src/components/layout/Masthead.tsx`
- Modify: `frontend/src/tests/phase5-architecture.test.ts`

- [ ] **Step 1: Write architecture guardrail before implementation**

Modify `frontend/src/tests/phase5-architecture.test.ts` imports:

```ts
import routeContextSource from '../components/layout/routeContext.ts?raw'
```

Add this test near the existing masthead mobile guardrails:

```ts
  it('keeps mobile masthead orientation explicit without duplicating detail breadcrumbs', () => {
    expect(mastheadSource).toContain('getMastheadRouteContext')
    expect(mastheadSource).toContain('scrollIntoView')
    expect(mastheadSource).not.toContain('aria-label="当前位置"')
    expect(mastheadSource).not.toContain('返回上一页')
    expect(routeContextSource).toContain("pathname.startsWith('/music/artists/')")
    expect(routeContextSource).toContain('activeNavTo: null')
  })
```

- [ ] **Step 2: Run guardrail to verify failure**

Run:

```bash
cd frontend && npm test -- phase5-architecture
```

Expected: FAIL because `Masthead.tsx` does not yet use route context or active auto-scroll.

- [ ] **Step 3: Update Masthead imports and route state**

Modify `frontend/src/components/layout/Masthead.tsx` imports:

```ts
import { Link, useLocation } from 'react-router-dom'
import { useEffect, useMemo, useRef } from 'react'
import { ThemeToggle } from './ThemeToggle'
import { cn } from '@/lib/utils'
import { getBillboardName, useBillboardNameVersion } from '@/lib/billboard-name'
import { getMastheadRouteContext, type MastheadNavTo } from './routeContext'
```

Inside `Masthead`, add:

```ts
  const location = useLocation()
  const activeNavRef = useRef<HTMLAnchorElement | null>(null)
  const routeContext = useMemo(
    () => getMastheadRouteContext(location.pathname, location.search),
    [location.pathname, location.search],
  )
```

Add active auto-scroll:

```ts
  useEffect(() => {
    const isMobile = window.matchMedia('(max-width: 639px)').matches
    if (!isMobile) return
    activeNavRef.current?.scrollIntoView({
      behavior: 'smooth',
      block: 'nearest',
      inline: 'center',
    })
  }, [routeContext.activeNavTo])
```

Add active helper:

```ts
  const isNavActive = (to: MastheadNavTo) => {
    if (routeContext.activeNavTo) return routeContext.activeNavTo === to
    return to === '/' && location.pathname === '/'
  }
```

- [ ] **Step 4: Strengthen mobile active nav styling**

Render each enabled nav item as `Link`, not `NavLink`, and compute active from `isNavActive(item.to)`:

```tsx
<Link
  key={item.to}
  to={item.to}
  ref={active ? activeNavRef : undefined}
  aria-current={active ? 'page' : undefined}
  className={cn(
    'rounded-[7px] border px-2.5 py-1.5 text-[12px] font-semibold uppercase tracking-[1.2px] transition-colors duration-200 sm:border-0 sm:px-0 sm:py-0.5',
    active
      ? 'border-accent-foreground/20 bg-accent-foreground/10 text-foreground sm:border-b-2 sm:border-accent-foreground sm:bg-transparent'
      : 'border-transparent text-muted-foreground hover:bg-muted/70 hover:text-foreground sm:hover:bg-transparent',
  )}
>
  {item.label}
</Link>
```

Keep these containment classes on `<nav>`:

```tsx
className="order-3 flex w-full min-w-0 max-w-full basis-full gap-2 overflow-x-auto whitespace-nowrap pb-1 sm:order-none sm:w-auto sm:max-w-none sm:basis-auto sm:gap-6 sm:pb-0"
```

- [ ] **Step 5: Run Masthead-related tests**

Run:

```bash
cd frontend && npm test -- masthead-route-context phase5-architecture
```

Expected: PASS.

---

### Task 3: Browser Smoke Verification

**Files:**
- No source file changes unless a smoke failure points to a real issue.

- [ ] **Step 1: Start or reuse local services**

Use existing services if already running. Otherwise:

```bash
source .venv/bin/activate && SPOTIFY_STATS_WARMUP=0 uvicorn backend.main:app --reload --reload-dir backend
```

In another shell:

```bash
cd frontend && npm run dev
```

- [ ] **Step 2: Run route smoke on mobile routes**

Run:

```bash
node scripts/frontend_route_smoke.mjs \
  --routes /music/artists/21%20Savage,/billboard/records,/analysis/charts,/community,/ai-insights,/settings \
  --viewport mobile \
  --max-scroll-overflow 0 \
  --fail-on-console-warning
```

Expected: PASS, no console warning/error, no horizontal overflow.

- [ ] **Step 3: Run control inventory on mobile with detail routes**

Run:

```bash
node scripts/frontend_control_inventory_smoke.mjs \
  --viewport mobile \
  --include-detail-routes \
  --max-violations 0
```

Expected: PASS, no missing accessible names, no nested interactive controls, no duplicate ids.

- [ ] **Step 4: Manually inspect the old weak-orientation route**

Open 390px mobile view for:

```text
http://localhost:5173/music/artists/21%20Savage
```

Confirm:

- The header does not contain a duplicate sticky `音乐详情 / 艺人` strip.
- The page hero still contains `Music / 艺人详情`.
- The page still contains the artist detail body.
- The horizontal nav is scrollable and does not create page-level horizontal overflow.

---

### Task 4: Build Verification and Handoff

**Files:**
- No additional source file changes expected.

- [ ] **Step 1: Run focused frontend tests**

Run:

```bash
cd frontend && npm test -- masthead-route-context phase5-architecture
```

Expected: PASS.

- [ ] **Step 2: Run production build**

Run:

```bash
cd frontend && npm run build
```

Expected: PASS. Existing Vite large chunk warnings are acceptable if no new build failure is introduced.

- [ ] **Step 3: Report changed files and validation**

Run:

```bash
git status --short
```

Expected changed files:

```text
 M frontend/src/components/layout/Masthead.tsx
 M frontend/src/tests/phase5-architecture.test.ts
?? frontend/src/components/layout/routeContext.ts
?? frontend/src/tests/masthead-route-context.test.ts
```

Do not commit unless the user explicitly asks for a commit.

## Self-Review

- Spec coverage: route ownership, stronger active state, active scroll, no duplicate sticky breadcrumb, overflow/accessibility/browser validation are covered by Tasks 1-4.
- Placeholder scan: no reserved placeholder markers are present.
- Type consistency: `MastheadNavTo`, `MastheadRouteContext`, and `getMastheadRouteContext(pathname, search)` are introduced in Task 1 and consumed in Task 2 with matching names.
