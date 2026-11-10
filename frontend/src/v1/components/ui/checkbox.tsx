import type { InputHTMLAttributes } from "react";
import { cn } from "../../lib/cn";

type Props = Omit<InputHTMLAttributes<HTMLInputElement>, "type">;

export function Checkbox({ className, ...props }: Props) {
  return (
    <input
      type="checkbox"
      className={cn("h-4 w-4 rounded border-[var(--color-border)] accent-[var(--color-primary)]", className)}
      {...props}
    />
  );
}
