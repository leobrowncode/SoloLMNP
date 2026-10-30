import { readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { ERROR_HELP } from "../api/errors";
import { GLOSSARY, GLOSSARY_IDS, isGlossaryId, type GlossaryId } from "./glossary";

function moduleDir(): string {
  const url = import.meta.url.startsWith("file:") ? import.meta.url : `file://${import.meta.url}`;
  return dirname(fileURLToPath(url));
}

const HERE = moduleDir();
const SRC = join(HERE, "..");
const ROOT = join(HERE, "../../..");

const REQUIRED: GlossaryId[] = [
  "extourne",
  "a-nouveaux",
  "centralisation",
  "vnc",
  "efi",
  "fec",
  "compte-164",
  "compte-681",
  "amortissement",
  "liasse",
];

const BANNED = [/déclarable/i, /prête à recopier/i, /télétransmis/i, /vous pouvez déclarer/i];

function walk(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) return walk(path);
    return path.endsWith(".tsx") && !path.endsWith(".test.tsx") ? [path] : [];
  });
}

function block(source: string, start: string, end: string): string {
  const from = source.indexOf(start);
  const to = source.indexOf(end, from);
  return source.slice(from, to);
}

function pairs(source: string): Map<string, string> {
  const found = new Map<string, string>();
  for (const match of source.matchAll(/"?([A-Z][A-Z0-9_]+)"?\s*:\s*"([a-z0-9-]+)"/g)) {
    const code = match[1];
    const id = match[2];
    if (code && id) found.set(code, id);
  }
  return found;
}

describe("glossary completeness", () => {
  it("defines every complex term from the accounting vocabulary", () => {
    for (const id of REQUIRED) expect(GLOSSARY_IDS).toContain(id);
  });

  it("gives each entry a label and the four action-oriented parts", () => {
    const labels = new Set<string>();
    for (const id of GLOSSARY_IDS) {
      const entry = GLOSSARY[id];
      expect(entry.label.trim().length).toBeGreaterThan(1);
      expect(labels.has(entry.label)).toBe(false);
      labels.add(entry.label);
      for (const key of ["what", "why", "example", "mistake"] as const) {
        expect(entry[key].trim().length).toBeGreaterThan(40);
      }
    }
  });

  it("never calls a research vintage declarable", () => {
    for (const id of GLOSSARY_IDS) {
      const text = Object.values(GLOSSARY[id]).join("\n");
      for (const pattern of BANNED) expect(text).not.toMatch(pattern);
    }
    for (const id of ["liasse", "efi", "fec", "millesime"] as const) {
      const text = Object.values(GLOSSARY[id]).join("\n");
      expect(text.toLowerCase()).toContain("recherche");
    }
    expect(GLOSSARY.liasse.what).toContain("n’envoie rien");
    expect(GLOSSARY.efi.what).toContain("n’envoie rien");
  });

  it("stays consistent with the tutorial", () => {
    const tutorial = readFileSync(join(ROOT, "docs/TUTORIAL.md"), "utf8");
    expect(tutorial).toContain("ne reconstitue pas l’historique");
    expect(GLOSSARY["a-nouveaux"].what).toContain("ne reconstitue pas l’historique");
    expect(tutorial).toContain("ne clôture pas l’exercice");
    expect(GLOSSARY.centralisation.what).toContain("ne clôture pas l’exercice");
    expect(tutorial).toContain("ce n’est pas un barème légal");
    expect(GLOSSARY.amortissement.what).toContain("ce n’est pas un barème légal");
    expect(tutorial).toContain("15 000 €");
    expect(GLOSSARY["compte-164"].example).toContain("15 000 €");
    expect(tutorial).toContain("deux emprunts");
    expect(GLOSSARY["compte-164"].example).toContain("deux emprunts");
    expect(tutorial).toContain("pastilles **?**");
    expect(tutorial).toContain("ce que c’est");
    expect(tutorial).toContain("pourquoi c’est demandé");
    expect(tutorial).toContain("un exemple");
    expect(tutorial).toContain("l’erreur fréquente");
    expect(GLOSSARY.plafond.what).toContain("ne peut pas dépasser");
    expect(GLOSSARY.deficit.what).toContain("10");
    expect(`${GLOSSARY.fec.what} ${GLOSSARY.fec.why}`).toContain("SIREN");
  });

  it("is rendered on a screen for every entry", () => {
    const screens = walk(SRC).map((path) => readFileSync(path, "utf8")).join("\n");
    const missing = GLOSSARY_IDS.filter((id) => (
      !screens.includes(`id="${id}"`) && !screens.includes(`help="${id}"`)
    ));
    expect(missing).toEqual([]);
  });
});

describe("error help links", () => {
  it("matches the backend help ids and only uses glossary entries", () => {
    const frontend = block(
      readFileSync(join(HERE, "../api/errors.ts"), "utf8"),
      "export const ERROR_HELP",
      "export function knownHelp",
    );
    const backend = block(
      readFileSync(join(ROOT, "backend/app/core/api_errors.py"), "utf8"),
      "HELP_IDS: dict[str, str] = {",
      "RESOLUTION_ACTIONS",
    );
    expect(pairs(frontend)).toEqual(pairs(backend));
    for (const id of Object.values(ERROR_HELP)) expect(isGlossaryId(id)).toBe(true);
  });
});
