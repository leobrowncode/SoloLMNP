export type OutputTrust = "recherche" | "provisoire" | "declarable";

const LABELS: Record<OutputTrust, string> = {
  recherche: "Recherche",
  provisoire: "Provisoire",
  declarable: "Déclarable",
};

export function outputTrust(value: {
  output_status?: string;
  declarable?: boolean;
}): OutputTrust {
  if (
    value.output_status === "declarable"
    || value.output_status === "provisoire"
    || value.output_status === "recherche"
  ) {
    return value.output_status;
  }
  return value.declarable ? "declarable" : "recherche";
}

export function outputLabel(value: {
  output_label?: string;
  output_status?: string;
  declarable?: boolean;
}): string {
  if (value.output_label && value.output_label.trim()) return value.output_label;
  return LABELS[outputTrust(value)];
}

export function readyToCopy(value: {
  output_status?: string;
  declarable?: boolean;
}): boolean {
  return outputTrust(value) === "declarable";
}

export function calculationNotice(trust: OutputTrust): string {
  if (trust === "declarable") {
    return "Le millésime est validé. La liasse indique si la feuille peut être recopiée. Aucune télétransmission.";
  }
  if (trust === "provisoire") {
    return "Ce résultat n’est pas une base de déclaration. Aucune télétransmission.";
  }
  return "Ce calcul n’est pas une base de déclaration. Aucune télétransmission.";
}
