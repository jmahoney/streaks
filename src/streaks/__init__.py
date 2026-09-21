"""Streaks - Track habits and streaks.

Three layers. `engine` computes every string, number and colour token from
plain data. `models` loads that data from SQLite and performs writes.
Everything else is a GTK view: it places what the engine produced into a
Blueprint template and reports user actions as signals or `models` writes
followed by `AppState.reload()`.
"""
