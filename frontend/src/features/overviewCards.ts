import type { DashboardAction, DashboardPrerequisite, DashboardStep, DashboardStepId } from "../api/dashboard";

export interface StepCardView {
  statusLabel: string;
  summary: string | null;
  showEvent: boolean;
  missing: DashboardPrerequisite[];
  actions: DashboardAction[];
}

function remember(actions: DashboardAction[], action: DashboardAction) {
  if (actions.some((item) => item.href === action.href && item.label === action.label)) return;
  actions.push(action);
}

/** Une ligne d’état par carte. La phrase de l’étape en cours n’est pas recopiée. */
export function presentStep(
  step: DashboardStep,
  context: {
    sharedSummary: string;
    currentStep: DashboardStepId;
  },
): StepCardView {
  const showSummary = step.id === context.currentStep || step.summary !== context.sharedSummary;
  const view = {
    statusLabel: step.status_label,
    summary: showSummary ? step.summary : null,
    showEvent: step.last_event !== null,
  };
  if (step.status === "a_faire") {
    return { ...view, missing: [], actions: [] };
  }
  const missing: DashboardPrerequisite[] = [];
  const actions: DashboardAction[] = [];
  for (const item of step.prerequisites) {
    const repeated = item.message === step.summary || item.message === context.sharedSummary;
    if (repeated) {
      remember(actions, item.action);
      continue;
    }
    missing.push(item);
  }
  return { ...view, missing, actions };
}
