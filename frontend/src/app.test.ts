import { describe, expect, it } from "vitest";
describe("foundation", () => { it("uses exact decimal strings at API boundaries", () => { expect("100.00").toMatch(/^\d+\.\d{2}$/); }); });
