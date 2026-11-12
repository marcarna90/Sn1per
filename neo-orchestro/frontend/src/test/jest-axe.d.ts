// Minimal local typings for jest-axe (it ships none; @types/jest-axe would pull an obsolete
// MPL-licensed axe-core 3.x that never runs). Ambient file: no top-level import/export.
declare module "jest-axe" {
  export interface AxeViolation {
    id: string;
    help: string;
    nodes: unknown[];
  }
  export interface AxeResults {
    violations: AxeViolation[];
  }
  export function axe(
    container: Element | string,
    options?: Record<string, unknown>,
  ): Promise<AxeResults>;
  export const toHaveNoViolations: {
    toHaveNoViolations: (results: AxeResults) => { pass: boolean; message: () => string };
  };
}
