"""US equity paper-trading MVP.

The package is intentionally long-only and paper-only in its first version.
"""

__version__ = "0.1.0"


if __name__ == "__main__":
    # Supports Streamlit Cloud when this package module is selected as the
    # app's entry point.
    from paper_trading.dashboard import run_dashboard

    run_dashboard()
