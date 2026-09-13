from njm135.live.gate import contracts_from_usdt


def test_contracts_reject_below_min_size() -> None:
    assert contracts_from_usdt(5, 100_000, 0.0001, 1) == 0
    assert contracts_from_usdt(50, 100, 0.01, 1) == 50
    assert contracts_from_usdt(100, 100, 0.01, 1, max_size=10) == 10
