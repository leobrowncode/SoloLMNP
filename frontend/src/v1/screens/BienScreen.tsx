import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useNavigate } from "react-router-dom";
import { z } from "zod";
import { Button } from "../components/ui/button";
import { Card, CardTitle } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { chargerDossier, construire, enregistrerDossier } from "../lib/api";
import { useDossierSession } from "../context/DossierContext";
import { centimesDepuisEuros, eurosDepuisCentimes } from "../lib/money";

const schema = z.object({
  nom_bien: z.string().min(1),
  date_acquisition: z.string().min(1),
  date_mise_en_service: z.string().min(1),
  terrain: z.string().min(1),
  batiment: z.string().min(1),
  frais: z.string(),
  mobilier: z.string(),
  mobilier_duree_mois: z.string().min(1),
  emprunt_capital: z.string(),
  emprunt_date: z.string().optional(),
  apport: z.string(),
});

type FormValues = z.infer<typeof schema>;

function lireBien(dossier: Record<string, unknown>) {
  const bien = (dossier.bien as Record<string, unknown> | undefined) ?? {};
  const emprunt = (dossier.emprunt as Record<string, unknown> | undefined) ?? {};
  return {
    nom_bien: String(bien.nom ?? ""),
    date_acquisition: String(bien.date_acquisition ?? dossier.debut_activite ?? ""),
    date_mise_en_service: String(bien.date_mise_en_service ?? ""),
    terrain: eurosDepuisCentimes(Number(bien.terrain_centimes ?? 0)),
    batiment: eurosDepuisCentimes(Number(bien.batiment_centimes ?? 0)),
    frais: eurosDepuisCentimes(Number(bien.frais_centimes ?? 0)),
    mobilier: eurosDepuisCentimes(Number(bien.mobilier_centimes ?? 0)),
    mobilier_duree_mois: String(bien.mobilier_duree_mois ?? 84),
    emprunt_capital: eurosDepuisCentimes(Number(emprunt.capital_centimes ?? 0)),
    emprunt_date: String(emprunt.date ?? ""),
    apport: eurosDepuisCentimes(Number(dossier.apport_centimes ?? 0)),
  };
}

