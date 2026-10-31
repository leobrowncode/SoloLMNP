"""Result accounts 120 and 129 are the exercise result, not other equity."""


def is_result_account(number: str) -> bool:
    """120 and 129 carry the unallocated result. 1209 is a down payment on dividends."""
    if number.startswith("1209"):
        return False
    return number.startswith("120") or number.startswith("129")


def still_held(closed_result: int, balances: dict[str, int]) -> dict[str, int]:
    """Credit-positive part of a closed result that each account still carries.

    ``closed_result`` is the class 6/7 result moved by centralization.
    ``balances`` are the credit-positive balances of the result accounts.
    The returned amount never exceeds the balance of the same sign: once the
    result has been appropriated, nothing remains to present as the exercise result.
    """
    allocated = {number: 0 for number in balances}
    if closed_result == 0:
        return allocated
    same_sign = {
        number: amount
        for number, amount in balances.items()
        if amount and (amount > 0) == (closed_result > 0)
    }
    sitting = sum(same_sign.values())
    if sitting == 0:
        return allocated
    remaining = min(closed_result, sitting) if closed_result > 0 else max(closed_result, sitting)
    for number in sorted(same_sign):
        if remaining == 0:
            break
        room = same_sign[number]
        take = min(room, remaining) if remaining > 0 else max(room, remaining)
        allocated[number] = take
        remaining -= take
    return allocated
