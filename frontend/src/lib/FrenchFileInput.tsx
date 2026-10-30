import { useId, useState, type ChangeEvent, type Ref } from "react";

export default function FrenchFileInput({
  label,
  labelledBy,
  accept,
  inputRef,
  disabled,
  onChange,
}: {
  label?: string;
  labelledBy?: string;
  accept?: string;
  inputRef?: Ref<HTMLInputElement>;
  disabled?: boolean;
  onChange?: (event: ChangeEvent<HTMLInputElement>) => void;
}) {
  const autoId = useId();
  const captionId = `${autoId}-caption`;
  const [name, setName] = useState<string | null>(null);
  return (
    <div className="file-picker">
      {label ? <span id={captionId} className="file-picker-caption">{label}</span> : null}
      <input
        id={autoId}
        ref={inputRef}
        className="file-picker-native"
        type="file"
        accept={accept}
        disabled={disabled}
        aria-labelledby={labelledBy ?? (label ? captionId : undefined)}
        onChange={(event) => {
          setName(event.target.files?.[0]?.name ?? null);
          onChange?.(event);
        }}
      />
      <label htmlFor={autoId} className="file-picker-button">Choisir un fichier</label>
      <span className="file-picker-name">{name ?? "Aucun fichier choisi"}</span>
    </div>
  );
}
