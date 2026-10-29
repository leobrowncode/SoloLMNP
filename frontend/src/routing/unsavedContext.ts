import { createContext } from "react";

export type UnsavedContextValue = {
  register: (id: symbol) => () => void;
};

export const UnsavedContext = createContext<UnsavedContextValue | null>(null);