export default function BienScreen() {
  const navigate = useNavigate();
  const { session, setSession, setCalcul } = useDossierSession();
  const [message, setMessage] = useState<string | null>(null);

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: lireBien(session?.dossier ?? {}),
  });

  useEffect(() => {
    if (session?.dossier) form.reset(lireBien(session.dossier));
  }, [form, session?.dossier]);

  if (!session) {
    return (
      <Card>
        <CardTitle>Bien</CardTitle>
        <p className="mt-2 text-sm">Commencez par l&apos;écran Dossier.</p>
        <Link className="mt-4 inline-flex text-sm text-[var(--color-primary)] underline" to="/v1/dossier">
          Retour au dossier
        </Link>
      </Card>
    );
  }

  async function onSubmit(values: FormValues) {
    if (!session) return;
    setMessage(null);
    const courant = session;
    const bien = {
      nom: values.nom_bien,
      date_acquisition: values.date_acquisition,
      date_mise_en_service: values.date_mise_en_service,
      terrain_centimes: centimesDepuisEuros(values.terrain),
      batiment_centimes: centimesDepuisEuros(values.batiment),
      frais_centimes: centimesDepuisEuros(values.frais),
      mobilier_centimes: centimesDepuisEuros(values.mobilier),
      mobilier_duree_mois: Number(values.mobilier_duree_mois) || 84,
      ventilation: "composants",
    };
    const emprunt =
      centimesDepuisEuros(values.emprunt_capital) > 0
        ? { capital_centimes: centimesDepuisEuros(values.emprunt_capital), date: values.emprunt_date || values.date_acquisition }
        : undefined;
    const dossier = {
      ...courant.dossier,
      bien,
      ...(emprunt ? { emprunt } : {}),
      apport_centimes: centimesDepuisEuros(values.apport),
    };
    try {
      await enregistrerDossier(courant.chemin, dossier, courant.mouvements);
      const relu = await chargerDossier(courant.chemin);
      const calcul = await construire(courant.chemin);
      if (calcul.erreur) {
        setMessage(calcul.erreur);
        return;
      }
      setCalcul(calcul);
      setSession({
        ...courant,
        dossier: relu.dossier,
        grille: relu.grille,
        calcul,
      });
      navigate("/v1/annee");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Enregistrement refusé.");
    }
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardTitle>2. Bien et emprunt</CardTitle>
        <p className="mt-2 text-sm text-[var(--color-muted-foreground)]">
          Acquisition, terrain non amortissable, ventilation par composants (grille par défaut) et emprunt.
        </p>
        <form className="mt-6 grid gap-4 sm:grid-cols-2" onSubmit={form.handleSubmit(onSubmit)}>
          <div className="sm:col-span-2">
            <Label htmlFor="nom_bien">Libellé du bien</Label>
            <Input id="nom_bien" {...form.register("nom_bien")} />
          </div>
          <div>
            <Label htmlFor="date_acquisition">Date d&apos;acquisition</Label>
            <Input id="date_acquisition" type="date" {...form.register("date_acquisition")} />
          </div>
          <div>
            <Label htmlFor="date_mise_en_service">Mise en service</Label>
            <Input id="date_mise_en_service" type="date" {...form.register("date_mise_en_service")} />
          </div>
          <div>
            <Label htmlFor="terrain">Terrain (euros)</Label>
            <Input id="terrain" inputMode="decimal" {...form.register("terrain")} />
          </div>
          <div>
            <Label htmlFor="batiment">Bâtiment (euros)</Label>
            <Input id="batiment" inputMode="decimal" {...form.register("batiment")} />
          </div>
          <div>
            <Label htmlFor="frais">Frais d&apos;acquisition (euros)</Label>
            <Input id="frais" inputMode="decimal" {...form.register("frais")} />
          </div>
          <div>
            <Label htmlFor="mobilier">Mobilier (euros)</Label>
            <Input id="mobilier" inputMode="decimal" {...form.register("mobilier")} />
          </div>
          <div>
            <Label htmlFor="mobilier_duree_mois">Durée mobilier (mois)</Label>
            <Input id="mobilier_duree_mois" inputMode="numeric" {...form.register("mobilier_duree_mois")} />
          </div>
          <div>
            <Label htmlFor="emprunt_capital">Capital emprunté (euros)</Label>
            <Input id="emprunt_capital" inputMode="decimal" {...form.register("emprunt_capital")} />
          </div>
          <div>
            <Label htmlFor="emprunt_date">Date de l&apos;emprunt</Label>
            <Input id="emprunt_date" type="date" {...form.register("emprunt_date")} />
          </div>
          <div>
            <Label htmlFor="apport">Apport (euros)</Label>
            <Input id="apport" inputMode="decimal" {...form.register("apport")} />
          </div>
          <div className="sm:col-span-2 flex justify-between">
            <Button type="button" variant="outline" onClick={() => navigate("/v1/dossier")}>
              Retour
            </Button>
            <Button type="submit">Enregistrer et continuer</Button>
          </div>
        </form>
        {message ? <p className="mt-4 text-sm text-[var(--color-destructive)]">{message}</p> : null}
      </Card>

      <Card>
        <CardTitle>Grille d&apos;amortissement par composants</CardTitle>
        <p className="mt-2 text-sm text-[var(--color-muted-foreground)]">
          Grille indicative modifiable dans le dossier source. Ce n&apos;est pas un barème légal.
        </p>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-[var(--color-border)]">
                <th className="py-2 pr-3">Composant</th>
                <th className="py-2 pr-3">Base</th>
                <th className="py-2 pr-3">Durée (mois)</th>
                <th className="py-2 pr-3">Compte</th>
              </tr>
            </thead>
            <tbody>
              {session.grille.map((ligne) => (
                <tr key={ligne.cle} className="border-b border-[var(--color-border)]">
                  <td className="py-2 pr-3">{ligne.libelle}</td>
                  <td className="py-2 pr-3">{eurosDepuisCentimes(ligne.base_centimes)}</td>
                  <td className="py-2 pr-3">{ligne.duree_mois}</td>
                  <td className="py-2 pr-3 font-mono text-xs">{ligne.compte}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
