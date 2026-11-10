"""Sous-ensemble YAML : maps, listes, scalaires. Pas d'ancre, pas de multiligne."""

from __future__ import annotations


def loads(text: str) -> object:
    lines: list[tuple[int, str, int]] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if "\t" in raw[: len(raw) - len(raw.lstrip(" \t"))]:
            raise ValueError(f"Ligne {number} : indentation par espaces uniquement.")
        indent = len(raw) - len(raw.lstrip(" "))
        lines.append((indent, raw.strip(), number))
    if not lines:
        raise ValueError("Document vide.")
    value, index = _node(lines, 0, lines[0][0])
    if index != len(lines):
        raise ValueError(f"Ligne {lines[index][2]} : contenu inattendu.")
    return value


def _node(
    lines: list[tuple[int, str, int]], index: int, indent: int
) -> tuple[object, int]:
    _ind, text, _number = lines[index]
    if text.startswith("- "):
        return _list(lines, index, indent)
    return _map(lines, index, indent)


def _map(
    lines: list[tuple[int, str, int]], index: int, indent: int
) -> tuple[dict[str, object], int]:
    result: dict[str, object] = {}
    while index < len(lines):
        ind, text, number = lines[index]
        if ind < indent:
            break
        if ind != indent or text.startswith("- "):
            raise ValueError(f"Ligne {number} : map attendue.")
        key, sep, rest = text.partition(":")
        if not sep or not key.strip():
            raise ValueError(f"Ligne {number} : clé attendue.")
        key = key.strip()
        index += 1
        if rest.strip():
            result[key] = _scalar(rest.strip(), number)
            continue
        if index < len(lines) and lines[index][0] > indent:
            child, index = _node(lines, index, lines[index][0])
            result[key] = child
        else:
            result[key] = None
    return result, index


def _list(
    lines: list[tuple[int, str, int]], index: int, indent: int
) -> tuple[list[object], int]:
    items: list[object] = []
    while index < len(lines):
        ind, text, number = lines[index]
        if ind < indent:
            break
        if ind != indent or not text.startswith("- "):
            break
        body = text[2:].strip()
        index += 1
        if body == "":
            if index >= len(lines):
                raise ValueError(f"Ligne {number} : élément de liste vide.")
            child, index = _node(lines, index, lines[index][0])
            items.append(child)
            continue
        if ":" not in body:
            items.append(_scalar(body, number))
            continue
        key, _, rest = body.partition(":")
        item: dict[str, object] = {}
        if rest.strip():
            item[key.strip()] = _scalar(rest.strip(), number)
        else:
            item[key.strip()] = None
        child_indent = indent + 2
        while index < len(lines):
            ind, text, number = lines[index]
            if ind != child_indent or text.startswith("- "):
                break
            field, sep, field_rest = text.partition(":")
            if not sep:
                raise ValueError(f"Ligne {number} : clé attendue.")
            index += 1
            if field_rest.strip():
                item[field.strip()] = _scalar(field_rest.strip(), number)
            elif index < len(lines) and lines[index][0] > child_indent:
                child, index = _node(lines, index, lines[index][0])
                item[field.strip()] = child
            else:
                item[field.strip()] = None
        items.append(item)
    return items, index


def _scalar(text: str, number: int) -> object:
    if text in {"true", "false"}:
        return text == "true"
    if text in {"null", "~"}:
        return None
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        return text[1:-1]
    if text.lstrip("-").isdigit():
        return int(text)
    if any(char in text for char in ":#"):
        raise ValueError(f"Ligne {number} : scalaire à citer ({text!r}).")
    return text
