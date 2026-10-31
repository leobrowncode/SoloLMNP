import type { ReactNode } from "react";
import { TABLE_CARD_QUERY, useMediaQuery } from "./viewport";

export type ResponsiveColumn = {
  key: string;
  label: string;
  header?: ReactNode;
  priority?: "primary" | "secondary";
};

function columnIndex(columns: ResponsiveColumn[], key: string): number {
  return columns.findIndex((column) => column.key === key);
}

function Cell({
  column,
  value,
  priority,
}: {
  column: ResponsiveColumn;
  value: ReactNode;
  priority: "primary" | "secondary";
}) {
  return (
    <p data-priority={priority}>
      <span className="card-label">{column.header ?? column.label}</span>
      <span className="card-value">{value}</span>
    </p>
  );
}

/**
 * Desktop: the same table as before.
 * Narrow: one card per row. Primary columns stay visible; the others sit
 * under « Autres colonnes », named in the priority line.
 */
export function ResponsiveTable({
  caption,
  columns,
  rows,
  footerRow,
  footerNote,
  label,
}: {
  caption?: ReactNode;
  columns: ResponsiveColumn[];
  rows: { key: string; cells: ReactNode[]; className?: string }[];
  footerRow?: ReactNode;
  footerNote?: ReactNode;
  label: string;
}) {
  const mobile = useMediaQuery(TABLE_CARD_QUERY);
  const primary = columns.filter((column) => (column.priority ?? "primary") === "primary");
  const secondary = columns.filter((column) => column.priority === "secondary");

  if (mobile) {
    return (
      <div className="mobile-table" data-mobile-variant="cards" data-table={label}>
        {caption ? <p className="mobile-table-caption">{caption}</p> : null}
        <p className="mobile-table-priority">
          Colonnes principales : {primary.map((column) => column.label).join(", ")}.
        </p>
        {secondary.length > 0 ? (
          <p className="mobile-table-secondary">
            Autres colonnes : {secondary.map((column) => column.label).join(", ")}.
          </p>
        ) : null}
        <ul className="mobile-cards" aria-label={label}>
          {rows.map((row) => (
            <li key={row.key} className={["mobile-card", row.className].filter(Boolean).join(" ")}>
              {primary.map((column) => (
                <Cell
                  key={column.key}
                  column={column}
                  priority="primary"
                  value={row.cells[columnIndex(columns, column.key)]}
                />
              ))}
              {secondary.length > 0 ? (
                <details className="mobile-card-more">
                  <summary>Autres colonnes</summary>
                  {secondary.map((column) => (
                    <Cell
                      key={column.key}
                      column={column}
                      priority="secondary"
                      value={row.cells[columnIndex(columns, column.key)]}
                    />
                  ))}
                </details>
              ) : null}
            </li>
          ))}
        </ul>
        {footerNote ? <p className="mobile-table-footer">{footerNote}</p> : null}
      </div>
    );
  }

  return (
    <div className="ledger-table" data-mobile-variant="table">
      <table>
        {caption ? <caption>{caption}</caption> : null}
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.key}>{column.header ?? column.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.key} className={row.className}>
              {row.cells.map((cell, index) => (
                <td key={columns[index]?.key ?? index}>{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
        {footerRow ? <tfoot>{footerRow}</tfoot> : null}
      </table>
    </div>
  );
}
