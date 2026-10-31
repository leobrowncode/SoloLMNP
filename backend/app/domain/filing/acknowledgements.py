"""Match pré-contrôle acknowledgements to the warnings on screen.

A code is enough when it appears once. The same code with two messages
(CLASSEMENT_INCOMPLET on 2033-A and 2033-E) needs one token per line,
``code`` plus a newline plus the message. Sending the code once does not
acknowledge both.
"""

from collections.abc import Mapping, Sequence


def warning_token(item: Mapping[str, object]) -> str:
    code = str(item.get("code", ""))
    message = str(item.get("message", "")).strip()
    if not message:
        return code
    return f"{code}\n{message}"


def acknowledgements_match(
    warnings: Sequence[Mapping[str, object]], acknowledged: Sequence[str]
) -> bool:
    if len(acknowledged) != len(warnings):
        return False
    tokens = [warning_token(item) for item in warnings]
    if sorted(acknowledged) == sorted(tokens):
        return True
    codes = [str(item.get("code", "")) for item in warnings]
    return len(set(codes)) == len(codes) and sorted(acknowledged) == sorted(codes)
