import { expect, test } from "vitest";
import {
  activityCause, assetCreateCauses, centralizationCauses, closeConfirmCauses, closePrepareCauses,
  csvPreviewCauses, depreciationCalculateCauses, duplicatePostCauses, fiscalActionCauses,
  inventoryVerifyCauses, linkCauses, loanPostCauses, openYearCauses, openingGenerationCauses,
  operationEntryCauses, postDepreciationCauses, propertyCause, propertyEntryPostCauses,
  propertyEntryPreviewCauses, propertyEntryStartCauses, rentCauses, reopenCauses, restoreCauses,
  selectedYearCauses, unbalancedCause,
} from "./actionCauses";

const closed = [{ status: "CLOSED" }];
const ready = [{ status: "READY_TO_CLOSE" }];
const open = [{ status: "OPEN" }];

test("activity, property and open-year causes name a single missing prerequisite", () => {
  expect(activityCause(true)).toBeNull();
  expect(activityCause(false)?.action.href).toBe("/comptabilite/brouillons#creer-activite");
  expect(propertyCause(1)).toBeNull();
  expect(propertyCause(0)?.code).toBe("NO_PROPERTY");
  expect(openYearCauses(open)).toEqual([]);
  expect(openYearCauses([])[0]?.code).toBe("NO_YEAR");
  expect(openYearCauses(closed).map((item) => item.code)).toEqual(["YEAR_CLOSED"]);
  expect(openYearCauses(ready).map((item) => item.code)).toEqual(["YEAR_READY_TO_CLOSE"]);
  expect(openYearCauses([...closed, ...ready]).map((item) => item.code)).toEqual([
    "YEAR_CLOSED", "YEAR_READY_TO_CLOSE",
  ]);
  expect(openYearCauses([{ status: "OTHER" }])[0]?.code).toBe("NO_OPEN_YEAR");
  expect(openYearCauses([{}])).toEqual([]);
});

test("selected year causes distinguish closed, ready and unknown", () => {
  expect(selectedYearCauses(undefined)).toEqual([]);
  expect(selectedYearCauses("OPEN")).toEqual([]);
  expect(selectedYearCauses("CLOSED")[0]?.action.href).toBe("/fiscalite#reopen-title");
  expect(selectedYearCauses("READY_TO_CLOSE")[0]?.action.href).toBe("/fiscalite#close-title");
  expect(selectedYearCauses("LOCKED")[0]?.code).toBe("YEAR_NOT_OPEN");
});

test("operation, rent and asset entry causes stack independent blockers", () => {
  expect(operationEntryCauses(0, closed).map((item) => item.code)).toEqual(["NO_PROPERTY", "YEAR_CLOSED"]);
  expect(operationEntryCauses(2, open)).toEqual([]);
  expect(rentCauses(4, 0, []).map((item) => item.code)).toEqual(["NO_YEAR", "NO_TENANT"]);
  expect(rentCauses(4, 0, [])[1]?.action.href).toBe("/operations/biens#colocataires-4");
  expect(rentCauses(4, 1, open)).toEqual([]);
  expect(assetCreateCauses(0)).toHaveLength(1);
  expect(assetCreateCauses(1)).toEqual([]);
  expect(depreciationCalculateCauses(3, closed)).toEqual([]);
  expect(depreciationCalculateCauses(0, []).map((item) => item.code)).toEqual(["NO_YEAR"]);
  expect(postDepreciationCauses([{ status: "CALCULATED" }])).toEqual([]);
  expect(postDepreciationCauses([])[0]?.code).toBe("NO_PERIOD");
  expect(postDepreciationCauses([{ status: "POSTED" }])[0]?.code).toBe("ALL_POSTED");
  const unbooked = postDepreciationCauses([{ status: "CALCULATED", asset_on_ledger: false, booking: "entry" }]);
  expect(unbooked[0]?.code).toBe("ASSET_NOT_BOOKED");
  expect(unbooked[0]?.action.href).toBe("/immobilisations#entree-bien");
  expect(unbooked[0]?.action.label).toBe("Faire entrer le bien en comptabilité");
  const purchase = postDepreciationCauses([{ status: "CALCULATED", asset_on_ledger: false, booking: "journal" }]);
  expect(purchase[0]?.code).toBe("ASSET_PURCHASE_UNBOOKED");
  expect(purchase[0]?.action.href).toBe("/comptabilite/brouillons#nouvelle-ecriture");
  expect(propertyEntryStartCauses(0, ready).map((item) => item.code)).toEqual(["NO_PROPERTY", "YEAR_READY_TO_CLOSE"]);
  expect(propertyEntryPreviewCauses(0, 0).map((item) => item.code)).toEqual(["NO_PROPERTY", "NO_OPEN_YEAR"]);
  expect(propertyEntryPreviewCauses(1, 2)).toEqual([]);
  expect(propertyEntryPostCauses(true)).toEqual([]);
  expect(propertyEntryPostCauses(false)[0]?.code).toBe("NO_ENTRY_PREVIEW");
  expect(fiscalActionCauses(1, [])).toEqual([]);
  expect(fiscalActionCauses(0, closed)[0]?.code).toBe("YEAR_CLOSED");
  expect(unbalancedCause(9).action.href).toBe("/comptabilite/brouillons#ecriture-9");
});

