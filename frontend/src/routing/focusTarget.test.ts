import { expect, test } from "vitest";
import { focusRouteTarget } from "./focusTarget";

test("focuses the hash target and falls back to main", () => {
  document.body.innerHTML = '<main id="main" tabindex="-1"></main><h2 id="ajouter-bien" tabindex="-1">Bien</h2>';
  expect(focusRouteTarget("")).toBe(true);
  expect(document.activeElement).toBe(document.getElementById("main"));
  expect(focusRouteTarget("#ajouter-bien")).toBe(true);
  expect(document.activeElement).toBe(document.getElementById("ajouter-bien"));
  expect(focusRouteTarget("#absent")).toBe(false);
  expect(focusRouteTarget("#ajouter-bien%20")).toBe(false);
});
