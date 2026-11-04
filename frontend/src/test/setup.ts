import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, beforeEach, vi } from "vitest";

const TOKEN_KEY = "sololmnp.token";

beforeEach(() => {
  sessionStorage.setItem(TOKEN_KEY, "vitest");
});

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
