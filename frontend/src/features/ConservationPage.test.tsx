import { act, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import ConservationPage from "./ConservationPage";

const HASH = "a".repeat(64);
const BACKUP_HASH = "b".repeat(64);

const documentRow = {
  id: 4,
  original_name: "quittance.pdf",
  created_at: "2026-03-05T10:00:00Z",
  media_type: "application/pdf",
  media_label: "PDF",
  size: 2048,
  sha256: HASH,
  entry: {
    entry_number: "2026-000012",
    accounting_date: "2026-03-05",
    piece_reference: "LOY-2026-03",
    piece_date: "2026-03-05",
    label: "Loyer mars",
    status: "VALIDATED",
    year: 2026,
  },
};

const backupRow = {
  filename: "sololmnp-1.zip",
  created_at: "2026-03-06T08:30:00Z",
  size: 4096,
  application_version: "1.0.0",
  schema_revision: "0010_carry_events",
  sha256: BACKUP_HASH,
  integrity: {
    status: "unchecked" as const,
    checked_at: null,
    message: "Aucun contrôle enregistré.",
  },
};

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function deferred() {
  let resolve!: (value: Response) => void;
  const promise = new Promise<Response>((finish) => { resolve = finish; });
  return { promise, resolve };
}

function renderPage() {
  return render(<MemoryRouter><ConservationPage /></MemoryRouter>);
}

afterEach(() => vi.restoreAllMocks());

test("asks for a supported document before upload", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    if (url.endsWith("/documents")) return json({ documents: [] });
    if (url.endsWith("/backups")) return json({ backups: [] });
    throw new Error(url);
  });
  renderPage();
  expect(screen.getByRole("heading", { name: "Justificatifs et sauvegarde" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Déposer le justificatif" }));
  expect(screen.getByRole("alert")).toHaveTextContent("Choisissez un PDF, un JPEG ou un PNG.");
  expect(await screen.findByText("Aucun justificatif déposé.")).toBeInTheDocument();
});

test("shows loading then an empty inventory, and an error is not an empty list", async () => {
  const pending = deferred();
  let documentsCalls = 0;
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    if (url.endsWith("/documents")) {
      documentsCalls += 1;
      if (documentsCalls === 1) return pending.promise;
      return json({ documents: [] });
    }
    if (url.endsWith("/backups")) return json({ backups: [] });
    throw new Error(url);
  });
  renderPage();
  expect(screen.getByText("Chargement des justificatifs…")).toBeInTheDocument();
  expect(document.querySelector("section")).toHaveAttribute("data-screen-phase", "loading");
  expect(screen.queryByText("Aucun justificatif déposé.")).not.toBeInTheDocument();
  await act(async () => {
    pending.resolve(json(
      { detail: { code: "DATABASE_UNAVAILABLE", message: "Base indisponible." } },
      503,
    ));
  });
  expect(await screen.findByRole("alert")).toHaveTextContent("Base indisponible.");
  expect(screen.queryByText("Aucun justificatif déposé.")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Réessayer" }));
  expect(await screen.findByText("Aucun justificatif déposé.")).toBeInTheDocument();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  expect(document.querySelector("section")).toHaveAttribute("data-screen-phase", "loaded");
});

