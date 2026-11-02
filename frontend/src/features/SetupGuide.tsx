import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { RequestError, request, type Setup } from "../api/ledger";
import { DATE_HINT, YEAR_END_BEFORE_START } from "../lib/format";
import FrenchDateInput from "../lib/FrenchDateInput";
import FrenchForm from "../lib/FrenchForm";
import { showFrenchValidation } from "../lib/validation";
import ApiErrorAlert from "./ApiErrorAlert";
import {
  DECLARATION_STEPS,
  identityFromSiren,
  identityFromSiret,
  identityIssue,
  sirenDerivedFromSiret,
  suggestedExercise,
  type DeclarationStepId,
  type GuideLocationState,
  type IdentityDraft,
} from "./declarationSetup";
import GlossaryTip from "./GlossaryTip";
import { GLOSSARY } from "./glossary";
import MutationStatus from "./MutationStatus";
import { useMutation } from "./useMutation";
import type { ShowSaveNotice } from "./localFeedback";

const PROPERTY_PATH = "/operations/biens#ajouter-bien";

function DeclarationRail({ current }: { current: DeclarationStepId }) {
  const index = DECLARATION_STEPS.findIndex((step) => step.id === current);
  return (
    <ol className="declaration-rail" aria-label="Initialisation de la déclaration">
      {DECLARATION_STEPS.map((step, position) => (
        <li
          key={step.id}
          className={position < index ? "is-done" : undefined}
          aria-current={position === index ? "step" : undefined}
        >
          <span className="step-index" aria-hidden="true">{position + 1}</span>
          {position < index ? <span className="sr-only">fait. </span> : null}
          {step.label}
        </li>
      ))}
    </ol>
  );
}

function YearForm({
  busy,
  suggestion,
  help,
  onCreate,
}: {
  busy: boolean;
  suggestion: { start: string; end: string; vintage: string } | null;
  help: string;
  onCreate: (input: { start: string; end: string; vintage: string }) => void;
}) {
  return (
    <FrenchForm
      onInput={(event) => {
        const form = event.currentTarget;
        const start = form.elements.namedItem("start");
        const end = form.elements.namedItem("end");
        if (start instanceof HTMLInputElement && end instanceof HTMLInputElement) {
          end.setCustomValidity(start.value && end.value && start.value > end.value ? YEAR_END_BEFORE_START : "");
        }
      }}
      onSubmit={(event) => {
        event.preventDefault();
        const form = event.currentTarget;
        const start = form.elements.namedItem("start");
        const endInput = form.elements.namedItem("end");
        if (
          start instanceof HTMLInputElement
          && endInput instanceof HTMLInputElement
          && start.value
          && endInput.value
          && start.value > endInput.value
        ) {
          endInput.setCustomValidity(YEAR_END_BEFORE_START);
          showFrenchValidation(form);
          return;
        }
        if (endInput instanceof HTMLInputElement) endInput.setCustomValidity("");
        const data = new FormData(form);
        onCreate({
          start: String(data.get("start") ?? ""),
          end: String(data.get("end") ?? ""),
          vintage: String(data.get("vintage") ?? ""),
        });
      }}
    >
      <p className="form-help">{help}</p>
      <label>
        Début de l’exercice
        <FrenchDateInput name="start" required defaultValue={suggestion?.start} />
        <span className="field-hint">{DATE_HINT}</span>
      </label>
      <label>
        Fin de l’exercice
        <FrenchDateInput name="end" required defaultValue={suggestion?.end} />
        <span className="field-hint">{DATE_HINT}</span>
      </label>
      <label>
        Millésime fiscal
        <input
          name="vintage"
          pattern="[0-9]{4}"
          required
          placeholder="2026"
          defaultValue={suggestion?.vintage}
        />
      </label>
      <GlossaryTip id="millesime" />
      <GlossaryTip id="exercice" />
      <button disabled={busy}>Créer l’exercice</button>
    </FrenchForm>
  );
}

