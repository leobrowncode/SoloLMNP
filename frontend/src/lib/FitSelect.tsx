import { useLayoutEffect, useRef, useState, type SelectHTMLAttributes } from "react";
import { NARROW_CONTROL_QUERY, useMediaQuery } from "./viewport";

function selectedText(select: HTMLSelectElement): string {
  return select.selectedOptions[0]?.textContent?.replace(/\s+/g, " ").trim() ?? "";
}

/**
 * Native select, plus the full selected label when the viewport is 320–430 px.
 * The extra label wraps, so the closed control is not the only copy of a long value.
 * On wider screens the wrapper is `display: contents` and adds no box.
 */
export default function FitSelect({ children, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  const narrow = useMediaQuery(NARROW_CONTROL_QUERY);
  const ref = useRef<HTMLSelectElement>(null);
  const [text, setText] = useState("");

  useLayoutEffect(() => {
    const select = ref.current;
    if (!select) return;
    const sync = () => setText(selectedText(select));
    sync();
    select.addEventListener("change", sync);
    return () => select.removeEventListener("change", sync);
  });

  return (
    <span className="fit-select">
      <select ref={ref} {...props} title={narrow && text ? text : props.title}>
        {children}
      </select>
      {narrow && text ? (
        <span className="select-full-value" aria-hidden="true">{text}</span>
      ) : null}
    </span>
  );
}
