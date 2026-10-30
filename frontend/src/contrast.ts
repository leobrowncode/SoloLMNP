export type Role = "text" | "large-text" | "ui" | "background" | "decorative" | "scrim";

export type Rgba = { r: number; g: number; b: number; a: number };

export type Token = {
  name: string;
  value: string;
  role: Role;
  color: Rgba | null;
};

export type Pair = {
  file: string;
  selector: string;
  property: string;
  fg: string;
  bg: string;
  ratio: number;
  need: number;
  kind: "text" | "ui" | "disabled";
};

export type Analysis = {
  tokens: Map<string, Token>;
  pairs: Pair[];
  violations: string[];
  stateViolations: string[];
  rawColorViolations: string[];
};

const ROLES = new Set<Role>(["text", "large-text", "ui", "background", "decorative", "scrim"]);

const TOKEN_RE = /--([\w-]+)\s*:\s*([^;]+?)\s*;\s*\/\*\s*role:\s*([\w-]+)\s*\*\//g;
const VAR_RE = /var\(\s*(--[\w-]+)\s*\)/g;
const HEX_RE = /#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b/g;
const COLOR_PROP = new Set(["color"]);
const BORDER_PROP = new Set([
  "border",
  "border-top",
  "border-right",
  "border-bottom",
  "border-left",
  "border-color",
]);
const OUTLINE_PROP = new Set(["outline", "outline-color"]);

export function parseColor(value: string): Rgba | null {
  const text = value.trim().toLowerCase();
  const hex = text.match(/^#([0-9a-f]{3}|[0-9a-f]{6}|[0-9a-f]{8})$/);
  if (hex?.[1]) {
    const raw = hex[1];
    const full = raw.length === 3 ? raw.split("").map((part) => part + part).join("") : raw;
    const r = Number.parseInt(full.slice(0, 2), 16);
    const g = Number.parseInt(full.slice(2, 4), 16);
    const b = Number.parseInt(full.slice(4, 6), 16);
    const a = full.length === 8 ? Number.parseInt(full.slice(6, 8), 16) / 255 : 1;
    return { r, g, b, a };
  }
  const rgb = text.match(/^rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*(?:,\s*([\d.]+)\s*)?\)$/);
  if (!rgb?.[1] || !rgb[2] || !rgb[3]) return null;
  return {
    r: Number(rgb[1]),
    g: Number(rgb[2]),
    b: Number(rgb[3]),
    a: rgb[4] === undefined ? 1 : Number(rgb[4]),
  };
}

function channel(value: number): number {
  const ratio = value / 255;
  return ratio <= 0.04045 ? ratio / 12.92 : ((ratio + 0.055) / 1.055) ** 2.4;
}

function luminance(color: Rgba): number {
  return 0.2126 * channel(color.r) + 0.7152 * channel(color.g) + 0.0722 * channel(color.b);
}

export function contrastRatio(foreground: Rgba, background: Rgba): number {
  const lighter = Math.max(luminance(foreground), luminance(background));
  const darker = Math.min(luminance(foreground), luminance(background));
  return (lighter + 0.05) / (darker + 0.05);
}

export function composite(foreground: Rgba, background: Rgba, opacity = 1): Rgba {
  const alpha = opacity * foreground.a;
  return {
    r: foreground.r * alpha + background.r * (1 - alpha),
    g: foreground.g * alpha + background.g * (1 - alpha),
    b: foreground.b * alpha + background.b * (1 - alpha),
    a: 1,
  };
}

export function parseTokens(css: string): Map<string, Token> {
  const tokens = new Map<string, Token>();
  for (const match of css.matchAll(TOKEN_RE)) {
    const name = `--${match[1]}`;
    const value = match[2]?.trim() ?? "";
    const role = match[3] as Role;
    if (!ROLES.has(role)) throw new Error(`Rôle de jeton inconnu pour ${name}: ${role}`);
    tokens.set(name, { name, value, role, color: parseColor(value) });
  }
  if (tokens.size < 20) throw new Error("Jetons de couleur introuvables dans tokens.css");
  return tokens;
}

type Rule = { file: string; selectors: string[]; decls: Record<string, string> };

