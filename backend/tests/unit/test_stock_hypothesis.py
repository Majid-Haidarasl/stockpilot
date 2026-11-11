"""Hypothesis sequences over receipt/reserve/release/consume domain ops."""

from __future__ import annotations

from uuid import uuid4

from hypothesis import given, settings
from hypothesis import strategies as st

from stockpilot.modules.inventory.domain.models import (
    InvalidQuantity,
    StockInvariantViolation,
    StockPosition,
)


def _fresh() -> StockPosition:
    return StockPosition(
        id=uuid4(),
        tenant_id=uuid4(),
        warehouse_code="main",
        product_id=uuid4(),
        on_hand=0,
        reserved=0,
        version=1,
    )


@given(
    st.lists(
        st.tuples(
            st.sampled_from(["receipt", "reserve", "release", "consume"]),
            st.integers(min_value=1, max_value=20),
        ),
        min_size=1,
        max_size=40,
    )
)
@settings(max_examples=80, deadline=None)
def test_stock_ops_never_go_negative(ops: list[tuple[str, int]]) -> None:
    position = _fresh()
    for kind, qty in ops:
        try:
            if kind == "receipt":
                position.apply_receipt(qty)
            elif kind == "reserve":
                position.apply_reserve(qty)
            elif kind == "release":
                position.apply_release(qty)
            else:
                position.apply_consume(qty)
        except (StockInvariantViolation, InvalidQuantity):
            continue
        assert position.on_hand >= 0
        assert position.reserved >= 0
        assert position.reserved <= position.on_hand
