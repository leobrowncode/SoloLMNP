import { describe, expect, it, vi } from "vitest";
import { REFUSAL, refusalMessage, request } from "./ledger";

describe("refusalMessage", () => {
  it("keeps a domain message and drops the validation payload", () => {
    expect(refusalMessage({ detail: { code: "SOURCE_NOT_CLOSED", message: "Clôturez l’exercice précédent." } }))
      .toBe("Clôturez l’exercice précédent.");
    const secret = "ne-pas-recopier-la-saisie";
    expect(refusalMessage({
      detail: [{
        type: "value_error",
        loc: ["body"],
        msg: "Value error, Le terrain et le bâtiment doivent totaliser le prix d’acquisition.",
        input: { notes: secret },
      }],
    })).toBe("Le terrain et le bâtiment doivent totaliser le prix d’acquisition.");
    expect(refusalMessage({
      detail: [
        { msg: "Value error, Premier contrôle." },
        { msg: "Value error, Second contrôle." },
      ],
    })).toBe("Premier contrôle. Second contrôle.");
    expect(refusalMessage({ detail: "Référence déjà utilisée." })).toBe("Référence déjà utilisée.");
    expect(refusalMessage({})).toBe(REFUSAL);
    expect(refusalMessage(null)).toBe(REFUSAL);
  });

  it("surfaces the validation sentence from a refused request", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
      detail: [{ msg: "Value error, La ventilation doit égaler le montant total de l’échéance.", input: { amount: "10.00" } }],
    }), { status: 422 })));
    await expect(request("/loans/1/payments", "POST", {}, "/api/operations"))
      .rejects.toThrow("La ventilation doit égaler le montant total de l’échéance.");
  });
});
