import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider } from "react-router-dom";
import { router } from "./routing/router";
import "./tokens.css";
import "./style.css";

const root = document.getElementById("root");
if (!root) throw new Error("Le point de montage de l’application est absent.");
createRoot(root).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>,
);
