import pytest

from paper_trading.config import Settings


def test_live_mode_is_rejected():
    with pytest.raises(ValueError, match="paper-only"):
        Settings(alpaca_paper=False).validate()
