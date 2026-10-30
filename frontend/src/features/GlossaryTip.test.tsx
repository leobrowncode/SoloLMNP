import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test } from "vitest";
import GlossaryTip from "./GlossaryTip";
import { GLOSSARY_IDS, GLOSSARY_PROMPTS, glossaryEntry } from "./glossary";

describe("glossary rendering", () => {
  test("opens the four parts through the help popover", async () => {
    const user = userEvent.setup();
    const { unmount } = render(<GlossaryTip id="extourne" />);
    const trigger = screen.getByRole("button", { name: "Aide : Extourne" });
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    await user.click(trigger);
    const panel = screen.getByRole("tooltip");
    expect(panel).toHaveTextContent(GLOSSARY_PROMPTS.what);
    expect(panel).toHaveTextContent(GLOSSARY_PROMPTS.why);
    expect(panel).toHaveTextContent(GLOSSARY_PROMPTS.example);
    expect(panel).toHaveTextContent(GLOSSARY_PROMPTS.mistake);
    expect(panel).toHaveTextContent(glossaryEntry("extourne").what);
    unmount();
  });

  test.each(GLOSSARY_IDS)("renders %s without claiming a filing", async (id) => {
    const user = userEvent.setup();
    const entry = glossaryEntry(id);
    const { unmount } = render(<GlossaryTip id={id} />);
    await user.click(screen.getByRole("button", { name: `Aide : ${entry.label}` }));
    const panel = screen.getByRole("tooltip");
    expect(panel).toHaveTextContent(entry.what);
    expect(panel).toHaveTextContent(entry.why);
    expect(panel).toHaveTextContent(entry.example);
    expect(panel).toHaveTextContent(entry.mistake);
    expect(panel).not.toHaveTextContent(/déclarable/i);
    unmount();
  });
});
