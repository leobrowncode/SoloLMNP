export function siretValide(siret: string): boolean {
  const chiffres = siret.replace(/\s/g, "");
  if (chiffres.length !== 14 || !/^\d+$/.test(chiffres)) return false;
  let total = 0;
  let doubler = false;
  for (let index = chiffres.length - 1; index >= 0; index -= 1) {
    let valeur = Number(chiffres[index]);
    if (doubler) {
      valeur *= 2;
      if (valeur > 9) valeur -= 9;
    }
    total += valeur;
    doubler = !doubler;
  }
  return total % 10 === 0;
}
