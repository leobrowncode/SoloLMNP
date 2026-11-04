import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RouterProvider } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createTestRouter } from "../routing/router";

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
