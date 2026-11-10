export function eurosDepuisCentimes(centimes: number): string {
  const signe = centimes < 0 ? "-" : "";
  const abs = Math.abs(centimes);
  const entiers = Math.floor(abs / 100);
  const reste = abs % 100;
  return `${signe}${entiers.toLocaleString("fr-FR")},${reste.toString().padStart(2, "0")}`;
}

export function centimesDepuisEuros(texte: string): number {
  const normalise = texte.trim().replace(/\s/g, "").replace(",", ".");
  if (!normalise) return 0;
  const valeur = Number(normalise);
  if (!Number.isFinite(valeur)) return 0;
  return Math.round(valeur * 100);
}
