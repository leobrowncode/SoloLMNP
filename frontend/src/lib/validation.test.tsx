import type { FormEvent } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import FrenchFileInput from "./FrenchFileInput";
import FrenchForm from "./FrenchForm";
import { DATE_HINT } from "./format";

describe("French validation", () => {
  it("blocks an empty required field with a French message and no native submit", async () => {
    const onSubmit = vi.fn((event: FormEvent<HTMLFormElement>) => event.preventDefault());
    render(
      <FrenchForm onSubmit={onSubmit}>
        <label>
          Libellé
          <input name="label" required />
        </label>
        <button type="submit">Enregistrer</button>
      </FrenchForm>,
    );
    const form = screen.getByRole("button", { name: "Enregistrer" }).closest("form");
    expect(form).toHaveAttribute("novalidate");
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer" }));
    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent("Ce champ est obligatoire.");
    await userEvent.type(screen.getByLabelText("Libellé"), "OK");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer" }));
    expect(onSubmit).toHaveBeenCalledOnce();
  });

  it("explains a money field and a year pattern in French", async () => {
    render(
      <FrenchForm onSubmit={(event) => event.preventDefault()}>
        <label>
          Montant
          <input name="amount" data-money="true" defaultValue="abc" />
        </label>
        <label>
          Millésime
          <input name="vintage" required pattern="[0-9]{4}" defaultValue="26" />
        </label>
        <button type="submit">Enregistrer</button>
      </FrenchForm>,
    );
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer" }));
    expect(screen.getByText("Indiquez un montant en euros, par exemple 1 234,56.")).toBeInTheDocument();
    expect(screen.getByText("Indiquez une année sur 4 chiffres.")).toBeInTheDocument();
  });

  it("asks for a file in French and hides the native picker label", () => {
    render(<FrenchFileInput label="Justificatif PDF, JPEG ou PNG" />);
    expect(screen.getByText("Choisir un fichier")).toBeInTheDocument();
    expect(screen.getByText("Aucun fichier choisi")).toBeInTheDocument();
    const input = document.querySelector("input[type=file]");
    expect(input).toHaveClass("file-picker-native");
    expect(input).not.toHaveAttribute("value", "Choose File");
  });

  it("keeps an explicit French hint on a date input", () => {
    render(
      <label>
        Date comptable
        <input type="date" lang="fr" />
        <span className="field-hint">{DATE_HINT}</span>
      </label>,
    );
    expect(document.querySelector("input[type=date]")).toHaveAttribute("lang", "fr");
    expect(screen.getByText("Date comptable")).toBeInTheDocument();
    expect(screen.getByText(DATE_HINT)).toBeInTheDocument();
  });
});
