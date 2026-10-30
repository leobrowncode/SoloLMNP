import type { FormHTMLAttributes, SubmitEvent } from "react";
import { clearFrenchField, showFrenchValidation } from "./validation";

export default function FrenchForm({ onSubmit, onInput, ...props }: FormHTMLAttributes<HTMLFormElement>) {
  function submit(event: SubmitEvent<HTMLFormElement>) {
    if (!showFrenchValidation(event.currentTarget)) {
      event.preventDefault();
      return;
    }
    onSubmit?.(event);
  }

  return (
    <form
      {...props}
      noValidate
      onSubmit={submit}
      onInput={(event) => {
        clearFrenchField(event.target);
        onInput?.(event);
      }}
    />
  );
}