function stripComments(css: string): string {
  return css.replace(/\/\*[\s\S]*?\*\//g, "");
}

function matchingBrace(css: string, open: number): number {
  let depth = 0;
  for (let index = open; index < css.length; index += 1) {
    if (css[index] === "{") depth += 1;
    else if (css[index] === "}") {
      depth -= 1;
      if (depth === 0) return index;
    }
  }
  throw new Error("Accolade CSS non fermée");
}

function splitTop(text: string, separator: string): string[] {
  const parts: string[] = [];
  let current = "";
  let depth = 0;
  for (const char of text) {
    if (char === "(" || char === "[") depth += 1;
    else if (char === ")" || char === "]") depth -= 1;
    if (char === separator && depth === 0) {
      parts.push(current);
      current = "";
    } else current += char;
  }
  if (current.trim()) parts.push(current);
  return parts;
}

function declarations(body: string): Record<string, string> {
  const decls: Record<string, string> = {};
  for (const part of splitTop(body, ";")) {
    const index = part.indexOf(":");
    if (index === -1) continue;
    const prop = part.slice(0, index).trim().toLowerCase();
    const value = part.slice(index + 1).replace(/\s*!important\s*/g, " ").trim();
    if (prop) decls[prop] = value;
  }
  return decls;
}

function extractRules(file: string, css: string): Rule[] {
  const source = stripComments(css);
  const rules: Rule[] = [];
  const walk = (text: string, end: number, cursor: { i: number }) => {
    while (cursor.i < end) {
      while (cursor.i < end && /\s/.test(text[cursor.i] ?? "")) cursor.i += 1;
      if (cursor.i >= end) return;
      if (text.startsWith("@import", cursor.i)) {
        const stop = text.indexOf(";", cursor.i);
        cursor.i = stop === -1 ? end : stop + 1;
        continue;
      }
      if (text[cursor.i] === "@") {
        const open = text.indexOf("{", cursor.i);
        const semi = text.indexOf(";", cursor.i);
        if (open === -1 || (semi !== -1 && semi < open)) {
          cursor.i = semi === -1 ? end : semi + 1;
          continue;
        }
        const prelude = text.slice(cursor.i, open);
        const close = matchingBrace(text, open);
        if (/@media|@supports/.test(prelude)) walk(text, close, { i: open + 1 });
        cursor.i = close + 1;
        continue;
      }
      const open = text.indexOf("{", cursor.i);
      if (open === -1 || open >= end) return;
      const selector = text.slice(cursor.i, open).trim();
      const close = matchingBrace(text, open);
      if (selector && !selector.startsWith("@")) {
        rules.push({
          file,
          selectors: splitTop(selector, ",").map((item) => item.trim()).filter(Boolean),
          decls: declarations(text.slice(open + 1, close)),
        });
      }
      cursor.i = close + 1;
    }
  };
  walk(source, source.length, { i: 0 });
  return rules;
}

function normalize(selector: string): string {
  return selector.replace(/\s+/g, " ").replace(/\s*>\s*/g, " > ").trim();
}

function varsIn(value: string | undefined): string[] {
  if (!value) return [];
  return [...value.matchAll(VAR_RE)].map((match) => match[1] ?? "").filter(Boolean);
}

function merged(rules: Rule[], selector: string): Record<string, string> {
  const key = normalize(selector);
  const decls: Record<string, string> = {};
  for (const rule of rules) {
    if (rule.selectors.some((item) => normalize(item) === key)) Object.assign(decls, rule.decls);
  }
  return decls;
}

function candidates(selector: string): string[] {
  const found: string[] = [];
  const push = (value: string) => {
    const next = normalize(value);
    if (next && !found.includes(next)) found.push(next);
  };
  push(selector);
  let current = selector;
  for (const pattern of [
    /:focus-visible|:hover|:active|:disabled/g,
    /:not\([^)]*\)/g,
    /\[aria-pressed="true"\]/g,
    /\.nav-active|\.nav-current/g,
  ]) {
    current = current.replace(pattern, "");
    push(current);
  }
  current = normalize(current);
  while (current) {
    const next = current.replace(/\s*(?:>|\+)\s*[^\s>+]+$|\s+[^\s>+]+$/, "").trim();
    if (!next || next === current) break;
    push(next);
    current = next;
  }
  return found;
}

function firstToken(rules: Rule[], selector: string, props: Set<string>): string | undefined {
  for (const candidate of candidates(selector)) {
    const decls = merged(rules, candidate);
    for (const prop of props) {
      const token = varsIn(decls[prop])[0];
      if (token) return token;
    }
  }
  return undefined;
}

function opacityOf(rules: Rule[], selector: string): number {
  for (const candidate of candidates(selector)) {
    const value = merged(rules, candidate).opacity;
    if (value) return Number(value);
  }
  return 1;
}

function hasOffset(rules: Rule[], selector: string): boolean {
  return candidates(selector).some((candidate) => Boolean(merged(rules, candidate)["outline-offset"]));
}

const VARIANT_SUFFIX = /-(good|warn|warning|error|info|provisoire|bloquee|finale|obsolete|declarable|neutral|recherche|valid|duplicate)$/;

