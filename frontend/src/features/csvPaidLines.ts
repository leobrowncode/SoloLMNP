/**
 * Detects « déjà payée = oui » before the preview request.
 * The server remains the authority; this only blocks the button early.
 */

const PAID_YES = new Set(["oui", "o", "yes", "x", "1"]);
const PAID_HEADERS = new Set(["paid", "payee", "deja payee", "reglee"]);

function normalize(value: string): string {
  return value
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .toLowerCase()
    .replace(/[_/–—-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function delimiterOf(header: string): string {
  const tabs = header.split("\t").length - 1;
  const semicolons = header.split(";").length - 1;
  if (tabs && tabs >= semicolons) return "\t";
  if (semicolons) return ";";
  if (header.includes(",")) return ",";
  return ";";
}

function splitLine(line: string, delimiter: string): string[] {
  return line.split(delimiter).map((cell) => cell.trim().replace(/^"|"$/g, ""));
}

export function contentHasPaidLines(content: string, paidColumn?: string): boolean {
  const text = content.replace(/^\uFEFF/, "");
  const lines = text.split(/\r?\n/).filter((line) => line.trim() !== "");
  if (lines.length < 2) return false;
  const delimiter = delimiterOf(lines[0] ?? "");
  const headers = splitLine(lines[0] ?? "", delimiter);
  const mapped = paidColumn?.trim() ?? "";
  let index = mapped ? headers.indexOf(mapped) : -1;
  if (index < 0) {
    index = headers.findIndex((header) => PAID_HEADERS.has(normalize(header)));
  }
  if (index < 0) return false;
  return lines.slice(1).some((line) => PAID_YES.has(normalize(splitLine(line, delimiter)[index] ?? "")));
}
