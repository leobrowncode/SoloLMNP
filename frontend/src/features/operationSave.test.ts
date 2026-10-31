import { describe, expect, it } from "vitest";
import { loanFollowUp, operationSaveNotice } from "./operationSave";

describe("loanFollowUp", () => {
  it("asks for a bank before any installment when nothing is posted", () => {
    const step = loanFollowUp({
      banks: 0,
      openYears: 1,
      onBalanceSheet: false,
      postingPath: "funding",
      remainingPrincipal: "0.00",
      loanId: 2,
    });
    expect(step.next?.label).toBe("Ajouter un compte bancaire");
    expect(step.detail).toContain("compte 164");
    expect(step.detail).not.toContain("Saisir une échéance");
    expect(step.next?.label).not.toBe("Saisir une échéance");
  });

  it("offers the drawdown, not an installment, once a bank exists", () => {
    const step = loanFollowUp({
      banks: 1,
      openYears: 1,
      onBalanceSheet: false,
      postingPath: "funding",
      remainingPrincipal: "0.00",
      loanId: 2,
    });
    expect(step.next).toEqual({
      label: "Enregistrer le déblocage",
      href: "/operations/emprunts#deblocage-2",
    });
    expect(step.detail).toContain("déblocage");
    expect(step.next?.label).not.toBe("Saisir une échéance");
  });

  it("offers only the property entry when the loan predates the exercise", () => {
    const step = loanFollowUp({
      banks: 1,
      openYears: 1,
      onBalanceSheet: false,
      postingPath: "property_entry",
      remainingPrincipal: "0.00",
      loanId: 3,
    });
    expect(step.next?.label).toBe("Faire entrer le bien en comptabilité");
    expect(step.detail).toContain("sans déblocage");
    expect(step.next?.label).not.toBe("Enregistrer le déblocage");
  });

  it("offers an installment only when the ledger still has capital to repay", () => {
    const step = loanFollowUp({
      banks: 1,
      openYears: 1,
      onBalanceSheet: true,
      postingPath: null,
      remainingPrincipal: "195000.00",
      loanId: 2,
    });
    expect(step.next?.label).toBe("Saisir une échéance");
    expect(step.detail).toBeUndefined();
  });
});

describe("operationSaveNotice", () => {
  it("does not suggest an installment after creating an unposted loan", () => {
    const notice = operationSaveNotice({
      path: "/loans",
      title: "Ajouter un emprunt",
      data: { lender: "Crédit Habitat 195k" },
      result: {
        id: 2,
        remaining_principal: "0.00",
        on_balance_sheet: false,
        posting_path: "funding",
      },
      banks: 1,
      openYears: 1,
    });
    expect(notice.next?.label).toBe("Enregistrer le déblocage");
    expect(notice.detail).toContain("compte 164");
    expect(notice.detail).not.toContain("Saisir une échéance");
    expect(notice.next?.label).not.toBe("Saisir une échéance");
  });
});
