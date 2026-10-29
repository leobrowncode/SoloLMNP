import { Navigate, createBrowserRouter, createMemoryRouter, type RouteObject } from "react-router-dom";
import AppShell from "../AppShell";
import LedgerPage from "../features/LedgerPage";
import OperationsPage from "../features/OperationsPage";
import AssetsPage from "../features/AssetsPage";
import StatementsPage from "../features/StatementsPage";
import FiscalPage from "../features/FiscalPage";
import ConservationPage from "../features/ConservationPage";
import { DEFAULT_LEDGER_TAB, DEFAULT_OPERATIONS_TAB, ledgerPath, operationsPath, ROUTES } from "./paths";

export const appRoutes: RouteObject[] = [
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: null },
      { path: "comptabilite", element: <Navigate to={ledgerPath(DEFAULT_LEDGER_TAB)} replace /> },
      { path: "comptabilite/:tab", element: <LedgerPage /> },
      { path: "operations", element: <Navigate to={operationsPath(DEFAULT_OPERATIONS_TAB)} replace /> },
      { path: "operations/:tab", element: <OperationsPage /> },
      { path: "immobilisations", element: <AssetsPage /> },
      { path: "etats-comptables", element: <StatementsPage /> },
      { path: "fiscalite", element: <FiscalPage /> },
      { path: "conservation", element: <ConservationPage /> },
      { path: "*", element: <Navigate to={ROUTES.home} replace /> },
    ],
  },
];

export const router = createBrowserRouter(appRoutes);

export function createTestRouter(initialEntries: string[], initialIndex = initialEntries.length - 1) {
  return createMemoryRouter(appRoutes, { initialEntries, initialIndex });
}
