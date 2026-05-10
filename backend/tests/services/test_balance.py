"""Balance computation + min-transfer settlement tests.

Focus on cents accuracy, weight rules, and settlement minimality.
"""

from app.services.balance import (
    BudgetCategoryInput,
    BudgetInput,
    BudgetUserInput,
    Settlement,
    compute_balance,
    minimum_transfers,
)


def _user(id_: int, family_id: int, attended: int, weight: float) -> BudgetUserInput:
    return BudgetUserInput(
        user_id=id_,
        family_id=family_id,
        attendance_days=attended,
        weight=weight,
    )


def test_single_payer_even_split_per_night():
    users = [
        _user(1, 1, 3, 1.0),  # adult, 3 nights
        _user(2, 2, 3, 1.0),  # adult, 3 nights
        _user(3, 2, 3, 0.5),  # kid, 3 nights
    ]
    cats = [
        BudgetCategoryInput(
            category_id=10, name="Mad", is_per_night=True, expenses=[(1, 2500)]
        )
    ]
    result = compute_balance(BudgetInput(users=users, categories=cats))

    # weighted units = 3 + 3 + 1.5 = 7.5; cost = 2500 cents
    # shares: u1=2500*3/7.5=1000, u2=1000, u3=2500*1.5/7.5=500
    shares = {s.user_id: s.share_cents for s in result.shares}
    assert shares == {1: 1000, 2: 1000, 3: 500}
    paid = {s.user_id: s.paid_cents for s in result.shares}
    assert paid == {1: 2500, 2: 0, 3: 0}
    nets = {s.user_id: s.net_cents for s in result.shares}
    assert nets == {1: 1500, 2: -1000, 3: -500}


def test_baby_pays_nothing_and_doesnt_get_share():
    users = [
        _user(1, 1, 2, 1.0),
        _user(2, 2, 2, 0.0),  # baby
    ]
    cats = [
        BudgetCategoryInput(
            category_id=10, name="Mad", is_per_night=True, expenses=[(1, 1000)]
        )
    ]
    result = compute_balance(BudgetInput(users=users, categories=cats))
    shares = {s.user_id: s.share_cents for s in result.shares}
    assert shares == {1: 1000, 2: 0}


def test_rounding_distributes_remainders_to_largest():
    users = [
        _user(1, 1, 3, 1.0),
        _user(2, 2, 3, 1.0),
        _user(3, 3, 3, 1.0),
    ]
    cats = [
        BudgetCategoryInput(
            category_id=10, name="Mad", is_per_night=True, expenses=[(1, 100)]
        )
    ]
    result = compute_balance(BudgetInput(users=users, categories=cats))
    shares = sorted(s.share_cents for s in result.shares)
    assert sum(shares) == 100
    assert shares == [33, 33, 34]


def test_non_per_night_split_evenly_among_attendees():
    users = [
        _user(1, 1, 2, 1.0),
        _user(2, 2, 5, 1.0),
        _user(3, 3, 0, 1.0),  # did not attend
    ]
    cats = [
        BudgetCategoryInput(
            category_id=10, name="Udlejning", is_per_night=False, expenses=[(1, 4000)]
        )
    ]
    result = compute_balance(BudgetInput(users=users, categories=cats))
    shares = {s.user_id: s.share_cents for s in result.shares}
    assert shares == {1: 2000, 2: 2000, 3: 0}


def test_aggregates_share_across_categories():
    users = [
        _user(1, 1, 2, 1.0),
        _user(2, 2, 2, 1.0),
    ]
    cats = [
        BudgetCategoryInput(
            category_id=10, name="Mad", is_per_night=True, expenses=[(1, 800)]
        ),
        BudgetCategoryInput(
            category_id=20,
            name="Udlejning",
            is_per_night=False,
            expenses=[(2, 2000)],
        ),
    ]
    result = compute_balance(BudgetInput(users=users, categories=cats))
    shares = {s.user_id: s.share_cents for s in result.shares}
    paid = {s.user_id: s.paid_cents for s in result.shares}
    assert shares == {1: 1400, 2: 1400}  # 400 + 1000 each
    assert paid == {1: 800, 2: 2000}


def test_minimum_transfers_two_parties():
    nets = [(1, 1000), (2, -1000)]  # family 1 is owed 10kr by family 2
    transfers = minimum_transfers(nets)
    assert transfers == [Settlement(from_family_id=2, to_family_id=1, amount_cents=1000)]


def test_minimum_transfers_three_parties():
    # 1: +500, 2: -300, 3: -200 -> two transfers
    transfers = minimum_transfers([(1, 500), (2, -300), (3, -200)])
    paid_to_1 = sum(t.amount_cents for t in transfers if t.to_family_id == 1)
    assert paid_to_1 == 500
    assert all(t.amount_cents > 0 for t in transfers)
    assert len(transfers) == 2


def test_minimum_transfers_uses_at_most_n_minus_one():
    # 4 parties, well-balanced -> at most 3 transfers
    transfers = minimum_transfers([(1, 300), (2, 100), (3, -200), (4, -200)])
    assert len(transfers) <= 3
    s = sum(t.amount_cents for t in transfers if t.to_family_id == 1)
    assert s == 300


def test_minimum_transfers_ignores_zero_balances():
    transfers = minimum_transfers([(1, 0), (2, 100), (3, -100)])
    assert len(transfers) == 1
    assert transfers[0].from_family_id == 3
    assert transfers[0].to_family_id == 2


def test_compute_balance_returns_family_level_settlements():
    users = [
        _user(1, 1, 2, 1.0),
        _user(2, 2, 2, 1.0),
    ]
    cats = [
        BudgetCategoryInput(
            category_id=10,
            name="Mad",
            is_per_night=True,
            expenses=[(1, 2000)],
        )
    ]
    result = compute_balance(BudgetInput(users=users, categories=cats))
    assert len(result.settlements) == 1
    s = result.settlements[0]
    assert s.from_family_id == 2
    assert s.to_family_id == 1
    assert s.amount_cents == 1000


def test_kid_half_weight_on_per_night():
    users = [
        _user(1, 1, 4, 1.0),
        _user(2, 1, 4, 0.5),  # kid in family 1
        _user(3, 2, 4, 1.0),
    ]
    cats = [
        BudgetCategoryInput(
            category_id=10, name="Mad", is_per_night=True, expenses=[(1, 2500)]
        )
    ]
    result = compute_balance(BudgetInput(users=users, categories=cats))
    shares = {s.user_id: s.share_cents for s in result.shares}
    # weighted units: 4 + 2 + 4 = 10; total 2500
    # u1: 2500*4/10 = 1000, u2: 500, u3: 1000
    assert shares == {1: 1000, 2: 500, 3: 1000}