test("lists a justificatif and links it from the entry picker", async () => {
  const unlinked = { ...documentRow, entry: null };
  const calls: { url: string; method: string; body: string | null }[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    const body = typeof init?.body === "string" ? init.body : null;
    calls.push({ url, method, body });
    if (url.endsWith("/documents") && method === "GET") return json({ documents: [unlinked] });
    if (url.endsWith("/backups") && method === "GET") return json({ backups: [] });
    if (url.includes("/entries?")) {
      return json({ entries: [documentRow.entry] });
    }
    if (url.endsWith("/documents/4/link") && method === "POST") {
      return json({ ...documentRow });
    }
    throw new Error(`${method} ${url}`);
  });
  renderPage();
  expect(await screen.findByText("quittance.pdf")).toBeInTheDocument();
  expect(screen.getByRole("cell", { name: "PDF" })).toBeInTheDocument();
  expect(screen.getByText(/octets/)).toHaveTextContent(/2.048 octets/);
  expect(screen.getByText(HASH)).toBeInTheDocument();
  expect(screen.getByText("Aucune")).toBeInTheDocument();
  expect(screen.getByText("05/03/2026 10:00")).toBeInTheDocument();
  expect(screen.queryByLabelText(/identifiant interne/i)).not.toBeInTheDocument();
  expect(screen.queryByRole("spinbutton")).not.toBeInTheDocument();

  fireEvent.change(screen.getByLabelText("Numéro d’écriture"), { target: { value: "2026-000012" } });
  fireEvent.change(screen.getByLabelText("Date de l’écriture"), { target: { value: "2026-03-05" } });
  fireEvent.change(screen.getByLabelText("Pièce"), { target: { value: "LOY" } });
  fireEvent.click(screen.getByRole("button", { name: "Rechercher une écriture" }));
  const choice = await screen.findByRole("radio", { name: /2026-000012/ });
  fireEvent.click(choice);
  fireEvent.click(screen.getByRole("button", { name: "Lier cette écriture" }));
  expect(await screen.findByRole("status")).toHaveTextContent("LOY-2026-03");

  const search = calls.find((call) => call.url.includes("/entries?"));
  expect(search?.url).toContain("number=2026-000012");
  expect(search?.url).toContain("entry_date=2026-03-05");
  expect(search?.url).toContain("piece=LOY");
  const link = calls.find((call) => call.url.endsWith("/documents/4/link"));
  expect(JSON.parse(link?.body ?? "{}")).toEqual({
    entry_number: "2026-000012",
    accounting_date: "2026-03-05",
    piece_reference: "LOY-2026-03",
  });
});

test("previews a known backup and restores only after RESTAURER", async () => {
  const calls: { url: string; method: string; body: string | null }[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    const body = typeof init?.body === "string" ? init.body : null;
    calls.push({ url, method, body });
    if (url.endsWith("/documents")) return json({ documents: [] });
    if (url.endsWith("/backups")) return json({ backups: [backupRow] });
    if (url.includes("/backups/preview")) {
      return json({
        filename: backupRow.filename,
        backup_date: backupRow.created_at,
        current: { entries: 14, years: 1 },
        backup: { entries: 12, years: 1 },
      });
    }
    if (url.endsWith("/backups/verify")) {
      return json({
        ...backupRow,
        integrity: { status: "ok", checked_at: "2026-03-06T09:00:00Z", message: "Contrôle d’intégrité réussi." },
      });
    }
    if (url.endsWith("/backup/restore")) {
      return json({
        restored_from: backupRow.filename,
        pre_restore_backup: "sololmnp-2.zip",
        backup_date: backupRow.created_at,
        entries: 12,
        years: 1,
      });
    }
    throw new Error(`${method} ${url}`);
  });
  renderPage();
  expect(await screen.findByText(BACKUP_HASH)).toBeInTheDocument();
  expect(screen.getByText("1.0.0 · schéma 0010_carry_events")).toBeInTheDocument();
  expect(screen.getByText("Aucun contrôle enregistré.")).toBeInTheDocument();
  const restore = screen.getByRole("button", { name: "Restaurer la sauvegarde" });
  expect(restore).toBeDisabled();
  expect(screen.getByText(/exactement RESTAURER/)).toBeInTheDocument();

  fireEvent.click(screen.getByRole("radio", { name: "Choisir la sauvegarde du 06/03/2026 08:30" }));
  expect(await screen.findByText("14 → 12")).toBeInTheDocument();
  expect(screen.getByText("1 → 1")).toBeInTheDocument();
  expect(screen.getAllByText("06/03/2026 08:30").length).toBeGreaterThan(0);
  expect(restore).toBeDisabled();
  fireEvent.change(screen.getByLabelText("Confirmation — saisir RESTAURER"), {
    target: { value: "RESTAURER" },
  });
  expect(restore).toBeEnabled();
  fireEvent.click(restore);
  expect(await screen.findByRole("status")).toHaveTextContent("sololmnp-2.zip");
  const posted = calls.find((call) => call.url.endsWith("/backup/restore"));
  expect(JSON.parse(posted?.body ?? "{}")).toEqual({
    filename: "sololmnp-1.zip",
    confirmation: "RESTAURER",
  });

  fireEvent.click(screen.getByRole("button", { name: "Contrôler la sauvegarde du 06/03/2026 08:30" }));
  expect(await screen.findByRole("status")).toHaveTextContent(/Contrôle d.intégrité réussi/);
  expect(calls.some((call) => call.url.endsWith("/backups/verify") && call.method === "POST")).toBe(true);
});
