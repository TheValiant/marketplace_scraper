# main.py

"""Entry point for the ecom_search TUI application."""

from src.ui.app import EcomSearchApp


def main():
    """Launch the ecom_search TUI application."""
    app = EcomSearchApp()
    app.run()


if __name__ == "__main__":
    main()
