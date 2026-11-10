import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "../components/ui/button";
import { Card, CardTitle } from "../components/ui/card";
import { Checkbox } from "../components/ui/checkbox";
import { chargerDossier, construire, enregistrerDossier } from "../lib/api";
import { useDossierSession } from "../context/dossierSession";
import { eurosDepuisCentimes } from "../lib/money";
import { libelleEtat } from "../lib/status";

export default function RevueScreen() {
  const navigate = useNavigate();
  const { session, setSession, setCalcul } = useDossierSession();
  const [relu, setRelu] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const millesime = String(session?.dossier?.millesime ?? "");
  const annee = session?.calcul?.annees?.[millesime] as Record<string, number> | undefined;

  useEffect(() => {
    queueMicrotask(() => setRelu(Boolean(session?.dossier?.relu_notice)));
  }, [session?.dossier?.relu_notice]);

  useEffect(() => {
    if (!session?.chemin || session.calcul) return;
    void construire(session.chemin).then((calcul) => {
      if (!calcul.erreur) setCalcul(calcul);
    });
  }, [session, setCalcul]);

  if (!session || !annee) {
    return (
      <Card>
        <CardTitle>4. Revue</CardTitle>
        <p className="mt-2 text-sm">Complétez l&apos;année pour calculer le résultat fiscal.</p>
        <Link className="mt-4 inline-flex text-sm text-[var(--color-primary)] underline" to="/v1/annee">
          Retour à l&apos;année
        </Link>
      </Card>
    );
  }

  async function valider() {
    if (!session) return;
    setMessage(null);
    const dossier = {
      ...session.dossier,
      relu_notice: relu,
      statut: relu ? "verifie" : "brouillon",
    };
    try {
      await enregistrerDossier(session.chemin, dossier, session.mouvements);
      const reluPayload = await chargerDossier(session.chemin);
      const calcul = await construire(session.chemin);
      if (calcul.erreur) {
        setMessage(calcul.erreur);
        return;
      }
      setCalcul(calcul);
      setSession({
        ...session,
        dossier: reluPayload.dossier,
        mouvements: reluPayload.mouvements,
        grille: reluPayload.grille,
        calcul,
      });
      navigate("/v1/sorties");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Enregistrement refusé.");
    }
  }

  const effectif = session.calcul?.etat?.effectif ?? "brouillon";

  return (
    <div className="space-y-6">
      <Card>
        <CardTitle>4. Revue fiscale {millesime}</CardTitle>
        <p className="mt-2 text-sm text-[var(--color-muted-foreground)]">
          État actuel : <strong>{libelleEtat(effectif)}</strong>. {session.calcul?.etat?.texte}
        </p>
        <dl className="mt-6 grid gap-3 sm:grid-cols-2">
          <div>
            <dt className="text-xs text-[var(--color-muted-foreground)]">Résultat comptable</dt>
            <dd className="text-lg font-semibold">{eurosDepuisCentimes(Number(annee.resultat_comptable))} €</dd>
          </div>
          <div>
            <dt className="text-xs text-[var(--color-muted-foreground)]">Résultat fiscal</dt>
            <dd className="text-lg font-semibold">{eurosDepuisCentimes(Number(annee.resultat_fiscal))} €</dd>
          </div>
          <div>
            <dt className="text-xs text-[var(--color-muted-foreground)]">Dotation (comptable)</dt>
            <dd>{eurosDepuisCentimes(Number(annee.dotation))} €</dd>
          </div>
          <div>
            <dt className="text-xs text-[var(--color-muted-foreground)]">Dotation déductible</dt>
            <dd>{eurosDepuisCentimes(Number(annee.dotation_deductible))} €</dd>
          </div>
          <div>
            <dt className="text-xs text-[var(--color-muted-foreground)]">Quote-part non déduite (39 C)</dt>
            <dd>{eurosDepuisCentimes(Number(annee.non_deduit))} €</dd>
          </div>
          <div>
            <dt className="text-xs text-[var(--color-muted-foreground)]">Déficit créé</dt>
            <dd>{eurosDepuisCentimes(Number(annee.deficit_cree))} €</dd>
          </div>
        </dl>
        {session.calcul?.sorties?.fec ? (
          <p className="mt-4 text-sm">
            FEC {session.calcul.sorties.fec.nom} :{" "}
            {session.calcul.sorties.fec.valide ? "contrôles internes verts" : "anomalies à corriger"}
          </p>
        ) : null}
      </Card>

      <Card>
        <CardTitle>Confirmation utilisateur</CardTitle>
        <label className="mt-4 flex items-start gap-3 text-sm">
          <Checkbox checked={relu} onChange={(event) => setRelu(event.target.checked)} aria-label="Notice relue" />
          <span>
            J&apos;ai relu les cases du millésime {millesime} contre la notice officielle archivée dans le dépôt.
          </span>
        </label>
        <p className="mt-2 text-xs text-[var(--color-muted-foreground)]">
          Sans cette case, l&apos;état reste Brouillon même si le calcul est complet.
        </p>
        <div className="mt-6 flex justify-between">
          <Button type="button" variant="outline" onClick={() => navigate("/v1/annee")}>
            Retour
          </Button>
          <Button type="button" onClick={() => void valider()}>
            Valider et ouvrir les sorties
          </Button>
        </div>
        {message ? <p className="mt-4 text-sm text-[var(--color-destructive)]">{message}</p> : null}
      </Card>
    </div>
  );
}