function variantSelectors(rules: Rule[], backgroundSelector: string): string[] {
  if (!/^\.[A-Za-z0-9_-]+$/.test(backgroundSelector)) return [];
  const base = backgroundSelector.slice(1);
  const found = new Set<string>();
  for (const rule of rules) {
    for (const selector of rule.selectors) {
      if (!/^\.[A-Za-z0-9_-]+$/.test(selector)) continue;
      const name = selector.slice(1);
      if (name.startsWith(`${base}-`) && VARIANT_SUFFIX.test(name) && varsIn(rule.decls.background ?? rule.decls["background-color"])[0]) {
        found.add(selector);
      }
    }
  }
  return [...found];
}

function rawColors(file: string, css: string): string[] {
  const source = stripComments(css);
  const hits = [
    ...(source.match(HEX_RE) ?? []),
    ...(source.match(/rgba?\(/gi) ?? []),
    ...(source.match(/(?<![\w-])white(?![\w-])/gi) ?? []),
  ];
  return hits.map((hit) => `${file}: couleur brute ${hit}`);
}

function needFor(role: Role, disabled: boolean): number {
  if (disabled) return 3;
  if (role === "large-text" || role === "ui") return 3;
  return 4.5;
}

export function analyze(tokensCss: string, sheets: { file: string; css: string }[]): Analysis {
  const tokens = parseTokens(tokensCss);
  const rules = sheets.flatMap((sheet) => extractRules(sheet.file, sheet.css));
  const pairs: Pair[] = [];
  const violations: string[] = [];
  const stateViolations: string[] = [];
  const rawColorViolations = sheets.flatMap((sheet) => rawColors(sheet.file, sheet.css));
  const rootBg = tokens.get("--bg-canvas");
  const rootFg = tokens.get("--text-body");
  if (!rootBg?.color || !rootFg?.color) throw new Error("Jetons --bg-canvas et --text-body requis");

  const paint = (file: string, selector: string, fgName: string, bgName: string, property: string, disabled: boolean) => {
    const fg = tokens.get(fgName);
    const bg = tokens.get(bgName);
    if (!fg || !bg) {
      violations.push(`${file}: jeton inconnu dans ${selector}`);
      return;
    }
    if (!fg.color || !bg.color) {
      violations.push(`${file}: ${selector} utilise ${fgName} / ${bgName}, qui n’est pas une couleur simple`);
      return;
    }
    const opacity = disabled ? opacityOf(rules, selector) : 1;
    const foreground = composite(fg.color, bg.color, Number.isFinite(opacity) ? opacity : 1);
    const ratio = contrastRatio(foreground, bg.color);
    const kind = disabled ? "disabled" : fg.role === "ui" ? "ui" : "text";
    const need = needFor(fg.role, disabled);
    const pair: Pair = { file, selector, property, fg: fgName, bg: bgName, ratio, need, kind };
    pairs.push(pair);
    if (ratio + 1e-6 < need) {
      violations.push(
        `${file} ${selector} ${property}: ${fgName} sur ${bgName} = ${ratio.toFixed(2)}:1, minimum ${need}:1`,
      );
    }
  };

  const resolveBg = (selector: string): { token: string; selector: string } | undefined => {
    for (const candidate of candidates(selector)) {
      const decls = merged(rules, candidate);
      const token = varsIn(decls.background ?? decls["background-color"])[0];
      if (!token) continue;
      const role = tokens.get(token)?.role;
      if (role === "background") return { token, selector: candidate };
    }
    return { token: "--bg-canvas", selector: ":root" };
  };

  for (const rule of rules) {
    for (const selector of rule.selectors) {
      const colorToken = varsIn(rule.decls.color)[0];
      const bgToken = varsIn(rule.decls.background ?? rule.decls["background-color"])[0];
      const disabled = selector.includes(":disabled");
      if (colorToken) {
        const role = tokens.get(colorToken)?.role;
        if (role !== "text" && role !== "large-text") {
          violations.push(`${rule.file} ${selector}: color utilise ${colorToken} (${role ?? "absent"}) au lieu d’un texte`);
        }
        const background = resolveBg(selector);
        if (background && tokens.get(background.token)?.role === "background") {
          paint(rule.file, selector, colorToken, background.token, "color", disabled);
          for (const variant of variantSelectors(rules, background.selector)) {
            const variantBg = varsIn(merged(rules, variant).background)[0];
            if (variantBg) paint(rule.file, `${selector} @ ${variant}`, colorToken, variantBg, "color", disabled);
          }
        }
      }
      if (bgToken) {
        const role = tokens.get(bgToken)?.role;
        if (role === "ui") {
          const parentSelector = candidates(selector)[1];
          const adjacent = (parentSelector ? resolveBg(parentSelector) : undefined)?.token ?? "--bg-canvas";
          paint(rule.file, selector, bgToken, adjacent, "background", false);
        } else if (role !== "background" && role !== "scrim") {
          violations.push(`${rule.file} ${selector}: background utilise ${bgToken} (${role ?? "absent"})`);
        } else if (role === "background" && !colorToken) {
          const inherited = firstToken(rules, selector, COLOR_PROP) ?? "--text-body";
          paint(rule.file, selector, inherited, bgToken, "background-text", selector.includes(":disabled"));
        }
      }
      for (const prop of BORDER_PROP) {
        for (const token of varsIn(rule.decls[prop])) {
          const role = tokens.get(token)?.role;
          if (role === "decorative") continue;
          if (role !== "ui") {
            violations.push(`${rule.file} ${selector}: ${prop} utilise ${token} (${role ?? "absent"})`);
            continue;
          }
          const element = resolveBg(selector);
          const parentCandidate = candidates(selector)[1];
          const parent = parentCandidate ? resolveBg(parentCandidate) : undefined;
          const targets = new Set<string>();
          if (element) targets.add(element.token);
          if (parent) targets.add(parent.token);
          if (targets.size === 0) targets.add("--bg-canvas");
          for (const target of targets) paint(rule.file, selector, token, target, prop, false);
        }
      }
      for (const prop of OUTLINE_PROP) {
        for (const token of varsIn(rule.decls[prop])) {
          const role = tokens.get(token)?.role;
          if (role !== "ui") {
            violations.push(`${rule.file} ${selector}: ${prop} utilise ${token} (${role ?? "absent"})`);
            continue;
          }
          const parentCandidate = hasOffset(rules, selector) ? candidates(selector)[1] : selector;
          const adjacent = (parentCandidate ? resolveBg(parentCandidate) : undefined)?.token ?? "--bg-canvas";
          paint(rule.file, selector, token, adjacent, prop, false);
        }
      }
      if (disabled) {
        const color = colorToken ?? firstToken(rules, selector, COLOR_PROP) ?? "--text-body";
        const background = bgToken ?? resolveBg(selector)?.token ?? "--bg-canvas";
        if (tokens.get(background)?.role === "background" && opacityOf(rules, selector) < 1) {
          paint(rule.file, selector, color, background, "disabled", true);
        }
      }
    }
  }

  const disabledOpacity = opacityOf(rules, "button:disabled");
  if (!(disabledOpacity < 1)) stateViolations.push("button:disabled ne réduit pas l’opacité");
  for (const rule of rules) {
    for (const selector of rule.selectors) {
      if (!/button|nav-toggle|help-tip-btn/.test(selector)) continue;
      if (/:hover|:active|:focus|:disabled/.test(selector)) continue;
      const color = varsIn(rule.decls.color)[0];
      const background = resolveBg(selector);
      if (!color || !background) continue;
      const fg = tokens.get(color);
      const bg = tokens.get(background.token);
      if (!fg?.color || !bg?.color) continue;
      const ratio = contrastRatio(composite(fg.color, bg.color, disabledOpacity), bg.color);
      if (ratio + 1e-6 < 3) {
        violations.push(`${rule.file} ${selector} désactivé: ${color} sur ${background.token} = ${ratio.toFixed(2)}:1, minimum 3:1`);
      }
    }
  }

  const stateMarker = /:hover|:focus-visible|:focus\b|:active|:disabled|\.nav-active|\.nav-current|\[aria-pressed="true"\]/;
  for (const rule of rules) {
    for (const selector of rule.selectors) {
      if (!stateMarker.test(selector)) continue;
      const baseName = normalize(
        selector
          .replace(/:focus-visible/g, "")
          .replace(/:focus\b/g, "")
          .replace(/:hover|:active|:disabled/g, "")
          .replace(/:not\([^)]*\)/g, "")
          .replace(/\[aria-pressed="true"\]/g, "")
          .replace(/\.nav-active|\.nav-current/g, ""),
      );
      const base = baseName ? merged(rules, baseName) : {};
      const overlay = { ...base, ...rule.decls };
      const keys = new Set([...Object.keys(base), ...Object.keys(rule.decls)]);
      const differs = [...keys].some((key) => (overlay[key] ?? "") !== (base[key] ?? ""));
      if (!differs) {
        stateViolations.push(`${rule.file} ${selector} ne se distingue pas de ${baseName || "l’état repos"}`);
      }
    }
  }

  const distinct: [string, string][] = [
    ["--bg-button", "--bg-button-hover"],
    ["--bg-button-hover", "--bg-nav-active"],
    ["--bg-nav-hover", "--bg-nav-active"],
    ["--bg-nav-hover", "--bg-surface"],
    ["--bg-accent", "--bg-brand"],
    ["--bg-accent", "--bg-inverse"],
    ["--text-muted", "--text-nav-active"],
    ["--focus-ring", "--bg-canvas"],
  ];
  for (const [left, right] of distinct) {
    if (tokens.get(left)?.value === tokens.get(right)?.value) {
      stateViolations.push(`${left} et ${right} ont la même couleur`);
    }
  }

  return { tokens, pairs, violations, stateViolations, rawColorViolations };
}
