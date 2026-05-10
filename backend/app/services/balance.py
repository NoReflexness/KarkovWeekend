"""Balance computation and minimum-transfer settlement.

The pipeline:
1. For each (category, user), compute the user's "units" share for that category:
   units_user = weight * (attendance_days if category.is_per_night else 1 if attended)
2. Per category, distribute the category total in proportion to units, using the
   largest-remainder method so the cents add up exactly.
3. Sum each user's share across categories and compute net = paid - share.
4. Aggregate net by family.
5. Run greedy two-pointer settlement (largest creditor pays largest debtor).
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class BudgetUserInput:
    user_id: int
    family_id: int
    attendance_days: int
    weight: float  # 0 (baby), 0.5 (kid), 1.0 (teen+adult)


@dataclass(frozen=True)
class BudgetCategoryInput:
    category_id: int
    name: str
    is_per_night: bool
    expenses: list[tuple[int, int]]  # (paid_by_user_id, amount_cents)


@dataclass(frozen=True)
class BudgetInput:
    users: list[BudgetUserInput]
    categories: list[BudgetCategoryInput]


@dataclass(frozen=True)
class UserShare:
    user_id: int
    family_id: int
    paid_cents: int
    share_cents: int

    @property
    def net_cents(self) -> int:
        return self.paid_cents - self.share_cents


@dataclass(frozen=True)
class Settlement:
    from_family_id: int
    to_family_id: int
    amount_cents: int


@dataclass
class BalanceResult:
    shares: list[UserShare] = field(default_factory=list)
    settlements: list[Settlement] = field(default_factory=list)
    per_category_totals: dict[int, int] = field(default_factory=dict)


def _category_units(user: BudgetUserInput, category: BudgetCategoryInput) -> float:
    if user.weight <= 0 or user.attendance_days <= 0:
        return 0.0
    if category.is_per_night:
        return user.weight * user.attendance_days
    return user.weight  # one share per attended person


def _largest_remainder_split(total_cents: int, weights: list[float]) -> list[int]:
    """Distribute total_cents in proportion to weights so the sum equals exactly total_cents."""
    s = sum(weights)
    if s <= 0:
        return [0] * len(weights)
    raw = [total_cents * w / s for w in weights]
    floors = [int(x) for x in raw]
    remainder = total_cents - sum(floors)
    # distribute remainder by largest fractional part, ties broken by index (stable)
    fracs = sorted(
        ((raw[i] - floors[i], i) for i in range(len(weights))),
        key=lambda t: (-t[0], t[1]),
    )
    for k in range(remainder):
        _, idx = fracs[k]
        floors[idx] += 1
    return floors


def compute_balance(payload: BudgetInput) -> BalanceResult:
    user_paid: dict[int, int] = {u.user_id: 0 for u in payload.users}
    user_share: dict[int, int] = {u.user_id: 0 for u in payload.users}
    per_category_totals: dict[int, int] = {}

    for cat in payload.categories:
        cat_total = sum(amount for _, amount in cat.expenses)
        per_category_totals[cat.category_id] = cat_total

        for paid_by, amount in cat.expenses:
            user_paid[paid_by] = user_paid.get(paid_by, 0) + amount

        weights = [_category_units(u, cat) for u in payload.users]
        per_user_split = _largest_remainder_split(cat_total, weights)
        for u, share in zip(payload.users, per_user_split, strict=True):
            user_share[u.user_id] += share

    shares = [
        UserShare(
            user_id=u.user_id,
            family_id=u.family_id,
            paid_cents=user_paid.get(u.user_id, 0),
            share_cents=user_share.get(u.user_id, 0),
        )
        for u in payload.users
    ]

    family_net: dict[int, int] = {}
    for s in shares:
        family_net[s.family_id] = family_net.get(s.family_id, 0) + s.net_cents

    settlements = minimum_transfers(list(family_net.items()))

    return BalanceResult(
        shares=shares, settlements=settlements, per_category_totals=per_category_totals
    )


def minimum_transfers(family_nets: list[tuple[int, int]]) -> list[Settlement]:
    """Greedy two-pointer settlement.

    Input: list of (family_id, net_cents). Positive = is owed money, negative = owes money.
    Returns at most N-1 settlements (often fewer when balances pair up).
    """
    nonzero = [(fid, net) for fid, net in family_nets if net != 0]
    creditors = sorted([(fid, net) for fid, net in nonzero if net > 0], key=lambda x: -x[1])
    debtors = sorted([(fid, -net) for fid, net in nonzero if net < 0], key=lambda x: -x[1])

    out: list[Settlement] = []
    i = j = 0
    while i < len(creditors) and j < len(debtors):
        cred_id, cred_amt = creditors[i]
        deb_id, deb_amt = debtors[j]
        pay = min(cred_amt, deb_amt)
        if pay > 0:
            out.append(Settlement(from_family_id=deb_id, to_family_id=cred_id, amount_cents=pay))
        cred_amt -= pay
        deb_amt -= pay
        if cred_amt == 0:
            i += 1
        else:
            creditors[i] = (cred_id, cred_amt)
        if deb_amt == 0:
            j += 1
        else:
            debtors[j] = (deb_id, deb_amt)
    return out
