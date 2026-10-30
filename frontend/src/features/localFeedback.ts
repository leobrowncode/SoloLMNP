/**
 * Precise acknowledgement after a save.
 * The sentence names the object, the action and the time it was taken into account.
 */
import { useCallback, useState } from "react";
import { formatClockTime } from "../lib/format";

export const SAVE_NOTICE_MS = 10_000;

export interface SaveNextAction {
  label: string;
  href?: string;
  onClick?: () => void;
}

export interface SaveNotice {
  id: string;
  text: string;
  /** Element that contains the message when the created row is not in the document yet. */
  targetId: string;
  /** Created or modified element. The message moves there once it is mounted. */
  highlightId?: string | undefined;
  /**
   * Focus that element. Only when the user should continue in that control.
   * The live region itself is never focused.
   */
  focus?: boolean | undefined;
  /** Extra sentence kept in the live region (counts, invalidation, empreinte). */
  detail?: string | undefined;
  next?: SaveNextAction | undefined;
}

export interface ShowSaveNotice {
  kind: string;
  name: string;
  /** Past participle, already agreed: « créée », « modifié », « enregistrée ». */
  action: string;
  at?: Date;
  targetId: string;
  highlightId?: string | undefined;
  focus?: boolean | undefined;
  detail?: string | undefined;
  next?: SaveNextAction | undefined;
}

export function saveFeedbackText(input: {
  kind: string;
  name: string;
  action: string;
  at?: Date;
}): string {
  const time = formatClockTime(input.at ?? new Date());
  return `${input.kind} “${input.name}” ${input.action} à ${time}`;
}

export function useSaveNotice() {
  const [notice, setNotice] = useState<SaveNotice | null>(null);
  const show = useCallback((input: ShowSaveNotice) => {
    const at = input.at ?? new Date();
    setNotice({
      id: crypto.randomUUID(),
      text: saveFeedbackText({ kind: input.kind, name: input.name, action: input.action, at }),
      targetId: input.targetId,
      highlightId: input.highlightId,
      focus: input.focus,
      detail: input.detail,
      next: input.next,
    });
  }, []);
  const dismiss = useCallback(() => setNotice(null), []);
  return { notice, show, dismiss };
}
