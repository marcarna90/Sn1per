# ADR 0009 — Frontend stack, token handling and accessibility

Status: Accepted

## Context

A professional, responsive, accessible UI (dashboard, scans, scope, users, audit, settings)
for a security platform. The browser is the most exposed part: XSS must not be able to steal
a long-lived credential, and role-based UI must never be mistaken for authorisation.

## Decision

**Stack.** React 19 + TypeScript (strict, `noUncheckedIndexedAccess`) + Vite 8 + Tailwind 4 +
React Router 7 + TanStack Query 5. Tests: Vitest + Testing Library + jest-axe. Lint/format:
ESLint (type-checked) + Prettier. Versions are locked by `package-lock.json` (`npm ci`).

- **TypeScript is pinned to 6.0.x.** TypeScript 7.0 is the newest release, but
  `typescript-eslint` 8.72 declares support for `>=4.8.4 <6.1.0`; forcing an unsupported
  combination would make the linter unreliable. Revisit when typescript-eslint supports 7.
- `npm overrides` pins `minimatch ^11.0.8`: the version ESLint 10 pulled had an advisory
  (GHSA-g3hv-75wg-m249). Result: `npm audit` reports 0 vulnerabilities (0 in runtime deps).

**Credentials.**
- The **access token lives in memory only** (never `localStorage`/`sessionStorage`), so an XSS
  cannot exfiltrate a long-lived secret. A page reload recovers the session through the
  **HttpOnly, SameSite=Strict refresh cookie** (ADR 0005).
- Cookie-authenticated calls (`/auth/refresh`, `/auth/logout`) send `X-Neo-CSRF: 1`.
- On a 401 the client refreshes **once**, shares that refresh between concurrent requests
  (single-flight), replays, and on failure ends the session — no refresh loops.
- The client only ever requests same-origin `/api/` and `/health/` paths, so a path can never
  send the bearer token or cookies to another host.
- The UI is same-origin by design (Vite proxy in development, nginx in production), so CORS
  stays closed and cookies keep their strict attributes.

**Authorisation.** Hiding menu entries and gating routes (`RequireRole`) is *only* UX; every
rule is enforced again by the API. Tests assert that the UI does not even issue admin requests
for lower roles, and the backend's RBAC matrix tests remain the source of truth.

**Error and state handling.** Every data view handles loading, error (with retry and request
reference), empty and permission states. Failed logins always show the same message; scope
refusals are explained in plain language (`scopeReasonLabel`); server validation messages are
shown, raw network/HTML errors never are.

**Accessibility (WCAG 2.2 AA intent).** Landmarks (`header`, `nav`, `main`, `footer`), a skip
link, focus moved to `main` after navigation, every control labelled, tables with captions and
scoped headers, errors in `role="alert"`, confirmations in `role="status"`, colour never the
only carrier of meaning (status/severity always have text), visible focus, `prefers-color-scheme`
dark mode, responsive layout. `jest-axe` runs on the main screens. **Not covered by automation:**
colour contrast (jsdom cannot compute it) and real screen-reader behaviour; these need a manual
pass / Playwright + axe in a real browser.

**Language.** The UI is in French with strings inline in components. A typed i18n layer
(catalogues + language switch) is deferred until a second language is actually required.

**Security headers.** The production nginx sends a strict CSP
(`default-src 'self'`, no inline script/style); the bundle has no external hosts and the app uses
no inline styles, so the policy holds.

## Alternatives rejected

- *Access token in `localStorage`* — the simplest design and the one XSS loves.
- *Next.js/SSR* — a server-side layer for an authenticated dashboard with no SEO needs.
- *MSW for API mocking* — a heavier dependency; a ~60-line fake `fetch` keeps tests explicit.
- *Redux/Zustand* — server state is TanStack Query's job; auth state fits one context.

## Licence notes

All runtime dependencies are MIT. In the dev tree: `axe-core` (MPL-2.0, test-time only),
`lightningcss` (MPL-2.0, build-time only, not shipped), `caniuse-lite` (CC-BY-4.0 data,
build-time only). None is bundled or modified. `@types/jest-axe` was *not* adopted (it pulls an
obsolete axe-core 3.x); a 20-line local declaration is used instead. See `docs/licences.md`.
