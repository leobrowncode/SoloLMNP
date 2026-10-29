import { render, type RenderOptions } from "@testing-library/react";
import { RouterProvider } from "react-router-dom";
import { createTestRouter } from "./router";

export function renderAt(path: string, options?: Omit<RenderOptions, "wrapper">) {
  const router = createTestRouter([path]);
  return render(<RouterProvider router={router} />, options);
}
