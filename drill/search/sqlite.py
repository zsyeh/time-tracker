"""Small-fixture reference matcher. SQLite is not a production performance target."""
from .query import private_matches

def matches(plan, values):
    return private_matches(plan, *values)
