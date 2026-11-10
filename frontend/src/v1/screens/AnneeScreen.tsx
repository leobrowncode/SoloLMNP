import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "../components/ui/button";
import { Card, CardTitle } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { chargerCategories, chargerDossier, construire, enregistrerDossier } from "../lib/api";
import { useDossierSession } from "../context/DossierContext";
import { centimesDepuisEuros, eurosDepuisCentimes } from "../lib/money";
import { ligneDepuisCategorie, parserCsvMouvements, totalParCompte } from "../lib/mouvements";

type Categorie = { id: string; libelle: string; compte: string; sens: string };

export default function AnneeScreen() {
  const navigate = useNavigate();
  const { session, setSession, setCalcul } = useDossierSession();
  const [categories, setCategories] = useState<Categorie[]>([]);
  const [montants, setMontants] = useState<Record<string, string>>({});
  const [message, setMessage] = useState<string | null>(null);

  const exercice = useMemo(() => {
    const exercices = session?.dossier?.exercices;
    if (!Array.isArray(exercices) || !exercices.length) return null;
    const premier = exercices[0] as Record<string, string>;
    return { debut: String(premier.debut ?? ""), fin: String(premier.fin ?? "") };
  }, [session?.dossier]);

  useEffect(() => {
    void chargerCategories().then((rep) => setCategories(rep.categories));
  }, []);

  useEffect(() => {
    if (!session?.mouvements?.length || !categories.length) return;
    const suivant: Record<string, string> = {};
    for (const categorie of categories) {
      const total = totalParCompte(session.mouvements, categorie.compte);
      if (total > 0) suivant[categorie.id] = eurosDepuisCentimes(total);
    }
    setMontants(suivant);
  }, [categories, session?.mouvements]);

  if (!session || !exercice) {
    return (
      <Card>
        <CardTitle>3. Année</CardTitle>
        <p className="mt-2 text-sm">Renseignez d&apos;abord le dossier et le bien.</p>
        <Link className="mt-4 inline-flex text-sm text-[var(--color-primary)] underline" to="/v1/dossier">
          Aller au dossier
        </Link>
      </Card>
    );
  }

  function remplacerMontant(id: string, valeur: string) {
    setMontants((courant) => ({ ...courant, [id]: valeur }));
  }

  function fusionnerCategories(): void {
    if (!session || !exercice) return;
    const horsCategories = session.mouvements.filter((ligne) => !ligne.piece.startsWith("CAT-"));
    const generes = categories
      .map((categorie) =>
        ligneDepuisCategorie({
          categorieId: categorie.id,
          libelle: categorie.libelle,
          compte: categorie.compte,
          sens: categorie.sens,
          montantCentimes: centimesDepuisEuros(montants[categorie.id] ?? "0"),
          date: exercice.fin,
        }),
      )
      .filter((ligne): ligne is NonNullable<typeof ligne> => ligne !== null);
    setSession({ ...session, mouvements: [...horsCategories, ...generes] });
  }

  async function appliquerCsv(fichier: File) {
    const texte = await fichier.text();
    const importes = parserCsvMouvements(texte);
    if (!importes.length) {
      setMessage("CSV illisible. Colonnes date, compte, debit_centimes, credit_centimes requises.");
      return;
    }
    if (!session) return;
    setSession({ ...session, mouvements: importes });
    setMessage(`${importes.length} lignes importées.`);
  }

  async function enregistrer() {
    if (!session || !exercice) return;
    setMessage(null);
    const horsCategories = session.mouvements.filter((ligne) => !ligne.piece.startsWith("CAT-"));
    const generes = categories
      .map((categorie) =>
        ligneDepuisCategorie({
          categorieId: categorie.id,
          libelle: categorie.libelle,
          compte: categorie.compte,
          sens: categorie.sens,
          montantCentimes: centimesDepuisEuros(montants[categorie.id] ?? "0"),
          date: exercice.fin,
        }),
      )
      .filter((ligne): ligne is NonNullable<typeof ligne> => ligne !== null);
    const mouvements = [...horsCategories, ...generes];
    try {
      await enregistrerDossier(session.chemin, session.dossier, mouvements);
      const relu = await chargerDossier(session.chemin);
      const calcul = await construire(session.chemin);
      if (calcul.erreur) {
        setMessage(calcul.erreur);
        return;
      }
      setCalcul(calcul);
      setSession({
        ...session,
        dossier: relu.dossier,
        mouvements: relu.mouvements,
        grille: relu.grille,
        calcul,
      });
      navigate("/v1/revue");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Enregistrement refusé.");
    }
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardTitle>3. Année {session.dossier.millesime as string}</CardTitle>
        <p className="mt-2 text-sm text-[var(--color-muted-foreground)]">
          Exercice du {exercice.debut} au {exercice.fin}. Saisissez les montants annuels par catégorie ou importez un CSV
          au format du noyau.
        </p>
        <div className="mt-4">
          <Label htmlFor="csv">Import CSV</Label>
          <Input
            id="csv"
            type="file"
            accept=".csv,text/csv"
            onChange={(event) => {
              const fichier = event.target.files?.[0];
              if (fichier) void appliquerCsv(fichier);
            }}
          />
        </div>
      </Card>

      <Card>
        <CardTitle>Grille de complétude des charges</CardTitle>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-[var(--color-border)]">
                <th className="py-2 pr-3">Catégorie</th>
                <th className="py-2 pr-3">Compte</th>
                <th className="py-2 pr-3">Montant annuel (€)</th>
                <th className="py-2 pr-3">État</th>
              </tr>
            </thead>
            <tbody>
              {categories.map((categorie) => {
                const saisi = centimesDepuisEuros(montants[categorie.id] ?? "0") > 0;
                return (
                  <tr key={categorie.id} className="border-b border-[var(--color-border)]">
                    <td className="py-2 pr-3">{categorie.libelle}</td>
                    <td className="py-2 pr-3 font-mono text-xs">{categorie.compte}</td>
                    <td className="py-2 pr-3">
                      <Input
                        aria-label={`Montant ${categorie.libelle}`}
                        inputMode="decimal"
                        value={montants[categorie.id] ?? ""}
                        onChange={(event) => remplacerMontant(categorie.id, event.target.value)}
                        onBlur={fusionnerCategories}
                      />
                    </td>
                    <td className="py-2 pr-3">{saisi ? "Renseigné" : "À compléter"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>

      <Card>
        <CardTitle>Écritures de l&apos;exercice ({session.mouvements.length})</CardTitle>
        <div className="mt-4 max-h-80 overflow-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-[var(--color-border)]">
                <th className="py-2 pr-2">Date</th>
                <th className="py-2 pr-2">Pièce</th>
                <th className="py-2 pr-2">Libellé</th>
                <th className="py-2 pr-2">Compte</th>
                <th className="py-2 pr-2">Débit</th>
                <th className="py-2 pr-2">Crédit</th>
              </tr>
            </thead>
            <tbody>
              {session.mouvements.map((ligne) => (
                <tr key={`${ligne.piece}-${ligne.date}-${ligne.compte}`} className="border-b border-[var(--color-border)]">
                  <td className="py-1 pr-2">{ligne.date}</td>
                  <td className="py-1 pr-2">{ligne.piece}</td>
                  <td className="py-1 pr-2">{ligne.libelle}</td>
                  <td className="py-1 pr-2 font-mono">{ligne.compte}</td>
                  <td className="py-1 pr-2">{eurosDepuisCentimes(Number(ligne.debit_centimes) || 0)}</td>
                  <td className="py-1 pr-2">{eurosDepuisCentimes(Number(ligne.credit_centimes) || 0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="mt-6 flex justify-between">
          <Button type="button" variant="outline" onClick={() => navigate("/v1/bien")}>
            Retour
          </Button>
          <Button type="button" onClick={() => void enregistrer()}>
            Enregistrer et passer à la revue
          </Button>
        </div>
        {message ? <p className="mt-4 text-sm text-[var(--color-destructive)]">{message}</p> : null}
      </Card>
    </div>
  );
}
