import { Link } from "react-router-dom";
import { Card, CardTitle } from "../components/ui/card";

export default function AnneePlaceholder() {
  return (
    <Card>
      <CardTitle>3. Année</CardTitle>
      <p className="mt-2 text-sm text-[var(--color-muted-foreground)]">
        Import des charges et loyers : livré dans la PR suivante du jalon J4.
      </p>
      <Link className="mt-4 inline-flex text-sm text-[var(--color-primary)] underline" to="/v1/bien">
        Retour au bien
      </Link>
    </Card>
  );
}
