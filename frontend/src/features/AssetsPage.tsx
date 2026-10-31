import { useEffect, useLayoutEffect, useRef, useState } from "react";
import {
  assetsRequest as api, type Asset, type DepreciationBatchResult, type DepreciationPeriod,
} from "../api/assets";
import { request, type Account, type Setup } from "../api/ledger";
import { BrowsableList } from "./BrowsableList";
import { EmptyState } from "./EmptyState";
import ScreenStatus from "./ScreenStatus";
import {
  beginLoad, defer, failLoad, finishLoad, idleView, showsData, toApiError, type ScreenView,
} from "./screenState";
import { operationsRequest, type Property } from "../api/operations";
import {
  alignAssetDraft, assetAccountChoices, componentAssetChoices, DEFAULT_ASSET,
  depreciationAccountChoices, mirrorDepreciation, preferredAccount,
} from "./assetAccounts";
import {
  PLAN_HELP, correctionMessage, editTitle, locked, readInvalidation, type CorrectionState,
} from "./correction";
import {
  depreciationPostedSentence, isSharedText, postedTotalCents, repeatedTexts,
} from "./assetJustification";
import ComponentJustification from "./ComponentJustification";
import {
  activityCause, assetCreateCauses, depreciationCalculateCauses, describedBy, listed, postDepreciationCauses,
} from "./actionCauses";
import PrerequisiteList from "./PrerequisiteList";
import PropertyEntry from "./PropertyEntry";
import GlossaryTip from "./GlossaryTip";
import { GLOSSARY } from "./glossary";
import { SaveNoticeHost } from "./LocalFeedback";
import { useSaveNotice } from "./localFeedback";
import ReviewForm, { type Field } from "./ReviewForm";
import MutationStatus from "./MutationStatus";
import { useMutation } from "./useMutation";
import { ENUM_LABELS, enumChoices, enumLabel, formatEuros, formatIsoDate } from "../lib/format";
import "./ledger.css";
import FitSelect from "../lib/FitSelect";
import { MobileSection, PageAnchors } from "../lib/PageSection";
import { ResponsiveTable } from "../lib/ResponsiveTable";

interface Editor {
  title: string; path: string; fields: Field[]; retry?: boolean;
  method?: "POST" | "PATCH";
  help?: string;
  derive?: ((draft: Record<string, string>, changed: string) => Partial<Record<string, string>>) | undefined;
}
const categories = (Object.entries(ENUM_LABELS.assetCategory) as [string, string][])
  .filter(([code]) => code !== "LAND");
interface PlanItem {
  kind: "LAND" | "BUILDING" | "COMPONENT";
  label: string;
  amount: string;
  asset_account: string;
  depreciation_account: string | null;
  useful_life_months: number | null;
  service_start_date: string;
}
interface DwellingPlan {
  property_id: number;
  depreciable_base: string;
  acquisition_costs_included: string;
  labels: string[];
  items: PlanItem[];
  preview_token: string;
  created: boolean;
}
function planKind(kind: PlanItem["kind"]): string {
  return enumLabel("planKind", kind);
}