test("opening generation ignores informational warnings and keeps every blocker", () => {
  expect(openingGenerationCauses(null)).toEqual([]);
  expect(openingGenerationCauses({
    preview_token: "token", total_debit: "1.00",
    warnings: [
      { code: "PREVIEW_ONLY", message: "info" },
      { code: "RESULT_ACCOUNT_REQUIRED", message: "compte" },
    ],
  })).toEqual([]);
  const causes = openingGenerationCauses({
    total_debit: "0.00",
    warnings: [
      { code: "SOURCE_NOT_CLOSED", message: "source" },
      { code: "INACTIVE_ACCOUNTS", message: "512000" },
    ],
  });
  expect(causes.map((item) => item.code)).toEqual(["NO_PREVIEW_TOKEN", "EMPTY_OPENING", "SOURCE_NOT_CLOSED", "INACTIVE_ACCOUNTS"]);
  expect(causes[3]?.message).toBe("512000");
});

test("inventory, centralization, closing and reopen list each unmet condition", () => {
  expect(inventoryVerifyCauses({
    yearStatus: "OPEN", generalJournalCount: 1, recoveryError: "", attempted: false,
  })).toEqual([]);
  expect(inventoryVerifyCauses({
    yearStatus: "CLOSED", generalJournalCount: 0, recoveryError: "stockage", attempted: true,
  })).toEqual([]);
  expect(inventoryVerifyCauses({
    yearStatus: "CLOSED", generalJournalCount: 0, recoveryError: "stockage", attempted: false,
  }).map((item) => item.code)).toEqual(["YEAR_CLOSED", "NO_GENERAL_JOURNAL", "INVENTORY_RECOVERY"]);
  expect(centralizationCauses("OPEN", false, "120")).toEqual([]);
  expect(centralizationCauses("READY_TO_CLOSE", true, "120").map((item) => item.code)).toEqual([
    "YEAR_READY_TO_CLOSE", "RESULT_ACCOUNT",
  ]);
  expect(closePrepareCauses({
    sealed: false, blocking: false, errors: [], warnings: [], acks: [],
  })).toEqual([]);
  expect(closePrepareCauses({
    sealed: true, blocking: true,
    errors: [{ code: "YEAR_DRAFTS", message: "brouillons" }, { code: "UNKNOWN", message: "autre" }],
    warnings: [{ code: "A" }], acks: [],
  }).map((item) => item.code)).toEqual(["SEALED", "YEAR_DRAFTS", "UNKNOWN", "WARNINGS_UNACKED"]);
  expect(closeConfirmCauses({
    prepared: true, sealed: false, blocking: false, errors: [],
  })).toEqual([]);
  expect(closeConfirmCauses({
    prepared: false, sealed: true, blocking: true, errors: [],
  }).map((item) => item.code)).toEqual(["NOT_PREPARED", "SEALED", "BLOCKING"]);
  expect(reopenCauses("ROUVRIR", "motif assez long")).toEqual([]);
  expect(reopenCauses("NON", "court").map((item) => item.code)).toEqual(["REOPEN_REASON", "REOPEN_CONFIRMATION"]);
  expect(linkCauses(true)).toEqual([]);
  expect(linkCauses(false)[0]?.code).toBe("ENTRY_PICK");
  expect(restoreCauses(true, true, "RESTAURER")).toEqual([]);
  expect(restoreCauses(false, false, "NON").map((item) => item.code)).toEqual([
    "RESTORE_BACKUP", "RESTORE_CONFIRMATION",
  ]);
  expect(restoreCauses(true, false, "RESTAURER").map((item) => item.code)).toEqual(["RESTORE_PREVIEW"]);
});

test("import buttons explain a missing file, a missing context and duplicates", () => {
  expect(csvPreviewCauses({
    hasContent: true, anchor: "/operations/banque#import-releve",
    missingProperty: false, missingYear: false, missingBank: false, missingLoan: false,
  })).toEqual([]);
  expect(csvPreviewCauses({
    hasContent: false, anchor: "/operations/transactions#import-operations",
    missingProperty: true, missingYear: true, missingBank: true, missingLoan: true,
  }).map((item) => item.code)).toEqual(["NO_CSV", "NO_PROPERTY", "NO_OPEN_YEAR", "NO_BANK", "NO_LOAN"]);
  expect(duplicatePostCauses(false, "/x")).toEqual([]);
  expect(duplicatePostCauses(true, "/operations/transactions#import-operations")[0]?.code).toBe("ALL_DUPLICATES");
  expect(loanPostCauses(true, true)).toEqual([]);
  expect(loanPostCauses(false, true)[0]?.code).toBe("MAPPING_UNCONFIRMED");
  expect(loanPostCauses(false, false).map((item) => item.code)).toEqual(["ALL_DUPLICATES"]);
});
