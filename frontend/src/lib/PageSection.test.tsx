import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MobileSection } from "./PageSection";

function queryMatches(query: string, width: number): boolean {
  return query.split(/\s+and\s+/i).every((part) => {
    const max = /max-width:\s*(\d+)px/.exec(part);
    if (max) return width <= Number(max[1]);
    const min = /min-width:\s*(\d+)px/.exec(part);
    if (min) return width >= Number(min[1]);
    return false;
  });
}

function installViewport(initialWidth: number) {
  let width = initialWidth;
  const listeners: Array<() => void> = [];
  vi.stubGlobal("matchMedia", (query: string) => ({
    get matches() {
      return queryMatches(query, width);
    },
    media: query,
    onchange: null,
    addEventListener: (_type: string, handler: () => void) => {
      listeners.push(handler);
    },
    removeEventListener: (_type: string, handler: () => void) => {
      const index = listeners.indexOf(handler);
      if (index >= 0) listeners.splice(index, 1);
    },
    dispatchEvent: () => false,
  }));
  return {
    resize(to: number) {
      width = to;
      for (const handler of listeners) handler();
    },
  };
}

function SectionWithInput() {
  const [value, setValue] = useState("");
  return (
    <MobileSection id="test-section" title="Réglages comptables" open>
      <label htmlFor="siret-test">
        SIRET
        <input id="siret-test" value={value} onChange={(event) => setValue(event.target.value)} />
      </label>
    </MobileSection>
  );
}

describe("MobileSection", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it("keeps the same details element on wide and narrow viewports", () => {
    installViewport(1200);
    render(
      <MobileSection id="wide" title="Section">
        <p>contenu</p>
      </MobileSection>,
    );
    const node = document.getElementById("wide");
    expect(node?.tagName).toBe("DETAILS");
    expect(node).toHaveClass("mobile-section--wide");
    expect(screen.getByText("contenu")).toBeVisible();
  });

  it("preserves child input when the viewport crosses the mobile threshold", async () => {
    const viewport = installViewport(1200);
    render(<SectionWithInput />);
    expect(document.getElementById("test-section")).toHaveClass("mobile-section--wide");

    const input = screen.getByLabelText("SIRET");
    await userEvent.type(input, "12345678900019");
    expect(input).toHaveValue("12345678900019");

    await act(async () => {
      viewport.resize(390);
    });
    expect(document.getElementById("test-section")).toHaveClass("mobile-section--narrow");
    expect(screen.getByLabelText("SIRET")).toHaveValue("12345678900019");

    await act(async () => {
      viewport.resize(1200);
    });
    expect(screen.getByLabelText("SIRET")).toHaveValue("12345678900019");
  });
});
