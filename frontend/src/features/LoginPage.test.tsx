import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RouterProvider } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { restoreNeonToken, signInWithGoogle, signOutNeon } from "../api/neonAuth";
import { createTestRouter } from "../routing/router";

vi.mock("../api/neonAuth", async () => {
  const actual = await vi.importActual<typeof import("../api/neonAuth")>("../api/neonAuth");
  return {
    ...actual,
    signInWithGoogle: vi.fn(),
    restoreNeonToken: vi.fn(async () => null),
    signOutNeon: vi.fn(),
  };
});

describe("connexion", () => {
  beforeEach(() => {
    sessionStorage.clear();
    vi.stubEnv("VITE_AUTH_MODE", "test");
    vi.stubEnv("VITE_TEST_USER_EMAIL", "testeur@sololmnp.test");
    vi.stubEnv("VITE_TEST_USER_PASSWORD", "mot-de-passe-essai");
    vi.stubEnv("VITE_TEST_TOKEN", "jeton-essai");
  });

  it("renvoie vers la page demandée après une connexion d’essai", async () => {
    const user = userEvent.setup();
    render(<RouterProvider router={createTestRouter(["/comptabilite/journal"])} />);
    expect(await screen.findByRole("heading", { name: "Connexion" })).toBeInTheDocument();
    await user.type(screen.getByLabelText("Adresse e-mail"), "testeur@sololmnp.test");
    await user.type(screen.getByLabelText("Mot de passe"), "mot-de-passe-essai");
    await user.click(screen.getByRole("button", { name: "Se connecter" }));
    expect(await screen.findByRole("heading", { level: 1, name: "Comptabilité" })).toBeInTheDocument();
  });

  it("refuse un mot de passe d’essai incorrect", async () => {
    const user = userEvent.setup();
    render(<RouterProvider router={createTestRouter(["/connexion"])} />);
    await user.type(screen.getByLabelText("Adresse e-mail"), "testeur@sololmnp.test");
    await user.type(screen.getByLabelText("Mot de passe"), "mauvais-mot");
    await user.click(screen.getByRole("button", { name: "Se connecter" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Adresse ou mot de passe refusé.");
  });
});

describe("dossier local", () => {
  beforeEach(() => {
    sessionStorage.clear();
    vi.stubEnv("VITE_AUTH_MODE", "local");
    vi.stubEnv("VITE_NEON_AUTH_URL", "");
  });

  it("ouvre le dossier sans formulaire ni bouton Google", async () => {
    const user = userEvent.setup();
    render(<RouterProvider router={createTestRouter(["/connexion"])} />);
    expect(await screen.findByRole("heading", { name: "Dossier local" })).toBeInTheDocument();
    expect(screen.queryByLabelText("Adresse e-mail")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Continuer avec Google" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Ouvrir le dossier" }));
    expect(await screen.findByRole("heading", { level: 1, name: "Vue d’ensemble" })).toBeInTheDocument();
    expect(screen.getByText("Dossier local, sans compte Neon.")).toBeInTheDocument();
  });
});

describe("neon absent", () => {
  beforeEach(() => {
    sessionStorage.clear();
    vi.stubEnv("VITE_AUTH_MODE", "");
    vi.stubEnv("VITE_NEON_AUTH_URL", "");
  });

  it("explique où configurer Neon au lieu d’un formulaire inactif", async () => {
    render(<RouterProvider router={createTestRouter(["/connexion"])} />);
    expect(await screen.findByRole("heading", { name: "Authentification non configurée" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Documentation de déploiement" })).toHaveAttribute(
      "href",
      "https://github.com/leobrowncode/SoloLMNP/blob/main/docs/DEPLOYMENT.md",
    );
    expect(screen.getByRole("link", { name: "Instance hébergée" })).toHaveAttribute(
      "href",
      "https://sololmnp.vercel.app",
    );
    expect(screen.queryByLabelText("Adresse e-mail")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Continuer avec Google" })).not.toBeInTheDocument();
    expect(screen.getByText(/AUTH_MODE=local/)).toBeInTheDocument();
  });
});

describe("retour Google", () => {
  beforeEach(() => {
    sessionStorage.clear();
    vi.stubEnv("VITE_AUTH_MODE", "");
    vi.stubEnv("VITE_NEON_AUTH_URL", "https://auth.example.test/neondb/auth");
    vi.mocked(restoreNeonToken).mockReset();
    vi.mocked(restoreNeonToken).mockResolvedValue(null);
    vi.mocked(signInWithGoogle).mockReset();
    vi.mocked(signOutNeon).mockReset();
    vi.stubGlobal("fetch", vi.fn(async () => new Response("{}", {
      status: 200,
      headers: { "content-type": "application/json" },
    })));
  });

  it("entre dans l’application quand la session Google fournit un JWT", async () => {
    vi.mocked(restoreNeonToken).mockResolvedValue("header.jwt.value");
    render(<RouterProvider router={createTestRouter([
      "/connexion?neon_auth_session_verifier=abc&next=%2Fcomptabilite%2Fjournal",
    ])} />);
    expect(await screen.findByRole("heading", { level: 1, name: "Comptabilité" })).toBeInTheDocument();
    expect(sessionStorage.getItem("sololmnp.token")).toBe("header.jwt.value");
    expect(restoreNeonToken).toHaveBeenCalledWith(expect.stringContaining("neon_auth_session_verifier=abc"));
  });

  it("explique un retour Google refusé", async () => {
    render(<RouterProvider router={createTestRouter(["/connexion?error=access_denied"])} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("La connexion Google a été refusée.");
    expect(restoreNeonToken).not.toHaveBeenCalled();
  });

  it("renvoie une adresse non autorisée vers la connexion", async () => {
    vi.mocked(restoreNeonToken).mockResolvedValue("header.jwt.value");
    vi.stubGlobal("fetch", vi.fn(async () => new Response("{}", { status: 403 })));
    render(<RouterProvider router={createTestRouter(["/connexion?neon_auth_session_verifier=abc"])} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Cette adresse n’est pas autorisée.");
    expect(signOutNeon).toHaveBeenCalled();
    expect(sessionStorage.getItem("sololmnp.token")).toBeNull();
  });

  it("ouvre Google vers /connexion en conservant la page demandée", async () => {
    const user = userEvent.setup();
    render(<RouterProvider router={createTestRouter(["/connexion?next=%2Fcomptabilite%2Fjournal"])} />);
    await user.click(await screen.findByRole("button", { name: "Continuer avec Google" }));
    expect(signInWithGoogle).toHaveBeenCalledWith(
      `${window.location.origin}/connexion?next=%2Fcomptabilite%2Fjournal`,
    );
  });
});
