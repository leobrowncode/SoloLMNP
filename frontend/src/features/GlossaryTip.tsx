import type { ReactNode } from "react";
import HelpTip from "./HelpTip";
import { GLOSSARY_PROMPTS, glossaryEntry, type GlossaryId } from "./glossary";

export function GlossaryText({ id }: { id: GlossaryId }): ReactNode {
  const entry = glossaryEntry(id);
  return (
    <span className="glossary-body">
      <span className="glossary-part">
        <span className="glossary-k">{GLOSSARY_PROMPTS.what}</span>
        <span>{entry.what}</span>
      </span>
      <span className="glossary-part">
        <span className="glossary-k">{GLOSSARY_PROMPTS.why}</span>
        <span>{entry.why}</span>
      </span>
      <span className="glossary-part">
        <span className="glossary-k">{GLOSSARY_PROMPTS.example}</span>
        <span>{entry.example}</span>
      </span>
      <span className="glossary-part">
        <span className="glossary-k">{GLOSSARY_PROMPTS.mistake}</span>
        <span>{entry.mistake}</span>
      </span>
    </span>
  );
}

export default function GlossaryTip({ id, label }: { id: GlossaryId; label?: string }) {
  const entry = glossaryEntry(id);
  return (
    <HelpTip label={label ?? entry.label}>
      <GlossaryText id={id} />
    </HelpTip>
  );
}
