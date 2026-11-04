import { expect, test } from "vitest";
import { needsDirectUpload, type StoragePolicy } from "./documentUpload";

const local: StoragePolicy = {
  backend: "local",
  max_upload_bytes: 10_000_000,
  inline_upload_bytes: 10_000_000,
  direct_upload: false,
  function_body_bytes: 4_500_000,
};

const blob: StoragePolicy = {
  backend: "blob",
  max_upload_bytes: 10_000_000,
  inline_upload_bytes: 3_000_000,
  direct_upload: true,
  function_body_bytes: 4_500_000,
};

test("keeps a small file inline and sends a large Blob file directly", () => {
  expect(needsDirectUpload(100, local)).toBe(false);
  expect(needsDirectUpload(3_000_000, blob)).toBe(false);
  expect(needsDirectUpload(3_000_001, blob)).toBe(true);
});
