import { zodResolver } from "@hookform/resolvers/zod";
import { useCallback, useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { useNavigate } from "react-router-dom";
import { z } from "zod";
import { Button } from "../components/ui/button";
import { Card, CardTitle } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import {
  chargerDossier,
  chargerModele,
  chargerModeles,
  construire,
  creerDepuisModele,
  enregistrerDossier,
  type DossierPayload,
} from "../lib/api";
import { useDossierSession } from "../context/dossierSession";
import { siretValide } from "../lib/siret";

const schema = z.object({
  nom: z.string().min(2, "Nom du dossier requis"),
  siret: z.string().refine(siretValide, "SIRET invalide (14 chiffres, clé de Luhn)"),
  debut_activite: z.string().min(1, "Date requise"),
  millesime: z.string().regex(/^\d{4}$/, "Millésime sur quatre chiffres"),
});

type FormValues = z.infer<typeof schema>;

export default function DossierScreen() {
  const navigate = useNavigate();
  const { session, setSession, setCalcul } = useDossierSession();
  const [modeles, setModeles] = useState<{ id: string; etiquette: string }[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [chargement, setChargement] = useState(false);

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      nom: "",
      siret: "",
      debut_activite: "",
      millesime: new Date().getFullYear().toString(),
    },
  });

  useEffect(() => {
    void chargerModeles().then((rep) => setModeles(rep.modeles));
  }, []);

  const appliquer = useCallback(
    (payload: DossierPayload) => {
      setSession({
        dossier: payload.dossier,
        mouvements: payload.mouvements,
        grille: payload.grille,
        calcul: null,
      });
      const dossier = payload.dossier;
      form.reset({
        nom: String(dossier.nom ?? ""),
        siret: String(dossier.siret ?? ""),
        debut_activite: String(dossier.debut_activite ?? ""),
        millesime: String(dossier.millesime ?? ""),
      });
    },
    [form, setSession],
  );

  useEffect(() => {
    if (session) return;
    void (async () => {
      setChargement(true);
      try {
        const payload = await chargerDossier();
        if (!payload || payload.erreur) return;
        appliquer(payload);
      } finally {
        setChargement(false);
      }
    })();
  }, [appliquer, form, session, setSession]);

  async function ouvrirModele(id: string) {
    setChargement(true);
    setMessage(null);
    try {
      const payload = await chargerModele(id);
      if (payload.erreur) {
        setMessage(payload.erreur);
        return;
      }
      appliquer(payload);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Chargement refusé.");
    } finally {
      setChargement(false);
    }
  }

  async function creerNouveau(modele: string) {
    setChargement(true);
    setMessage(null);
    try {
      const created = await creerDepuisModele(modele);
      if (created.erreur) {
        setMessage(created.erreur);
        return;
      }
      appliquer(created);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Copie refusée.");
    } finally {
      setChargement(false);
    }
  }

  async function onSubmit(values: FormValues) {
    setMessage(null);
    setChargement(true);
    try {
      let base = session?.dossier;
      let mouvements = session?.mouvements;
      if (!base) {
        const created = await creerDepuisModele("premier-exercice");
        if (created.erreur) {
          setMessage(created.erreur);
          return;
        }
        base = created.dossier;
        mouvements = created.mouvements;
      }
      const dossier = {
        ...base,
        ...values,
        regime: "lmnp",
        statut: base.statut ?? "brouillon",
        relu_notice: base.relu_notice ?? false,
      };
      const saved = await enregistrerDossier(dossier, mouvements);
      if (saved.erreur) {
        setMessage(saved.erreur);
        return;
      }
      const calcul = await construire();
      if (calcul.erreur) {
        setMessage(calcul.erreur);
        return;
      }
      setCalcul(calcul);
      setSession({
        dossier: saved.dossier,
        mouvements: saved.mouvements,
        grille: saved.grille,
        calcul,
      });
      navigate("/v1/bien");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Enregistrement refusé.");
    } finally {
      setChargement(false);
    }
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardTitle>1. Dossier</CardTitle>
        <p className="mt-2 text-sm text-[var(--color-muted-foreground)]">
          SIRET, début d&apos;activité et millésime fiscal. Contrôle minimal de la clé SIRENE (Luhn).
        </p>
        <form className="mt-6 grid gap-4 sm:grid-cols-2" onSubmit={form.handleSubmit(onSubmit)}>
          <div className="sm:col-span-2">
            <Label htmlFor="nom">Nom du dossier</Label>
            <Input id="nom" {...form.register("nom")} autoComplete="organization" />
            {form.formState.errors.nom ? (
              <p className="mt-1 text-sm text-[var(--color-destructive)]">{form.formState.errors.nom.message}</p>
            ) : null}
          </div>
          <div>
            <Label htmlFor="siret">SIRET</Label>
            <Input id="siret" inputMode="numeric" maxLength={14} {...form.register("siret")} />
            {form.formState.errors.siret ? (
              <p className="mt-1 text-sm text-[var(--color-destructive)]">{form.formState.errors.siret.message}</p>
            ) : null}
          </div>
          <div>
            <Label htmlFor="debut_activite">Début d&apos;activité</Label>
            <Input id="debut_activite" type="date" {...form.register("debut_activite")} />
          </div>
          <div>
            <Label htmlFor="millesime">Millésime</Label>
            <Input id="millesime" inputMode="numeric" maxLength={4} {...form.register("millesime")} />
          </div>
          <div className="sm:col-span-2 flex justify-end">
            <Button type="submit" disabled={chargement}>
              Enregistrer et continuer
            </Button>
          </div>
        </form>
        {message ? <p className="mt-4 text-sm text-[var(--color-destructive)]">{message}</p> : null}
      </Card>

      <Card>
        <CardTitle>Démarrer depuis un exemple</CardTitle>
        <p className="mt-2 text-sm text-[var(--color-muted-foreground)]">
          Les dossiers golden servent de référence et de point de départ pour la saisie.
        </p>
        <ul className="mt-4 space-y-2">
          {modeles.map((modele) => (
            <li key={modele.id} className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-medium">{modele.etiquette}</span>
              <Button type="button" size="sm" variant="outline" onClick={() => void ouvrirModele(modele.id)}>
                Ouvrir en lecture
              </Button>
              <Button type="button" size="sm" variant="ghost" onClick={() => void creerNouveau(modele.id)}>
                Copier pour travailler
              </Button>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
