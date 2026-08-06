import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// React Testing Library does not auto-register cleanup unless the test
// globals are enabled; register it explicitly so rendered trees do not leak
// between tests.
afterEach(() => {
  cleanup();
});
