import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "../components/ui/button";
import { Card, CardTitle } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { chargerDossier, construire, enregistrerDossier, type EfiLigne } from "../lib/api";
import { useDossierSession } from "../context/DossierContext";
import { libelleEtat } from "../lib/status";

function cleCase(ligne: EfiLigne): string {
  return `${ligne.formulaire}/${ligne.case}`;
}

export default function SortiesScreen() {
  const { session, setSession, setCalcul } = useDossierSession();
  const [ouvert, setOuvert] = useState<string | null>(null);
  const [dateDepot, setDateDepot] = useState("");
  const [accuse, setAccuse] = useState("");
  const [copie, setCopie] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const sorties = session?.calcul?.sorties;
  const lignes = sorties?.efi?.lignes ?? [];
  const traces = sorties?.traces ?? {};
  const archive = sorties;

  const effectif = session?.calcul?.etat?.effectif ?? String(session?.dossier?.statut ?? "brouillon");

  const lignesParEcran = useMemo(() => {
    const map = new Map<string, EfiLigne[]>();
    for (const ligne of lignes) {
      const bloc = map.get(ligne.ecran) ?? [];
      bloc.push(ligne);
      map.set(ligne.ecran, bloc);
    }
    return map;
  }, [lignes]);

  async function copierLigne(ligne: EfiLigne) {
    const texte = `${ligne.case}\t${ligne.montant ?? ""}`;
    await navigator.clipboard.writeText(texte);
    setCopie(`${ligne.ecran} ${ligne.case}`);
    window.setTimeout(() => setCopie(null), 2000);
  }

  async function enregistrerDepot() {
    if (!session?.calcul) return;
    setMessage(null);
    if (!dateDepot || !accuse.trim()) {
      setMessage("Date de dépôt et numéro d'accusé EFI requis pour l'état Déclaré.");
      return;
    }
    const dossier = {
      ...session.dossier,
      statut: "declare",
      relu_notice: true,
      date_depot: dateDepot,
      numero_accuse: accuse.trim(),
      empreinte_figee: session.calcul.empreinte,
    };
    try {
      await enregistrerDossier(session.chemin, dossier, session.mouvements);
      const relu = await chargerDossier(session.chemin);
      const calcul = await construire(session.chemin);
      setCalcul(calcul);
      setSession({
        ...session,
        dossier: relu.dossier,
        mouvements: relu.mouvements,
        grille: relu.grille,
        calcul,
      });
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Enregistrement refusé.");
    }
  }

  if (!session?.calcul?.sorties) {
    return (
      <Card>
        <CardTitle>5. Sorties</CardTitle>
        <p className="mt-2 text-sm">Calculez et validez la revue pour produire la feuille EFI.</p>
        <Link className="mt-4 inline-flex text-sm text-[var(--color-primary)] underline" to="/v1/revue">
          Aller à la revue
        </Link>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardTitle>5. Sorties et recopie EFI</CardTitle>
        <p className="mt-2 text-sm text-[var(--color-muted-foreground)]">
          État : <strong>{libelleEtat(String(effectif))}</strong>. Feuille dans l&apos;ordre des écrans EFI. Aucune
          télétransmission.
        </p>
        {archive ? (
          <p className="mt-2 text-xs text-[var(--color-muted-foreground)]">
            Archive {archive.archive_nom} · empreinte {archive.archive_sha256.slice(0, 16)}…
          </p>
        ) : null}
      </Card>

      {[...lignesParEcran.entries()].map(([ecran, bloc]) => (
        <Card key={ecran}>
          <CardTitle>{ecran}</CardTitle>
          <ul className="mt-4 space-y-2">
            {bloc.map((ligne) => {
              const id = cleCase(ligne);
              const trace = traces[id];
              const visible = ouvert === id;
              return (
                <li key={id} className="rounded-lg border border-[var(--color-border)] p-3 text-sm">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <span className="font-mono font-medium">{ligne.case}</span>
                      <span className="ml-2">{ligne.montant ?? "néant"}</span>
                    </div>
                    <div className="flex gap-2">
                      <Button type="button" size="sm" variant="outline" onClick={() => void copierLigne(ligne)}>
                        Copier
                      </Button>
                      <Button type="button" size="sm" variant="ghost" onClick={() => setOuvert(visible ? null : id)}>
                        Sources
                      </Button>
                    </div>
                  </div>
                  {visible ? (
                    <div className="mt-2 text-xs text-[var(--color-muted-foreground)]">
                      <p>Comptes : {(trace?.comptes ?? ligne.comptes).join(", ") || "aucun"}</p>
                      <p>Écritures : {(trace?.ecritures ?? ligne.ecritures).join(", ") || "aucune"}</p>
                      <p>Origine : {trace?.origine ?? ligne.origine}</p>
                    </div>
                  ) : null}
                </li>
              );
            })}
          </ul>
        </Card>
      ))}

      <Card>
        <CardTitle>Dépôt EFI (état Déclaré)</CardTitle>
        <p className="mt-2 text-sm text-[var(--color-muted-foreground)]">
          Après recopie sur impots.gouv.fr, enregistrez la date et le numéro d&apos;accusé pour figer les sorties.
        </p>
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <div>
            <Label htmlFor="date_depot">Date de dépôt</Label>
            <Input id="date_depot" type="date" value={dateDepot} onChange={(event) => setDateDepot(event.target.value)} />
          </div>
          <div>
            <Label htmlFor="accuse">Numéro d&apos;accusé</Label>
            <Input id="accuse" value={accuse} onChange={(event) => setAccuse(event.target.value)} />
          </div>
        </div>
        <Button type="button" className="mt-4" onClick={() => void enregistrerDepot()}>
          Marquer comme Déclaré
        </Button>
        {message ? <p className="mt-4 text-sm text-[var(--color-destructive)]">{message}</p> : null}
        {copie ? <p className="mt-2 text-sm text-[var(--color-primary)]">Copié : {copie}</p> : null}
      </Card>
    </div>
  );
}
