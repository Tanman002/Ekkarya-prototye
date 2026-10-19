"""Registry of the current run's pages so views can link / switch to each other."""
PAGES: dict = {}


def page(key):
    return PAGES[key]