export default function SetupGuide({
  setup,
  hash,
  onReload,
  show,
}: {
  setup: Setup;
  hash: string;
  onReload: () => void;
  show: (notice: ShowSaveNotice) => void;
}) {
  const navigate = useNavigate();
  const { busy, step, run } = useMutation();
  const persistedKey = `${setup.activity?.siren ?? ""}\0${setup.activity?.siret ?? ""}`;
  const persistedIdentity: IdentityDraft = {
    siren: setup.activity?.siren ?? "",
    siret: setup.activity?.siret ?? "",
  };
  const [identityState, setIdentityState] = useState({ key: persistedKey, value: persistedIdentity });
  if (identityState.key !== persistedKey) {
    setIdentityState({ key: persistedKey, value: persistedIdentity });
  }
  const identity = identityState.key === persistedKey ? identityState.value : persistedIdentity;
  const [editState, setEditState] = useState({ hash, editing: hash === "#identite-liasse" });
  if (editState.hash !== hash) {
    setEditState({ hash, editing: hash === "#identite-liasse" ? true : editState.editing });
  }
  const editing = editState.hash === hash ? editState.editing : hash === "#identite-liasse" || editState.editing;
  function setIdentity(update: (current: IdentityDraft) => IdentityDraft) {
    setIdentityState({ key: persistedKey, value: update(identity) });
  }
  function setEditing(next: boolean) {
    setEditState({ hash, editing: next });
  }
  const [formError, setFormError] = useState("");
  const [error, setError] = useState<RequestError | null>(null);
  const derived = sirenDerivedFromSiret(identity);
  const initializing = !setup.activity?.siren || setup.years.length === 0;
  const current: DeclarationStepId = setup.activity?.siren ? "exercice" : "siret";
  const showIdentityForm = !setup.activity || !setup.activity.siren || editing;
  const suggestion = setup.years.length === 0 ? suggestedExercise(setup.activity?.activity_start_date) : null;

  function goToProperty(note: string) {
    const state: GuideLocationState = { guideNote: note };
    navigate(PROPERTY_PATH, { state });
  }

  function saveIdentity(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const issue = identityIssue(identity);
    if (issue) {
      setFormError(issue);
      setError(null);
      return;
    }
    const data = new FormData(event.currentTarget);
    const activityName = String(data.get("name") ?? setup.activity?.activity_name ?? "").trim();
    const start = String(data.get("start") ?? "");
    const creating = !setup.activity;
    const sirenWasMissing = !setup.activity?.siren;
    const openProperty = sirenWasMissing && setup.years.length > 0;
    setFormError("");
    setError(null);
    let note = "";
    void run(async (report) => {
      report("Enregistrement de l’identité…");
      try {
        if (creating) {
          await request("/activity", "POST", {
            activity_name: activityName,
            activity_start_date: start,
            siren: identity.siren,
            siret: identity.siret || null,
          });
        } else {
          await request("/activity/identity", "POST", {
            siren: identity.siren,
            siret: identity.siret || null,
          });
        }
        setEditing(false);
        if (openProperty) {
          note = `SIREN ${identity.siren} enregistré. Indiquez le logement.`;
          return;
        }
        show({
          kind: creating ? "Activité" : GLOSSARY.siren.label,
          name: creating ? activityName : identity.siren,
          action: creating ? "créée" : "enregistré",
          targetId: "reglages-comptables",
          detail: setup.years.length === 0
            ? "L’exercice est l’étape suivante. Les dates sont proposées à partir du début d’activité."
            : "Identité enregistrée. Elle apparaîtra en tête de la liasse.",
          ...(setup.years.length === 0
            ? { next: { label: "Renseigner l’exercice", href: "#ajouter-exercice" } }
            : {}),
        });
        onReload();
      } catch (reason) {
        if (reason instanceof RequestError) setError(reason);
        else setFormError(reason instanceof Error ? reason.message : "Service indisponible.");
      }
    }).then(() => {
      if (note) goToProperty(note);
    });
  }

  function saveYear(input: { start: string; end: string; vintage: string }) {
    const first = setup.years.length === 0;
    const vintage = input.vintage || input.end.slice(0, 4);
    setFormError("");
    setError(null);
    let note = "";
    void run(async (report) => {
      report("Enregistrement de l’exercice…");
      try {
        await request("/years", "POST", {
          year: Number(input.end.slice(0, 4)),
          start_date: input.start,
          end_date: input.end,
          fiscal_vintage: input.vintage,
        });
        if (first) {
          note = `Exercice ${vintage} enregistré. Indiquez le logement.`;
          return;
        }
        show({
          kind: GLOSSARY.exercice.label,
          name: vintage,
          action: "créé",
          targetId: "reglages-comptables",
          detail: "Exercice créé.",
          next: { label: "Ajouter un bien", href: PROPERTY_PATH },
        });
        onReload();
      } catch (reason) {
        if (reason instanceof RequestError) setError(reason);
        else setFormError(reason instanceof Error ? reason.message : "Service indisponible.");
      }
    }).then(() => {
      if (note) goToProperty(note);
    });
  }

  return (
    <section className="declaration-guide" id="creer-activite" tabIndex={-1}>
      {initializing && (
        <>
          <DeclarationRail current={current} />
          <p className="form-help">
            Une étape à la fois. Le SIRET remplit le SIREN, puis l’exercice s’ouvre, puis le logement.
          </p>
        </>
      )}
      <div className="heading-with-help">
        <h3 id="identite-liasse" tabIndex={-1}>
          {setup.activity ? "Identité pour la liasse" : "Initialiser la déclaration"}
        </h3>
        <GlossaryTip id="liasse" />
        <GlossaryTip id="siren" />
      </div>
      {showIdentityForm ? (
        <FrenchForm onSubmit={saveIdentity}>
          {!setup.activity && (
            <p className="form-help">
              Le nom sert vos documents. La date est le début réel de l’activité, pas forcément le 1er janvier.
              Une activité déjà en cours se reprend ensuite par des à-nouveaux justifiés : cette initialisation ne reconstitue pas l’historique.
              <GlossaryTip id="a-nouveaux" />
            </p>
          )}
          <label>
            SIRET
            <input
              name="siret"
              inputMode="numeric"
              autoComplete="off"
              aria-describedby="siret-hint"
              value={identity.siret}
              onChange={(event) => {
                setFormError("");
                setIdentity((current) => identityFromSiret(event.target.value, current));
              }}
            />
          </label>
          <span id="siret-hint" className="field-hint">
            14 chiffres. Les 9 premiers deviennent le SIREN. Laissez vide si vous n’avez que le SIREN.
          </span>
          <label>
            SIREN
            <input
              name="siren"
              inputMode="numeric"
              autoComplete="off"
              aria-describedby={derived ? "siren-derived" : undefined}
              readOnly={derived}
              value={identity.siren}
              onChange={(event) => {
                setFormError("");
                setIdentity((current) => identityFromSiren(event.target.value, current));
              }}
            />
          </label>
          {derived && (
            <span id="siren-derived" className="field-hint">Repris des 9 premiers chiffres du SIRET.</span>
          )}
          {!setup.activity && (
            <>
              <label>Nom de l’activité<input name="name" required maxLength={200} autoComplete="organization" /></label>
              <label>
                Date réelle de début
                <FrenchDateInput name="start" required />
                <span className="field-hint">{DATE_HINT}</span>
              </label>
            </>
          )}
          <button disabled={busy}>{setup.activity ? "Enregistrer l’identité" : "Enregistrer et continuer"}</button>
          {editing && setup.activity?.siren && (
            <button type="button" onClick={() => setEditing(false)}>Annuler</button>
          )}
        </FrenchForm>
      ) : (
        <>
          <p>
            SIREN {setup.activity?.siren}
            {setup.activity?.siret ? ` · SIRET ${setup.activity.siret}` : " · SIRET non renseigné"}
          </p>
          <button type="button" onClick={() => setEditing(true)}>Modifier l’identité</button>
        </>
      )}
      {formError && <p role="alert" className="ledger-error">{formError}</p>}
      {error && <ApiErrorAlert detail={error.detail} />}
      <MutationStatus step={step} />
      {setup.activity?.siren && setup.years.length === 0 && (
        <div id="ajouter-exercice" tabIndex={-1}>
          <YearForm
            key={suggestion?.start ?? "exercice"}
            busy={busy}
            suggestion={suggestion}
            help="Dates proposées à partir du début d’activité, jusqu’au 31 décembre. Corrigez-les si l’exercice est différent."
            onCreate={saveYear}
          />
        </div>
      )}
      {setup.activity && setup.years.length > 0 && (
        <details id="ajouter-exercice" tabIndex={-1} open={hash === "#ajouter-exercice"}>
          <summary>{setup.activity.activity_name} · Ajouter un exercice</summary>
          <YearForm
            busy={busy}
            suggestion={null}
            help="L’exercice suivant a ses propres dates. La date de fin reste dans son année."
            onCreate={saveYear}
          />
        </details>
      )}
    </section>
  );
}
