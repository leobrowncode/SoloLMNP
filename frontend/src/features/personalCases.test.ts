import { expect, test } from "vitest";
import { idleCaseSentence, visiblePersonalLines } from "./personalCases";

const benefit = { case: "5NA", label: "Bénéfice", amount: "920.00", served: true };
const deficit = { case: "5NY", label: "Déficit", amount: "0.00", served: false };

test("shows only the served case and names the one left at zero", () => {
  const view = visiblePersonalLines([benefit, deficit]);
  expect(view.shown).toEqual([benefit]);
  expect(view.idleCase).toBe("5NY");
  expect(idleCaseSentence(view.idleCase ?? "")).toBe("La case 5NY reste à 0.");
});

test("a deficit hides the benefit row", () => {
  const loss = { case: "5NY", amount: "40.00", served: true };
  const zero = { case: "5NA", amount: "0.00", served: false };
  const view = visiblePersonalLines([zero, loss]);
  expect(view.shown).toEqual([loss]);
  expect(idleCaseSentence(view.idleCase ?? "")).toBe("La case 5NA reste à 0.");
});

test("two zero lines without a served flag keep 5NA only", () => {
  const view = visiblePersonalLines([
    { case: "5NA", amount: "0.00" },
    { case: "5NY", amount: "0.00" },
  ]);
  expect(view.shown.map((line) => line.case)).toEqual(["5NA"]);
  expect(view.idleCase).toBe("5NY");
});
