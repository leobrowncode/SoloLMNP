import { AMOUNT_INPUT_ERROR, parseAmountToCents } from "./format";

const ERROR_CLASS = "field-error french-validation";

function patternMessage(field: HTMLInputElement): string {
  switch (field.pattern) {
    case "[0-9]{4}":
      return "Indiquez une année sur 4 chiffres.";
    case "[1-7][0-9]{2,9}":
      return "Indiquez un numéro de compte : un chiffre de 1 à 7, puis 2 à 9 chiffres.";
    case "[A-Z0-9]{2,10}":
      return "Indiquez 2 à 10 lettres majuscules ou chiffres.";
    default:
      return "Le format saisi n’est pas accepté.";
  }
}

function isField(value: EventTarget | null): value is HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement {
  return value instanceof HTMLInputElement || value instanceof HTMLSelectElement || value instanceof HTMLTextAreaElement;
}

function skipped(field: HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement): boolean {
  if (field.disabled) return true;
  if (!(field instanceof HTMLInputElement)) return false;
  return field.type === "hidden" || field.type === "button" || field.type === "submit" || field.type === "reset" || field.type === "radio";
}

export function frenchValidityMessage(field: HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement): string {
  if (skipped(field)) return "";
  const validity = field.validity;
  if (validity.valueMissing) {
    if (field instanceof HTMLInputElement && field.type === "checkbox") return "Cochez cette case pour continuer.";
    if (field instanceof HTMLInputElement && field.type === "file") return "Choisissez un fichier.";
    return "Ce champ est obligatoire.";
  }
  if (validity.customError) return field.validationMessage || "Corrigez ce champ.";
  if (field instanceof HTMLInputElement && field.type === "date" && (validity.badInput || validity.typeMismatch)) {
    return "Indiquez une date au format JJ/MM/AAAA.";
  }
  if (validity.patternMismatch && field instanceof HTMLInputElement) return patternMessage(field);
  if (validity.tooShort && "minLength" in field) return `Saisissez au moins ${field.minLength} caractères.`;
  if (validity.tooLong && "maxLength" in field) return `${field.maxLength} caractères maximum.`;
  if (validity.rangeUnderflow) {
    return field instanceof HTMLInputElement && field.type === "date"
      ? "Cette date est antérieure à la période autorisée."
      : "La valeur est inférieure au minimum.";
  }
  if (validity.rangeOverflow) {
    return field instanceof HTMLInputElement && field.type === "date"
      ? "Cette date est postérieure à la période autorisée."
      : "La valeur est supérieure au maximum.";
  }
  if (validity.stepMismatch) return "Indiquez un montant au centime près.";
  if (validity.typeMismatch) return "La valeur ne correspond pas au format attendu.";
  if (validity.badInput) return "La valeur saisie est incomplète.";
  if (field instanceof HTMLInputElement && field.dataset.money === "true" && field.value.trim()) {
    try {
      if (parseAmountToCents(field.value) < 0n) return AMOUNT_INPUT_ERROR;
    } catch {
      return AMOUNT_INPUT_ERROR;
    }
  }
  if (!validity.valid) return "Corrigez ce champ.";
  return "";
}

function clearField(field: HTMLElement) {
  const errorId = field.dataset.frenchError;
  if (errorId) document.getElementById(errorId)?.remove();
  if (field.dataset.frenchDescribed !== undefined) {
    const previous = field.dataset.frenchDescribed;
    if (previous) field.setAttribute("aria-describedby", previous);
    else field.removeAttribute("aria-describedby");
    delete field.dataset.frenchDescribed;
  }
  field.removeAttribute("aria-invalid");
  delete field.dataset.frenchError;
}

export function clearFrenchValidation(form: HTMLFormElement) {
  form.querySelectorAll<HTMLElement>("[data-french-error]").forEach(clearField);
  form.querySelectorAll(`.${ERROR_CLASS.split(" ").join(".")}`).forEach((node) => node.remove());
}

export function clearFrenchField(target: EventTarget | null) {
  if (isField(target)) clearField(target);
}

/** Show French messages and return true when the form can be submitted. */
export function showFrenchValidation(form: HTMLFormElement): boolean {
  clearFrenchValidation(form);
  const fields = [...form.querySelectorAll<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>("input, select, textarea")];
  let first: HTMLElement | null = null;
  let index = 0;
  for (const field of fields) {
    const message = frenchValidityMessage(field);
    if (!message) continue;
    const error = document.createElement("span");
    const errorId = `${field.id || field.name || "champ"}-fr-${index}`;
    index += 1;
    error.id = errorId;
    error.className = ERROR_CLASS;
    error.setAttribute("role", "alert");
    error.textContent = message;
    field.setAttribute("aria-invalid", "true");
    field.dataset.frenchDescribed = field.getAttribute("aria-describedby") ?? "";
    field.dataset.frenchError = errorId;
    const described = [field.dataset.frenchDescribed, errorId].filter(Boolean).join(" ");
    if (described) field.setAttribute("aria-describedby", described);
    const label = field.closest("label");
    if (label && !field.getAttribute("aria-label") && !field.getAttribute("aria-labelledby")) {
      const clone = label.cloneNode(true) as HTMLElement;
      clone.querySelectorAll("input, select, textarea, button, .field-hint, .field-error").forEach((node) => node.remove());
      const name = (clone.textContent ?? "").replace(/\s+/g, " ").trim();
      if (name) field.setAttribute("aria-label", name);
    }
    if (label) label.append(error);
    else field.insertAdjacentElement("afterend", error);
    first ??= field;
  }
  first?.focus();
  return first === null;
}
