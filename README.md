# Expense Tracker

A command-line app to record, search and summarize your spending.

## Run
    python main.py          # needs Python 3.10+
    python -m unittest      # run the tests

## Structure
    main.py              entry point
    tracker/models.py    the Expense data class
    tracker/manager.py   logic: add, delete, search, totals
    tracker/storage.py   JSON saving/loading, CSV export
    tracker/inputs.py    safe user-input helpers
    tracker/cli.py       menu and screens

## Ideas to improve it
1. Add an "edit expense" option.
2. Add monthly budgets with a warning when exceeded.
3. Filter by date range.
4. Add a bar chart with matplotlib.
5. Replace JSON with SQLite.
6. Turn it into a web app using Flask (manager.py stays unchanged).
