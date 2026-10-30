/** Announces the step in progress. Rendered only while a mutation is running. */
export default function MutationStatus({ step }: { step: string | null }) {
  if (!step) return null;
  return <p aria-live="polite">{step}</p>;
}