export default function AssetsPage() {
  const [setup, setSetup] = useState<Setup | null>(null);
  const [properties, setProperties] = useState<Property[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [periods, setPeriods] = useState<DepreciationPeriod[]>([]);
  const [yearId, setYearId] = useState(0);
  const [planProperty, setPlanProperty] = useState(0);
  const [plan, setPlan] = useState<{ propertyId: number; preview: DwellingPlan } | null>(null);
  const [confirming, setConfirming] = useState(false);
  const { busy, step, run } = useMutation();
  const batchKey = useRef<string | null>(null);
  const [editor, setEditor] = useState<Editor | null>(null);
  const [revision, setRevision] = useState(0);
  const [error, setError] = useState("");
  const [errorAction, setErrorAction] = useState<{ label: string; href: string } | null>(null);
  const { notice, show, dismiss } = useSaveNotice();
  const [boot, setBoot] = useState<ScreenView<{ ready: true }>>(() => beginLoad(idleView(), false));
  const [periodsView, setPeriodsView] = useState<ScreenView<{ yearId: number }>>(idleView());
  const [periodsAttempt, setPeriodsAttempt] = useState(0);
  const periodRequest = useRef(0);
  const planRequest = useRef(0);

  useEffect(() => {
    let active = true;
    defer(() => {
      if (!active) return;
      setBoot((current) => beginLoad(current, current.data !== null));
    });
    void Promise.all([
      request<Setup>("/setup"), request<Account[]>("/accounts"),
      operationsRequest<Property[]>("/properties"), api<Asset[]>(""),
    ]).then(([s, a, p, rows]) => {
      if (!active) return;
      setSetup(s); setAccounts(a); setProperties(p); setAssets(rows);
      setYearId((value) => value || s.years.find((year) => year.status === "OPEN")?.id || 0);
      setBoot(finishLoad({ ready: true }));
    }).catch((reason: unknown) => {
      if (active) setBoot((current) => failLoad(current, toApiError(reason), current.data !== null));
    });
    return () => { active = false; };
  }, [revision]);
  // Register the read before the user can calculate against this rendered year.
  // A passive effect could otherwise invalidate a calculation started first.
  useLayoutEffect(() => {
    if (!yearId) return;
    let active = true;
    const requests = periodRequest;
    const requestId = ++requests.current;
    const selectedYear = yearId;
    defer(() => {
      if (!(active && requestId === periodRequest.current)) return;
      setPeriodsView((current) => beginLoad(current, current.data?.yearId === selectedYear));
    });
    void api<DepreciationPeriod[]>(`/years/${selectedYear}/periods`).then((rows) => {
      if (!(active && requestId === periodRequest.current)) return;
      setPeriods(rows);
      setPeriodsView(finishLoad({ yearId: selectedYear }, () => rows.length === 0));
    }).catch((reason: unknown) => {
      if (active && requestId === periodRequest.current) {
        setPeriodsView((current) => failLoad(current, toApiError(reason), current.data?.yearId === selectedYear));
      }
    });
    return () => { active = false; ++requests.current; };
  }, [yearId, revision, periodsAttempt]);

  const property: Field = { name: "property_id", label: "Bien", choices: properties.map((row) => [String(row.id), row.name]) };
  function openAsset(land: boolean) {
    const category = land ? "LAND" : "BUILDING";
    const assetAccount = preferredAccount(assetAccountChoices(accounts, category), DEFAULT_ASSET[category]);
    const depreciationAccount = preferredAccount(
      depreciationAccountChoices(accounts, assetAccount),
      mirrorDepreciation(assetAccount),
    );
    const fields: Field[] = [
      property,
      { name: "category", label: "Catégorie", choices: land ? [["LAND", `${enumLabel("assetCategory", "LAND")} — jamais amorti`]] : categories },
      { name: "label", label: "Libellé" },
      { name: "acquisition_date", label: "Date d’acquisition", type: "date" },
      { name: "service_start_date", label: "Date de mise en service", type: "date" },
      { name: "acquisition_value", label: "Valeur d’acquisition (€)", money: true },
      { name: "depreciable_value", label: "Valeur amortissable (€)", money: true, value: land ? "0.00" : undefined },
      { name: "non_depreciable_value", label: "Valeur non amortissable (€)", money: true, value: land ? undefined : "0.00" },
      { name: "residual_value", label: "Valeur résiduelle (€)", money: true, value: "0.00" },
      { name: "method", label: "Méthode", choices: land ? [["NONE", `${enumLabel("depreciationMethod", "NONE")} — terrain`]] : [["LINEAR", enumLabel("depreciationMethod", "LINEAR")]] },
      { name: "useful_life_months", label: "Durée d’utilisation en mois", type: "number", optional: land },
      {
        name: "asset_account", label: "Compte d’immobilisation", value: assetAccount,
        choicesFor: (draft) => assetAccountChoices(accounts, land ? "LAND" : draft.category ?? ""),
        hint: land
          ? "Compte 211 uniquement. Le terrain n’a pas de compte d’amortissement."
          : "Uniquement les comptes de la catégorie. Les comptes 28 n’y figurent pas.",
      },
    ];
    if (!land) fields.push({
      name: "depreciation_account", label: "Compte d’amortissement", value: depreciationAccount,
      choicesFor: (draft) => depreciationAccountChoices(accounts, draft.asset_account ?? ""),
      hint: "Compte 28 miroir du compte d’immobilisation, par exemple 213000 et 281300.",
    });
    fields.push(
      { name: "basis_reason", label: "Justification de la valeur (au moins 5 caractères)" },
      { name: "duration_reason", label: "Justification de la durée (au moins 5 caractères)", value: land ? "Terrain non amortissable" : undefined },
    );
    setEditor({
      title: land ? "Inscrire un terrain non amortissable" : "Inscrire une immobilisation",
      path: "", fields,
      derive: (draft, changed) => alignAssetDraft(accounts, draft, changed, land ? "land" : "asset"),
    });
  }
  function openComponent(asset: Asset) {
    const assetAccount = preferredAccount(componentAssetChoices(accounts), asset.asset_account);
    const depreciationAccount = preferredAccount(
      depreciationAccountChoices(accounts, assetAccount),
      asset.depreciation_account,
    );
    setEditor({ title: `Ajouter un composant à ${asset.label}`, path: `/${asset.id}/components`, derive: (draft, changed) => alignAssetDraft(accounts, draft, changed, "component"), fields: [
      { name: "category", label: "Catégorie technique" }, { name: "label", label: "Libellé" },
      { name: "value", label: "Valeur du composant (€)", money: true },
      { name: "useful_life_months", label: "Durée d’utilisation en mois", type: "number" },
      { name: "service_start_date", label: "Date de mise en service", type: "date" },
      {
        name: "asset_account", label: "Compte d’immobilisation", value: assetAccount,
        choicesFor: () => componentAssetChoices(accounts),
        hint: "Construction ou agencement (213 ou 2135), jamais 211 ni 28.",
      },
      {
        name: "depreciation_account", label: "Compte d’amortissement", value: depreciationAccount,
        choicesFor: (draft) => depreciationAccountChoices(accounts, draft.asset_account ?? ""),
        hint: "Compte 28 miroir : 213000 avec 281300, 213500 avec 281350.",
      },
      { name: "basis_reason", label: "Justification de la ventilation" },
      { name: "duration_reason", label: "Justification de la durée" },
    ] });
  }
  async function save(data: Record<string, unknown>) {
    await run(async (report) => {
      if (!editor) return;
      report("Enregistrement de l’immobilisation…");
      const result = await api<Record<string, unknown>>(editor.path, editor.method ?? "POST", data);
      const invalidation = readInvalidation(result.invalidation);
      const label = typeof data.label === "string" && data.label.trim() ? data.label.trim() : editor.title;
      const created = (editor.method ?? "POST") === "POST";
      const component = editor.path.includes("/components");
      const assetMatch = editor.path.match(/^\/(\d+)/);
      const savedId = typeof result.id === "number" ? result.id : null;
      const cardId = savedId ?? (assetMatch ? Number(assetMatch[1]) : null);
      setEditor(null);
      if (editor.path.includes("/periods/") && editor.path.endsWith("/post")) {
        show({
          kind: GLOSSARY.dotation.label,
          name: editor.title.replace(/^Comptabiliser /, "") || label,
          action: "comptabilisée",
          targetId: "dotations",
          detail: "Dotation comptabilisée.",
          next: { label: "Voir le journal", href: "/comptabilite/journal" },
        });
      } else {
        const existingCard = !created && cardId ? `asset-${cardId}` : null;
        show({
          kind: component ? GLOSSARY.composant.label : GLOSSARY.immobilisation.label,
          name: label,
          action: created ? (component ? "créé" : "créée") : (component ? "modifié" : "modifiée"),
          targetId: existingCard ?? "creer-immobilisation",
          highlightId: created && cardId ? `asset-${cardId}` : undefined,
          detail: invalidation ? correctionMessage(invalidation) : undefined,
          next: invalidation?.dropped_period_ids.length
            ? { label: "Relancer le calcul des périodes", href: "/immobilisations#calculer-periodes" }
            : { label: "Calculer les périodes", href: "/immobilisations#calculer-periodes" },
        });
      }
      setRevision((value) => value + 1);
    });
  }
  function correctionOf(row: { correction?: CorrectionState }): CorrectionState | undefined {
    return row.correction;
  }
  function openAssetCorrection(row: Asset) {
    const state = correctionOf(row);
    const land = row.category === "LAND";
    const groups = land ? ["value", "dates", "account"] : ["value", "life", "dates", "account"];
    const fields: Field[] = [
      { name: "label", label: "Libellé", value: row.label, group: "Identification" },
    ];
    if (!locked(state, "dates")) {
      fields.push(
        { name: "acquisition_date", label: "Date d’acquisition", type: "date", value: row.acquisition_date ?? "", group: "Dates" },
        { name: "service_start_date", label: "Date de mise en service", type: "date", value: row.service_start_date ?? "", group: "Dates" },
      );
    }
    if (!locked(state, "value")) {
      fields.push({ name: "acquisition_value", label: "Valeur d’acquisition (€)", money: true, value: row.acquisition_value, group: "Valeur" });
      if (!land) {
        fields.push(
          { name: "depreciable_value", label: "Valeur amortissable (€)", money: true, value: row.depreciable_value, group: "Valeur" },
          { name: "non_depreciable_value", label: "Valeur non amortissable (€)", money: true, value: row.non_depreciable_value, group: "Valeur" },
          { name: "residual_value", label: "Valeur résiduelle (€)", money: true, value: row.residual_value, group: "Valeur" },
        );
      } else {
        fields.push({ name: "non_depreciable_value", label: "Valeur non amortissable (€)", money: true, value: row.non_depreciable_value, group: "Valeur" });
      }
    }
    if (!land && !locked(state, "life")) {
      fields.push({
        name: "useful_life_months", label: "Durée d’utilisation en mois", type: "number",
        value: row.useful_life_months == null ? "" : String(row.useful_life_months), group: "Durée",
      });
    }
    if (!locked(state, "account")) {
      fields.push({
        name: "asset_account", label: "Compte d’immobilisation", value: row.asset_account, group: "Comptes",
        choicesFor: (draft) => assetAccountChoices(accounts, land ? "LAND" : draft.category ?? row.category),
      });
      if (!land) {
        fields.push({
          name: "depreciation_account", label: "Compte d’amortissement", value: row.depreciation_account ?? "", group: "Comptes",
          choicesFor: (draft) => depreciationAccountChoices(accounts, draft.asset_account ?? row.asset_account),
        });
      }
    }
    fields.push(
      { name: "basis_reason", label: "Justification de la valeur", value: row.basis_reason ?? "", group: "Justification" },
      {
        name: "duration_reason", label: "Justification de la durée",
        value: row.duration_reason ?? (land ? "Terrain non amortissable" : ""),
        optional: land, group: "Justification",
      },
      { name: "notes", label: "Notes", value: row.notes ?? "", optional: true, group: "Justification" },
      { name: "reason", label: "Motif de la correction (au moins 5 caractères)", group: "Motif" },
    );
    setEditor({
      title: editTitle(row.label, state, groups),
      path: `/${row.id}`,
      method: "PATCH",
      help: PLAN_HELP,
      fields,
      derive: (draft, changed) => {
        const aligned = alignAssetDraft(
          accounts, { ...draft, category: row.category }, changed, land ? "land" : "asset",
        );
        if (!land || changed !== "acquisition_value") return aligned;
        return { ...aligned, non_depreciable_value: draft.acquisition_value ?? "0.00" };
      },
    });
  }
  function openComponentCorrection(asset: Asset, part: Asset["components"][number]) {
    const state = correctionOf(part);
    const fields: Field[] = [
      { name: "label", label: "Libellé", value: part.label, group: "Identification" },
    ];
    if (!locked(state, "value")) {
      fields.push({ name: "value", label: "Valeur du composant (€)", money: true, value: part.value, group: "Valeur" });
    }
    if (!locked(state, "life")) {
      fields.push({
        name: "useful_life_months", label: "Durée d’utilisation en mois", type: "number",
        value: String(part.useful_life_months), group: "Durée",
      });
    }
    if (!locked(state, "dates")) {
      fields.push({
        name: "service_start_date", label: "Date de mise en service", type: "date",
        value: part.service_start_date, group: "Dates",
      });
    }
    if (!locked(state, "account")) {
      fields.push(
        {
          name: "asset_account", label: "Compte d’immobilisation", value: part.asset_account ?? "", group: "Comptes",
          choicesFor: () => componentAssetChoices(accounts),
        },
        {
          name: "depreciation_account", label: "Compte d’amortissement", value: part.depreciation_account ?? "", group: "Comptes",
          choicesFor: (draft) => depreciationAccountChoices(accounts, draft.asset_account ?? ""),
        },
      );
    }
    fields.push(
      { name: "reason", label: "Motif de la correction (au moins 5 caractères)", group: "Motif" },
    );
    setEditor({
      title: editTitle(part.label, state, ["value", "life", "dates", "account"]),
      path: `/${asset.id}/components/${part.id}`,
      method: "PATCH",
      help: PLAN_HELP,
      fields,
      derive: (draft, changed) => alignAssetDraft(accounts, draft, changed, "component"),
    });
  }
  const selectedProperty = properties.some((row) => row.id === planProperty)
    ? planProperty
    : properties[0]?.id ?? 0;
  const visiblePlan = plan?.propertyId === selectedProperty ? plan.preview : null;
  async function previewPlan() {
    if (!selectedProperty) return;
    await run(async (report) => {
      const requestId = ++planRequest.current;
      const propertyId = selectedProperty;
      report("Prévisualisation du plan d’amortissement…");
      setError(""); dismiss(); setConfirming(false);
      try {
        const result = await api<DwellingPlan>(`/properties/${propertyId}/plan`);
        if (requestId === planRequest.current) setPlan({ propertyId, preview: result });
      } catch (reason) {
        if (requestId === planRequest.current) {
          setError(reason instanceof Error ? reason.message : "Aperçu impossible.");
        }
      }
    });
  }
  async function confirmPlan() {
    if (!visiblePlan || !selectedProperty) return;
    const token = visiblePlan.preview_token;
    const propertyId = selectedProperty;
    await run(async (report) => {
      const requestId = ++planRequest.current;
      report("Création des immobilisations…");
      setError(""); dismiss(); setConfirming(true);
      try {
        const result = await api<DwellingPlan>(
          `/properties/${propertyId}/plan`,
          "POST",
          { confirm: true, preview_token: token },
        );
        if (requestId !== planRequest.current) return;
        setPlan(null);
        const createdLabels = result.labels.join(", ");
        show({
          kind: "Immobilisations",
          name: result.labels[0] ?? "logement",
          action: result.created ? "créées" : "déjà présentes",
          targetId: "creer-immobilisation",
          detail: result.created
            ? `Immobilisations créées : ${createdLabels}. Calculez ensuite les périodes, puis comptabilisez-les.`
            : "Ces immobilisations existent déjà. Aucun doublon n’a été créé.",
          next: { label: "Calculer les périodes", href: "/immobilisations#calculer-periodes" },
        });
        setRevision((value) => value + 1);
      } catch (reason) {
        if (requestId === planRequest.current) {
          setError(reason instanceof Error ? reason.message : "Création impossible.");
        }
      } finally {
        if (requestId === planRequest.current) setConfirming(false);
      }
    });
  }
  function cancelPlan() {
    if (confirming || busy) return;
    ++planRequest.current;
    setPlan(null);
    setError("");
  }
  async function postAll() {
    const pending = periods.filter((row) => row.status !== "POSTED");
    if (pending.length === 0 || !yearId) return;
    await run(async (report) => {
      report(`Comptabilisation de ${pending.length} dotation(s)…`);
      setError("");
      setErrorAction(null);
      dismiss();
      batchKey.current ??= crypto.randomUUID();
      const key = batchKey.current;
      try {
        const result = await api<DepreciationBatchResult>(
          `/years/${yearId}/post`,
          "POST",
          {
            items: pending.map((row) => ({
              period_id: row.id,
              request_id: `dotation-${row.id}-poste`,
              piece_reference: `DOT-${row.id}`,
            })),
          },
          { headers: { "Idempotency-Key": key } },
        );
        batchKey.current = null;
        const failed = result.items.find((item) => item.status === "error");
        if (failed) {
          setErrorAction(failed.action ?? null);
          setError(
            `${failed.message} L’écran recharge l’état enregistré : les dotations déjà passées restent comptabilisées.`,
          );
        } else {
          show({
            kind: GLOSSARY.dotation.label,
            name: `${result.posted_count} écriture(s)`,
            action: result.replayed ? "déjà comptabilisée" : "comptabilisée",
            sentence: depreciationPostedSentence(
              result.posted_count,
              postedTotalCents(pending, result.items),
              result.replayed,
            ),
            targetId: "actions-dotations",
            next: { label: "Voir le journal", href: "/comptabilite/journal" },
          });
        }
      } catch (reason) {
        setErrorAction(null);
        setError(reason instanceof Error ? reason.message : "Comptabilisation impossible.");
      } finally {
        setRevision((value) => value + 1);
      }
    });
  }
  async function calculate() {
    await run(async (report) => {
      const requestId = ++periodRequest.current;
      report("Calcul des périodes…");
      setError(""); dismiss();
      try {
        const rows = await api<DepreciationPeriod[]>(`/years/${yearId}/calculate`, "POST");
        if (requestId === periodRequest.current) {
          setPeriods(rows);
          setPeriodsView(finishLoad({ yearId }, () => rows.length === 0));
          show({
            kind: rows.length > 1 ? "Dotations" : GLOSSARY.dotation.label,
            name: `${rows.length} période(s)`,
            action: rows.length > 1 ? "calculées" : "calculée",
            targetId: "actions-dotations",
            detail: `${rows.length} période(s) calculée(s). Vérifiez-les avant comptabilisation.`,
            next: rows.length
              ? { label: "Comptabiliser toutes les dotations", href: "/immobilisations#comptabiliser-dotations" }
              : undefined,
          });
        }
      } catch (reason) {
        if (requestId === periodRequest.current) {
          setError(reason instanceof Error ? reason.message : "Calcul impossible.");
          setPeriodsView((current) => (current.phase === "loading" ? idleView() : current));
        }
      }
    });
  }

  async function saveComponentJustification(
    asset: Asset,
    part: Asset["components"][number],
    data: { basis_reason?: string; duration_reason?: string; reason: string },
  ) {
    const result = await run(async (report) => {
      report("Enregistrement de la justification…");
      return api<Record<string, unknown>>(`/${asset.id}/components/${part.id}`, "PATCH", data);
    });
    if (!result) return;
    const invalidation = readInvalidation(result.invalidation);
    show({
      kind: GLOSSARY.composant.label,
      name: part.label,
      action: "précisé",
      targetId: `asset-${asset.id}`,
      highlightId: `asset-${asset.id}`,
      detail: invalidation ? correctionMessage(invalidation) : undefined,
    });
    setRevision((value) => value + 1);
  }

  const bootReady = boot.phase === "loaded" || showsData(boot);
  const sharedDuration = repeatedTexts(assets.flatMap((row) => row.components.map((part) => part.duration_reason)));
  const sharedBasis = repeatedTexts(assets.flatMap((row) => row.components.map((part) => part.basis_reason)));
  const sharedLocks = repeatedTexts(assets.flatMap((row) => (
    row.components.flatMap((part) => part.correction?.locks.map((lock) => lock.message) ?? [])
  )));
  const assetCauses = assetCreateCauses(properties.length);
  const assetCauseId = "asset-create-causes";
  const planCauses = assetCreateCauses(properties.length);
  const planCauseId = "asset-plan-causes";
  const periodCauses = depreciationCalculateCauses(yearId, setup?.years ?? []);
  const periodCauseId = "asset-period-causes";
  const periodsSettled = periodsView.phase === "loaded" || periodsView.phase === "empty";
  const postCauses = yearId && periodsSettled ? postDepreciationCauses(periods) : [];
  const postCauseId = "asset-post-causes";
  const postDescribed = yearId ? describedBy(postCauseId, postCauses) : describedBy(periodCauseId, periodCauses);
  return <section id="assets" className="ledger-page asset-page" aria-labelledby="assets-title" data-screen-phase={boot.phase}>
    <div className="heading-with-help">
      <h2 id="assets-title">Immobilisations</h2>
      <GlossaryTip id="amortissement" />
    </div>
    <p id="assets-method-note" className="form-help asset-shared-note">Terrain à part : il ne s’amortit pas. Le bâtiment et les composants sont en linéaire. Les durées proposées se confirment selon l’état du bien.</p>
    <details className="asset-note">
      <summary>Détail et aides</summary>
      <p>Le formulaire ne propose que les comptes de la catégorie. Un couple déjà enregistré et incohérent est signalé ; il n’est pas réécrit. Modifier une fiche demande un motif : tant qu’aucune dotation n’est comptabilisée, la valeur, la durée et les comptes peuvent être corrigés.</p>
      <p>L’aperçu du logement n’enregistre rien. Créer les immobilisations affichées inscrit le terrain à part, ajoute les frais de notaire et d’agence à la base du bâtiment, puis crée six composants. Annuler laisse la base inchangée. Confirmer une seconde fois ne crée pas de doublon. Le mobilier se saisit à part.</p>
      <p>L’entrée du bien se fait une fois : elle inscrit au bilan le terrain, le bâtiment, les emprunts et les frais payés avant l’exercice. L’écart va au compte de l’exploitant (108).</p>
      {sharedDuration.length === 0 && (
        <p>Pour un logement, la durée d’usage proposée se confirme selon l’état du bien et les travaux. Ce n’est pas un barème légal.</p>
      )}
      {sharedDuration.length > 0 && (
        <>
          <p className="field-hint">Justification de durée, commune aux composants.</p>
          {sharedDuration.map((text) => <p key={text}>{text}</p>)}
        </>
      )}
      {sharedBasis.length > 0 && (
        <>
          <p className="field-hint">Justification de quote-part, commune aux composants.</p>
          {sharedBasis.map((text) => <p key={text}>{text}</p>)}
        </>
      )}
      {sharedLocks.length > 0 && (
        <>
          <p className="field-hint">Règle commune après comptabilisation.</p>
          {sharedLocks.map((text) => <p key={text}>{text}</p>)}
        </>
      )}
      <div className="heading-with-help">
        <GlossaryTip id="immobilisation" />
        <GlossaryTip id="terrain" />
        <GlossaryTip id="composant" />
        <GlossaryTip id="compte-108" />
        <GlossaryTip id="extourne" />
      </div>
    </details>
    <PageAnchors
      label="Sections des immobilisations"
      links={[
        { href: "#creer-immobilisation", label: "Nouvelle immobilisation" },
        { href: "#registre-immobilisations", label: "Registre" },
        { href: "#dotations", label: "Dotations" },
      ]}
    />
    {error && <p role="alert" className="ledger-error">{error}{errorAction && <> <a href={errorAction.href}>{errorAction.label}</a></>}</p>}
    <MutationStatus step={step} />
    <ScreenStatus
      state={boot}
      onRetry={() => setRevision((value) => value + 1)}
      loading={<p>Chargement des immobilisations…</p>}
    />
    {boot.phase === "loaded" && !setup?.activity && (
      <PrerequisiteList id="assets-activity" causes={listed(activityCause(false))} intro="Les immobilisations restent indisponibles :" />
    )}
    {bootReady && setup?.activity && <>
      <div id="creer-immobilisation" className="asset-actions">
        <button id="nouvelle-immobilisation" disabled={assetCauses.length > 0 || busy} aria-describedby={describedBy(assetCauseId, assetCauses)} onClick={() => openAsset(false)}>Nouvelle immobilisation</button>
        <button disabled={assetCauses.length > 0 || busy} aria-describedby={describedBy(assetCauseId, assetCauses)} onClick={() => openAsset(true)}>Inscrire un terrain</button>
      </div>
      <PrerequisiteList id={assetCauseId} causes={assetCauses} />
      <PropertyEntry
        properties={properties}
        years={setup.years}
        locked={busy}
        compact
        onDone={() => { setError(""); setRevision((value) => value + 1); }}
      />
      <div id="actions-dotations" className="asset-actions" tabIndex={-1}>
        <label>Exercice<FitSelect value={yearId} onChange={(event) => {
          ++periodRequest.current;
          setPeriods([]); setError(""); dismiss(); setEditor(null);
          setYearId(Number(event.target.value));
        }}>{setup.years.filter((year) => year.status === "OPEN").map((year) => <option key={year.id} value={year.id}>{year.year}</option>)}</FitSelect></label>
        <button id="calculer-periodes" disabled={periodCauses.length > 0 || busy} aria-busy={busy || undefined} aria-describedby={describedBy(periodCauseId, periodCauses)} onClick={() => { void calculate(); }}>Calculer les périodes</button>
        <button id="comptabiliser-dotations" type="button" disabled={busy || (yearId ? postCauses.length > 0 || !periodsSettled : periodCauses.length > 0)} aria-busy={busy || undefined} aria-describedby={postDescribed} onClick={() => { void postAll(); }}>Comptabiliser toutes les dotations</button>
        <SaveNoticeHost place="actions-dotations" notice={notice} onDismiss={dismiss} />
      </div>
      <PrerequisiteList id={periodCauseId} causes={periodCauses} />
      <PrerequisiteList id={postCauseId} causes={postCauses} />
      <SaveNoticeHost place="creer-immobilisation" notice={notice} onDismiss={dismiss} />
      <div className="toolbar asset-actions">
        <label>Logement
          <FitSelect value={selectedProperty} disabled={confirming || busy} onChange={(event) => {
            if (confirming) return;
            ++planRequest.current;
            setPlan(null);
            setPlanProperty(Number(event.target.value));
          }}>
            {properties.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
          </FitSelect>
        </label>
        <button id="preview-amortissement" type="button" disabled={planCauses.length > 0 || busy} aria-busy={busy || undefined} aria-describedby={describedBy(planCauseId, planCauses)} onClick={() => { void previewPlan(); }}>Prévisualiser l’amortissement du logement</button>
        <PrerequisiteList id={planCauseId} causes={planCauses} />
      </div>
      {visiblePlan && <>
        <ResponsiveTable
          label="Aperçu d’amortissement"
          caption={`Aperçu non enregistré · base amortissable ${formatEuros(visiblePlan.depreciable_base)} · frais inclus ${formatEuros(visiblePlan.acquisition_costs_included)}`}
          columns={[
            { key: "kind", label: "Élément" },
            { key: "label", label: "Libellé" },
            { key: "amount", label: "Montant" },
            { key: "account", label: "Compte", priority: "secondary" },
            { key: "depreciation", label: "Amortissement", priority: "secondary" },
            { key: "life", label: "Durée", priority: "secondary" },
            { key: "start", label: "Mise en service", priority: "secondary" },
          ]}
          rows={visiblePlan.items.map((item) => ({
            key: `${item.kind}-${item.label}`,
            cells: [
              planKind(item.kind),
              item.label,
              formatEuros(item.amount),
              item.asset_account,
              item.depreciation_account ?? "—",
              item.useful_life_months === null ? "Non amortissable" : `${item.useful_life_months} mois`,
              formatIsoDate(item.service_start_date),
            ],
          }))}
        />
        <div className="form-actions">
          <button type="button" disabled={busy || !visiblePlan.preview_token} aria-busy={busy || undefined} onClick={() => { void confirmPlan(); }}>Créer les immobilisations affichées</button>
          <button type="button" disabled={confirming} onClick={cancelPlan}>Annuler l’aperçu</button>
        </div>
      </>}
      {editor && <ReviewForm key={JSON.stringify(editor)} title={editor.title} fields={editor.fields} help={editor.help} onSave={save} onCancel={() => setEditor(null)} retryId={editor.retry} derive={editor.derive} locked={busy} />}
      <MobileSection id="registre-immobilisations" title="Registre des immobilisations" open>
      <BrowsableList
        items={assets}
        searchLabel="Rechercher une immobilisation"
        text={(row) => `${row.label} ${row.asset_account} ${row.depreciation_account ?? ""} ${enumLabel("assetCategory", row.category)}`}
        statusOf={(row) => row.method || "NONE"}
        categoryOf={(row) => row.category}
        statusChoices={enumChoices("depreciationMethod")}
        categoryChoices={enumChoices("assetCategory").filter(([code]) => assets.some((row) => row.category === code))}
        statusLabel="Filtrer par mode"
        emptyTitle="Aucune immobilisation."
        emptyReason="Le registre est vide : inscrivez le terrain à part, puis le bâtiment et le mobilier. Le terrain ne s’amortit pas."
        emptyAction={{ label: "Inscrire une immobilisation", href: "#nouvelle-immobilisation" }}
        noResultsReason="Aucune immobilisation ne correspond à la recherche, au mode ou à la catégorie."
        groupBy={(row) => row.category}
        groupTitle={(key) => enumLabel("assetCategory", key)}
      >
      {(listed) => listed.map((row) => <article className="entry-card" id={`asset-${row.id}`} key={row.id}><h3>{row.label}</h3>
        <p>{enumLabel("assetCategory", row.category)} · Valeur {formatEuros(row.acquisition_value)} · Base {formatEuros(row.depreciable_value)} · Non amortissable {formatEuros(row.non_depreciable_value)}</p>
        <p>{row.category === "LAND" ? "Terrain protégé : aucun plan d’amortissement" : `${enumLabel("depreciationMethod", row.method ?? "LINEAR")} sur ${row.useful_life_months} mois · ${row.asset_account} / ${row.depreciation_account}`}</p>
        {row.account_warning && <p role="alert" className="ledger-error">{row.account_warning}</p>}
        {row.correction?.locks.map((lock) => <p className="form-help" key={lock.code}>{lock.message}</p>)}
        {(row.correction?.calculated_periods ?? 0) > 0 && !locked(row.correction, "value") && (
          <p className="form-help">{row.correction?.calculated_periods} période(s) calculée(s) seront effacées si la valeur, la durée, les dates ou les comptes changent.</p>
        )}
        <div className="entry-actions">
          {row.category === "BUILDING" && <button type="button" disabled={busy} onClick={() => openComponent(row)}>Ajouter un composant</button>}
          <button type="button" disabled={busy} onClick={() => openAssetCorrection(row)}>{editTitle(row.label, row.correction, row.category === "LAND" ? ["value", "dates", "account"] : ["value", "life", "dates", "account"])}</button>
        </div>
        {row.category === "BUILDING" && row.components.length === 0 && <p>Ajoutez tous les composants avant le premier calcul ; leur total doit couvrir exactement la base.</p>}
        {row.components.length > 0 && <ResponsiveTable
          label={`Composants de ${row.label}`}
          caption={`${row.components.length} composants`}
          columns={[
            { key: "label", label: "Composant" },
            { key: "amount", label: "Montant" },
            { key: "justification", label: "Justification" },
            { key: "life", label: "Durée", priority: "secondary" },
            { key: "account", label: "Comptes", priority: "secondary" },
          ]}
          rows={row.components.map((part) => {
            const groups = ["value", "life", "dates", "account"];
            const frozen = groups.every((group) => locked(part.correction, group));
            const ownLocks = (part.correction?.locks ?? []).filter((lock) => !isSharedText(lock.message, sharedLocks));
            return {
              key: String(part.id),
              cells: [
                <span key="label">
                  {part.label}
                  {part.account_warning && <span role="alert" className="component-alert">{part.account_warning}</span>}
                  {ownLocks.map((lock) => <span className="component-note" key={lock.code}>{lock.message}</span>)}
                </span>,
                formatEuros(part.value),
                <span key="justification">
                  <ComponentJustification
                    key={`${part.id}-${part.basis_reason ?? ""}-${part.duration_reason ?? ""}`}
                    part={part}
                    sharedBasis={isSharedText(part.basis_reason, sharedBasis)}
                    sharedDuration={isSharedText(part.duration_reason, sharedDuration)}
                    busy={busy}
                    onSave={(data) => saveComponentJustification(row, part, data)}
                  />
                  {!frozen && (
                    <button type="button" disabled={busy} onClick={() => openComponentCorrection(row, part)}>
                      {editTitle(part.label, part.correction, groups)}
                    </button>
                  )}
                </span>,
                `${part.useful_life_months} mois`,
                `${part.asset_account ?? "—"} / ${part.depreciation_account ?? "—"}`,
              ],
            };
          })}
        />}
        <SaveNoticeHost place={`asset-${row.id}`} notice={notice} onDismiss={dismiss} />
      </article>)}
      </BrowsableList>
      </MobileSection>
      <div className="section-heading" id="dotations" tabIndex={-1}><div><div className="heading-with-help"><h3>Dotations comptables</h3><GlossaryTip id="dotation" /><GlossaryTip id="compte-681" /></div><p>Le calcul en jours calendaires ne modifie jamais la couche fiscale.</p></div>
        <SaveNoticeHost place="dotations" notice={notice} onDismiss={dismiss} />
      </div>
      <ScreenStatus
        state={periodsView}
        onRetry={() => setPeriodsAttempt((value) => value + 1)}
        loading={<p>Chargement des dotations…</p>}
        empty={<EmptyState title="Aucune dotation calculée pour cet exercice." reason="Le calcul crée les périodes à comptabiliser. Il ne modifie pas la fiscalité." action={{ label: "Calculer les périodes de cet exercice", href: "#calculer-periodes" }} />}
      />
      {showsData(periodsView) && periods.length > 0 && (
      <BrowsableList
        items={periods}
        searchLabel="Rechercher une dotation"
        text={(row) => `${row.target_label} ${enumLabel("periodStatus", row.status)}`}
        statusOf={(row) => row.status}
        categoryOf={(row) => row.target_type}
        statusChoices={enumChoices("periodStatus")}
        categoryChoices={[["ASSET", "Immobilisation"], ["COMPONENT", "Composant"]]}
        emptyTitle="Aucune dotation calculée pour cet exercice."
        emptyReason="Le calcul crée les périodes à comptabiliser."
        noResultsReason="Aucune dotation ne correspond à la recherche, au statut ou à la catégorie."
        groupBy={(row) => row.status}
        groupTitle={(key) => enumLabel("periodStatus", key)}
      >
      {(rows) => <ResponsiveTable
        label="Dotations"
        columns={[
          { key: "target", label: "Actif / composant" },
          { key: "period", label: "Période", priority: "secondary" },
          { key: "days", label: "Jours", priority: "secondary" },
          { key: "amount", label: "Dotation" },
          { key: "accumulated", label: "Cumul", priority: "secondary" },
          { key: "vnc", label: "VNC de la base", header: <>VNC de la base <GlossaryTip id="vnc" /></>, priority: "secondary" },
          { key: "status", label: "État" },
        ]}
        rows={rows.map((row) => ({
          key: String(row.id),
          cells: [
            row.target_label,
            `${formatIsoDate(row.period_start)} → ${formatIsoDate(row.period_end)}`,
            row.days,
            formatEuros(row.amount),
            formatEuros(row.accumulated),
            formatEuros(row.net_book_value),
            row.status === "POSTED"
              ? enumLabel("periodStatus", row.status)
              : <button type="button" disabled={busy} aria-busy={busy || undefined} onClick={() => setEditor({ title: `Comptabiliser ${row.target_label}`, path: `/periods/${row.id}/post`, retry: true, fields: [{ name: "piece_reference", label: "Référence de la pièce d’inventaire" }] })}>Comptabiliser</button>,
          ],
        }))}
      />}
      </BrowsableList>
      )}
    </>}
  </section>;
}
