import { useState, type InputHTMLAttributes } from "react";
import { DATE_PLACEHOLDER } from "./format";

type Props = Omit<InputHTMLAttributes<HTMLInputElement>, "type" | "lang">;

/** Date field whose empty mask matches the French hint JJ/MM/AAAA. */
export default function FrenchDateInput({
  className,
  value,
  defaultValue,
  onChange,
  ...rest
}: Props) {
  const controlled = value !== undefined;
  const [uncontrolledFilled, setUncontrolledFilled] = useState(
    defaultValue !== undefined && String(defaultValue) !== "",
  );
  const empty = controlled ? String(value ?? "") === "" : !uncontrolledFilled;
  const classes = [empty ? "date-empty" : "", className].filter(Boolean).join(" ");
  return (
    <div className="date-control">
      <input
        {...rest}
        type="date"
        lang="fr"
        className={classes || undefined}
        {...(controlled ? { value: value ?? "" } : {})}
        {...(!controlled && defaultValue !== undefined ? { defaultValue } : {})}
        onChange={(event) => {
          if (!controlled) setUncontrolledFilled(event.currentTarget.value !== "");
          onChange?.(event);
        }}
      />
      {empty ? <span className="date-placeholder" aria-hidden="true">{DATE_PLACEHOLDER}</span> : null}
    </div>
  );
}
