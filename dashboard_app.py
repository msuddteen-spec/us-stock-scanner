import importlib

from paper_trading import dashboard, interactive_cards


if __name__ == "__main__":
    # Streamlit keeps imported modules in memory during development reruns.
    # Reload the dashboard and its custom component so view edits are reflected immediately.
    importlib.reload(interactive_cards)
    importlib.reload(dashboard)
    dashboard.run_dashboard()
