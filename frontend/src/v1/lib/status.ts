const LIBELLES: Record<string, string> = {
  brouillon: "Brouillon",
  verifie: "Vérifié par l'utilisateur",
  declare: "Déclaré",
};

export function libelleEtat(code: string | undefined): string {
  if (!code) return "Brouillon";
  return LIBELLES[code] ?? String(code);
}
