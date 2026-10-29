import { render, type RenderOptions } from "@testing-library/react";
import { createMemoryRouter, Outlet, RouterProvider } from "react-router-dom";
import type { ReactElement } from "react";
import { UnsavedChangesProvider } from "./unsaved";

export function renderWithRouter(
  element: ReactElement,
  path: string,
  childPath: string,
  options?: Omit<RenderOptions, "wrapper">,
) {
  const router = createMemoryRouter(
    [
      {
        path: "/",
        element: (
          <UnsavedChangesProvider>
            <Outlet />
          </UnsavedChangesProvider>
        ),
        children: [{ path: childPath.replace(/^\//, ""), element }],
      },
    ],
    { initialEntries: [path] },
  );
  return render(<RouterProvider router={router} />, options);
}
