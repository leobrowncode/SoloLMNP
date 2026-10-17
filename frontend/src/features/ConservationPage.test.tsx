import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import ConservationPage from "./ConservationPage";

test("asks for a supported document before upload", () => {
  render(<ConservationPage />);
  expect(screen.getByRole("heading", { name: "Justificatifs et sauvegarde" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Déposer le justificatif" }));
  expect(screen.getByRole("alert")).toHaveTextContent("Choisissez un PDF, un JPEG ou un PNG.");
});
