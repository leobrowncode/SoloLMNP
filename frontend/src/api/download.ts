import { parseApiErrorDetail, type ApiErrorDetail } from "./errors";
import { RequestError } from "./ledger";

export async function downloadFiling(path: string): Promise<void> {
  const response = await fetch(path, {
    method: "GET",
    cache: "no-store",
    headers: { "X-SoloLMNP-Request": "1", Accept: "application/octet-stream, application/json" },
  });
  if (!response.ok) {
    let detail: ApiErrorDetail;
    try {
      const data = await response.json() as { detail?: unknown };
      detail = parseApiErrorDetail(data.detail as Parameters<typeof parseApiErrorDetail>[0]);
    } catch {
      detail = parseApiErrorDetail(undefined);
    }
    throw new RequestError(detail, response.status);
  }
  const blob = await response.blob();
  const name = filenameFrom(response.headers.get("Content-Disposition"));
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = name;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  // The browser reads the blob after the click. Revoking immediately can
  // cancel the download before the file is written.
  window.setTimeout(() => URL.revokeObjectURL(url), 1500);
}

function filenameFrom(header: string | null): string {
  const match = header ? /filename="([^"]+)"/.exec(header) : null;
  return match?.[1] || "export";
}
