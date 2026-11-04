import type { SupportingDocumentRow } from "./conservation";
import { parseApiErrorDetail } from "./errors";
import { RequestError, request } from "./ledger";

export interface StoragePolicy {
  backend: "local" | "blob";
  max_upload_bytes: number;
  inline_upload_bytes: number;
  direct_upload: boolean;
  function_body_bytes: number;
}

export interface DocumentLink {
  entry_number?: string | null;
  accounting_date?: string;
  piece_reference?: string;
}

interface DirectGrant extends StoragePolicy {
  mode: "inline" | "direct";
  stored_name?: string;
  method?: string;
  upload_url?: string;
  headers?: Record<string, string>;
}

export function needsDirectUpload(size: number, policy: StoragePolicy): boolean {
  return policy.direct_upload && size > policy.inline_upload_bytes;
}

function bytesToBase64(content: ArrayBuffer): string {
  const bytes = new Uint8Array(content);
  let binary = "";
  const chunk = 0x8000;
  for (let index = 0; index < bytes.length; index += chunk) {
    binary += String.fromCharCode(...bytes.subarray(index, index + chunk));
  }
  return btoa(binary);
}

export async function sha256Hex(content: ArrayBuffer): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", content);
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

export async function uploadInline(
  file: File,
  content: ArrayBuffer,
  link: DocumentLink,
): Promise<SupportingDocumentRow> {
  return request<SupportingDocumentRow>(
    "/documents",
    "POST",
    {
      filename: file.name,
      media_type: file.type,
      content_base64: bytesToBase64(content),
      ...link,
    },
    "/api/filing",
  );
}

export async function uploadDirect(
  file: File,
  content: ArrayBuffer,
  link: DocumentLink,
): Promise<SupportingDocumentRow> {
  const grant = await request<DirectGrant>(
    "/documents/upload-grant",
    "POST",
    { filename: file.name, media_type: file.type, size: content.byteLength },
    "/api/filing",
  );
  if (grant.mode !== "direct" || !grant.upload_url || !grant.stored_name || !grant.headers) {
    return uploadInline(file, content, link);
  }
  const sent = await fetch(grant.upload_url, {
    method: grant.method ?? "PUT",
    headers: grant.headers,
    body: content,
  });
  if (!sent.ok) {
    throw new RequestError(
      parseApiErrorDetail({ code: "DOCUMENT_STORE", message: "L’envoi direct a été refusé." }),
      sent.status,
    );
  }
  return request<SupportingDocumentRow>(
    "/documents/complete",
    "POST",
    {
      filename: file.name,
      media_type: file.type,
      stored_name: grant.stored_name,
      sha256: await sha256Hex(content),
      size: content.byteLength,
      ...link,
    },
    "/api/filing",
  );
}
