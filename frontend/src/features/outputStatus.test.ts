import { expect, test } from "vitest";
import { calculationNotice, outputLabel, outputTrust, readyToCopy } from "./outputStatus";

test("a research payload never counts as ready to copy", () => {
  const research = { output_status: "recherche", declarable: true, output_label: "Recherche" };
  expect(outputTrust(research)).toBe("recherche");
  expect(readyToCopy(research)).toBe(false);
  expect(outputLabel(research)).toBe("Recherche");
  expect(calculationNotice("recherche")).toMatch(/pas une base de déclaration/);
  expect(calculationNotice("recherche")).not.toMatch(/Prête à recopier/);
});

test("provisional and declarable stay distinct", () => {
  expect(outputTrust({ output_status: "provisoire" })).toBe("provisoire");
  expect(readyToCopy({ output_status: "provisoire", declarable: true })).toBe(false);
  expect(outputLabel({ output_status: "provisoire" })).toBe("Provisoire");
  expect(readyToCopy({ output_status: "declarable" })).toBe(true);
  expect(outputLabel({ declarable: true })).toBe("Déclarable");
  expect(outputTrust({})).toBe("recherche");
  expect(calculationNotice("provisoire")).not.toMatch(/Prête à recopier/);
  expect(calculationNotice("declarable")).not.toMatch(/Prête à recopier/);
});
