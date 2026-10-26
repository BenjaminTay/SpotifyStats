# Mobile Navigation Orientation Implementation Plan

> 历史实施提纲：已省略大段实现／测试代码草稿、重复命令及红绿测试步骤，保留设计要求、分工、接口示例与原验收事实。正文中的任务和Expected属于当时计划；当前行为见[文档地图](../../README.md)。

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

涉及文件：`frontend/src/components/layout/routeContext.ts`、`frontend/src/tests/masthead-route-context.test.ts`。

- Implement route context helper

Create `frontend/src/components/layout/routeContext.ts` with `MastheadNavTo`, `MastheadRouteContext`, and `getMastheadRouteContext(pathname, search)`. The helper must return parent active owners for `/analysis/*`, `/billboard/*`, and `/community/*`; it must return `activeNavTo: null` and `showMobileContext: false` for `/music/*`.

---

### Task 2: Update Masthead Active State Without Adding a New Context Bar

涉及文件：`frontend/src/components/layout/Masthead.tsx`、`frontend/src/tests/phase5-architecture.test.ts`。

- Write architecture guardrail before implementation
- Update Masthead imports and route state

Add active helper:

- Strengthen mobile active nav styling

---

- 历史实施约束：Render each enabled nav item as `Link`, not `NavLink`, and compute active from `isNavActive(item.to)`.

### Task 3: Browser Smoke Verification

- No source file changes unless a smoke failure points to a real issue.
- Start or reuse local services

In another shell:

- Manually inspect the old weak-orientation route

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

- 历史验收要求：PASS, no console warning/error, no horizontal overflow.
- 历史验收要求：PASS, no missing accessible names, no nested interactive controls, no duplicate ids.

### Task 4: Build Verification and Handoff

- No additional source file changes expected.
- Report changed files and validation

Expected changed files:

```text
 M frontend/src/components/layout/Masthead.tsx
 M frontend/src/tests/phase5-architecture.test.ts
?? frontend/src/components/layout/routeContext.ts
?? frontend/src/tests/masthead-route-context.test.ts
```

Do not commit unless the user explicitly asks for a commit.

- 历史验收要求：Existing Vite large chunk warnings are acceptable if no new build failure is introduced.

## Self-Review

- Spec coverage: route ownership, stronger active state, active scroll, no duplicate sticky breadcrumb, overflow/accessibility/browser validation are covered by Tasks 1-4.
- Placeholder scan: no reserved placeholder markers are present.
- Type consistency: `MastheadNavTo`, `MastheadRouteContext`, and `getMastheadRouteContext(pathname, search)` are introduced in Task 1 and consumed in Task 2 with matching names.
