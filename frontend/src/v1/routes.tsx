import { Navigate, type RouteObject } from "react-router-dom";
import { DossierProvider } from "./context/DossierContext";
import V1Shell from "./layout/V1Shell";
import AnneeScreen from "./screens/AnneeScreen";
import BienScreen from "./screens/BienScreen";
import DossierScreen from "./screens/DossierScreen";
import RevueScreen from "./screens/RevueScreen";
import SortiesScreen from "./screens/SortiesScreen";

export const v1Routes: RouteObject = {
  path: "/v1",
  element: (
    <DossierProvider>
      <V1Shell />
    </DossierProvider>
  ),
  children: [
    { index: true, element: <Navigate to="dossier" replace /> },
    { path: "dossier", element: <DossierScreen /> },
    { path: "bien", element: <BienScreen /> },
    { path: "annee", element: <AnneeScreen /> },
    { path: "revue", element: <RevueScreen /> },
    { path: "sorties", element: <SortiesScreen /> },
  ],
};
