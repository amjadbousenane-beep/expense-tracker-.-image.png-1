
from __future__ import annotations

import argparse
import csv
import io
import sqlite3
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import streamlit as st


DATABASE_PATH = Path(__file__).resolve().with_name("expenses.db")


CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    spent_on TEXT NOT NULL,
    category TEXT NOT NULL,
    description TEXT NOT NULL,
    amount_cents INTEGER NOT NULL CHECK (amount_cents > 0)
)
"""


def initialize_database(connection: sqlite3.Connection) -> None:
    connection.execute(CREATE_TABLE)
    connection.commit()


def parse_amount(value: str) -> int:
    try:
        amount = Decimal(value.strip())
    except InvalidOperation as error:
        raise ValueError("Enter a valid amount, such as 12.50.") from error
    if not amount.is_finite() or amount <= 0:
        raise ValueError("Amount must be greater than zero.")
    cents = amount * 100
    if cents != cents.to_integral_value():
        raise ValueError("Use no more than two decimal places.")
    return int(cents)


def format_money(cents: int) -> str:
    return f"${cents / 100:,.2f}"


def prompt_non_empty(label: str) -> str:
    while True:
        value = input(label).strip()
        if value:
            return value
        print("This field cannot be empty.")


def add_expense(connection: sqlite3.Connection) -> None:
    print("\nAdd expense")
    while True:
        raw_date = input(f"Date [today: {date.today().isoformat()}]: ").strip()
        raw_date = raw_date or date.today().isoformat()
        try:
            spent_on = date.fromisoformat(raw_date).isoformat()
            break
        except ValueError:
            print("Enter a date in YYYY-MM-DD format.")

    category = prompt_non_empty("Category: ")
    description = prompt_non_empty("Description: ")
    while True:
        try:
            amount_cents = parse_amount(input("Amount: "))
            break
        except ValueError as error:
            print(error)

    connection.execute(
        "INSERT INTO expenses (spent_on, category, description, amount_cents) "
        "VALUES (?, ?, ?, ?)",
        (spent_on, category, description, amount_cents),
    )
    connection.commit()
    print("Expense saved.")


def fetch_expenses(
    connection: sqlite3.Connection, month: str | None = None
) -> list[tuple[int, str, str, str, int]]:
    if month:
        try:
            datetime.strptime(month, "%Y-%m")
        except ValueError as error:
            raise ValueError("Month must use YYYY-MM format.") from error
        rows = connection.execute(
            "SELECT id, spent_on, category, description, amount_cents "
            "FROM expenses WHERE substr(spent_on, 1, 7) = ? "
            "ORDER BY spent_on DESC, id DESC",
            (month,),
        )
    else:
        rows = connection.execute(
            "SELECT id, spent_on, category, description, amount_cents "
            "FROM expenses ORDER BY spent_on DESC, id DESC"
        )
    return rows.fetchall()


def print_expenses(rows: list[tuple[int, str, str, str, int]]) -> None:
    if not rows:
        print("No expenses found.")
        return
    print(f"\n{'ID':>5}  {'Date':<10}  {'Category':<18}  {'Amount':>12}  Description")
    print("-" * 76)
    for expense_id, spent_on, category, description, amount_cents in rows:
        print(
            f"{expense_id:>5}  {spent_on:<10}  {category[:18]:<18}  "
            f"{format_money(amount_cents):>12}  {description}"
        )
    print(f"\n{len(rows)} expense(s), total {format_money(sum(row[4] for row in rows))}.")


def list_expenses(connection: sqlite3.Connection) -> None:
    month = input("Filter by month (YYYY-MM), or press Enter for all: ").strip()
    try:
        print_expenses(fetch_expenses(connection, month or None))
    except ValueError as error:
        print(error)


def show_summary(connection: sqlite3.Connection) -> None:
    month = input(f"Month (YYYY-MM) [{date.today():%Y-%m}]: ").strip()
    month = month or date.today().strftime("%Y-%m")
    try:
        datetime.strptime(month, "%Y-%m")
    except ValueError:
        print("Month must use YYYY-MM format.")
        return

    total, count = connection.execute(
        "SELECT COALESCE(SUM(amount_cents), 0), COUNT(*) FROM expenses "
        "WHERE substr(spent_on, 1, 7) = ?",
        (month,),
    ).fetchone()
    print(f"\nSummary for {month}: {count} expense(s), {format_money(total)} total.")
    categories = connection.execute(
        "SELECT category, SUM(amount_cents), COUNT(*) FROM expenses "
        "WHERE substr(spent_on, 1, 7) = ? GROUP BY category "
        "ORDER BY SUM(amount_cents) DESC, category COLLATE NOCASE",
        (month,),
    ).fetchall()
    if categories:
        print(f"{'Category':<24} {'Count':>7} {'Total':>12}")
        for category, category_total, category_count in categories:
            print(f"{category[:24]:<24} {category_count:>7} {format_money(category_total):>12}")
    else:
        print("No expenses recorded for this month.")


def delete_expense(connection: sqlite3.Connection) -> None:
    raw_id = input("Expense ID to delete: ").strip()
    try:
        expense_id = int(raw_id)
    except ValueError:
        print("Enter a valid numeric ID.")
        return

    row = connection.execute(
        "SELECT spent_on, category, description, amount_cents "
        "FROM expenses WHERE id = ?",
        (expense_id,),
    ).fetchone()
    if row is None:
        print(f"No expense found with ID {expense_id}.")
        return
    spent_on, category, description, amount_cents = row
    print(f"{spent_on} | {category} | {description} | {format_money(amount_cents)}")
    if input("Delete this expense? [y/N]: ").strip().lower() != "y":
        print("Deletion cancelled.")
        return
    connection.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
    connection.commit()
    print("Expense deleted.")


def export_csv(connection: sqlite3.Connection) -> None:
    raw_path = input("CSV file path [expenses.csv]: ").strip()
    output_path = Path(raw_path or "expenses.csv")
    rows = fetch_expenses(connection)
    try:
        with output_path.open("w", newline="", encoding="utf-8") as output_file:
            writer = csv.writer(output_file)
            writer.writerow(("id", "date", "category", "description", "amount"))
            for expense_id, spent_on, category, description, amount_cents in rows:
                writer.writerow((expense_id, spent_on, category, description, f"{amount_cents / 100:.2f}"))
    except OSError as error:
        print(f"Could not write CSV: {error}")
        return
    print(f"Exported {len(rows)} expense(s) to {output_path}.")


def run_menu(connection: sqlite3.Connection) -> None:
    actions = {
        "1": add_expense,
        "2": list_expenses,
        "3": show_summary,
        "4": delete_expense,
        "5": export_csv,
    }
    while True:
        print(
            "\nExpense Tracker\n"
            "1. Add expense\n"
            "2. List expenses\n"
            "3. Monthly summary\n"
            "4. Delete expense\n"
            "5. Export CSV\n"
            "6. Quit"
        )
        choice = input("Choose an option: ").strip()
        if choice == "6":
            print("Goodbye.")
            return
        action = actions.get(choice)
        if action is None:
            print("Choose a number from 1 to 6.")
            continue
        try:
            action(connection)
        except sqlite3.Error as error:
            print(f"Database error: {error}")


class ExpenseTrackerApp:
    def __init__(self, root: tk.Tk, connection: sqlite3.Connection) -> None:
        self.root = root
        self.connection = connection
        self.month_var = tk.StringVar(value=date.today().strftime("%Y-%m"))
        self.status_var = tk.StringVar()
        self.total_var = tk.StringVar()
        self.root.title("Expense Tracker")
        self.root.geometry("1000x680")
        self.root.minsize(760, 500)
        self.root.configure(background="#f3f5f2")

        style = ttk.Style(root)
        style.configure("Treeview", rowheight=30, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))
        style.configure("TButton", padding=(12, 7), font=("Segoe UI", 10))
        style.configure("Accent.TButton", padding=(12, 7), font=("Segoe UI", 10, "bold"))
        style.configure("TLabel", background="#f3f5f2", font=("Segoe UI", 10))

        self._build_layout()
        self.refresh_expenses()

    def _build_layout(self) -> None:
        header = tk.Frame(self.root, bg="#173c35", padx=24, pady=20)
        header.pack(fill="x")
        tk.Label(
            header, text="EXPENSE TRACKER", bg="#173c35", fg="#d9e9d8",
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w")
        tk.Label(
            header, text="Your spending, clearly.", bg="#173c35", fg="white",
            font=("Segoe UI", 22, "bold"),
        ).pack(anchor="w", pady=(3, 0))

        content = ttk.Frame(self.root, padding=(24, 20, 24, 12))
        content.pack(fill="both", expand=True)

        toolbar = ttk.Frame(content)
        toolbar.pack(fill="x", pady=(0, 16))
        ttk.Button(toolbar, text="+  Add expense", style="Accent.TButton", command=self.add_expense).pack(side="left")
        ttk.Button(toolbar, text="Delete selected", command=self.delete_expense).pack(side="left", padx=(8, 0))
        ttk.Button(toolbar, text="Export CSV", command=self.export_csv).pack(side="left", padx=(8, 0))
        ttk.Label(toolbar, text="Month (YYYY-MM)").pack(side="right", padx=(8, 0))
        month_entry = ttk.Entry(toolbar, textvariable=self.month_var, width=10)
        month_entry.pack(side="right")
        month_entry.bind("<Return>", lambda _event: self.refresh_expenses())
        ttk.Button(toolbar, text="All months", command=self.show_all_expenses).pack(side="right", padx=(0, 8))

        summary = tk.Frame(content, bg="#ffffff", padx=16, pady=13, highlightbackground="#dce2dc", highlightthickness=1)
        summary.pack(fill="x", pady=(0, 14))
        tk.Label(summary, text="MONTHLY TOTAL", bg="white", fg="#61716a", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        tk.Label(summary, textvariable=self.total_var, bg="white", fg="#173c35", font=("Segoe UI", 18, "bold")).pack(anchor="w", pady=(2, 0))

        table_frame = ttk.Frame(content)
        table_frame.pack(fill="both", expand=True)
        columns = ("date", "category", "description", "amount")
        self.table = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")
        self.table.heading("date", text="DATE")
        self.table.heading("category", text="CATEGORY")
        self.table.heading("description", text="DESCRIPTION")
        self.table.heading("amount", text="AMOUNT", anchor="e")
        self.table.column("date", width=120, minwidth=100)
        self.table.column("category", width=160, minwidth=110)
        self.table.column("description", width=450, minwidth=150)
        self.table.column("amount", width=130, minwidth=110, anchor="e")
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=scrollbar.set)
        self.table.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.table.bind("<Double-1>", lambda _event: self.delete_expense())

        footer = ttk.Frame(content)
        footer.pack(fill="x", pady=(10, 0))
        ttk.Label(footer, textvariable=self.status_var).pack(side="left")
        ttk.Button(footer, text="Refresh", command=self.refresh_expenses).pack(side="right")

    def _selected_month(self) -> str | None:
        month = self.month_var.get().strip()
        if not month:
            return None
        try:
            datetime.strptime(month, "%Y-%m")
        except ValueError as error:
            raise ValueError("Enter a month in YYYY-MM format, or leave it blank for all months.") from error
        return month

    def refresh_expenses(self) -> None:
        try:
            month = self._selected_month()
            rows = fetch_expenses(self.connection, month)
        except ValueError as error:
            messagebox.showerror("Invalid month", str(error), parent=self.root)
            return
        except sqlite3.Error as error:
            messagebox.showerror("Database error", str(error), parent=self.root)
            return

        self.table.delete(*self.table.get_children())
        for expense_id, spent_on, category, description, amount_cents in rows:
            self.table.insert(
                "", "end", iid=str(expense_id),
                values=(spent_on, category, description, format_money(amount_cents)),
            )
        total = sum(row[4] for row in rows)
        label_month = month or "all months"
        self.total_var.set(f"{format_money(total)}  ·  {len(rows)} expense(s) · {label_month}")
        self.status_var.set(f"Showing {len(rows)} expense(s).")

    def show_all_expenses(self) -> None:
        self.month_var.set("")
        self.refresh_expenses()

    def add_expense(self) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title("Add expense")
        dialog.transient(self.root)
        dialog.resizable(False, False)
        dialog.grab_set()

        form = ttk.Frame(dialog, padding=20)
        form.pack(fill="both", expand=True)
        fields = (
            ("Date (YYYY-MM-DD)", date.today().isoformat()),
            ("Category", ""),
            ("Description", ""),
            ("Amount", ""),
        )
        entries: dict[str, ttk.Entry] = {}
        for row, (label, initial) in enumerate(fields):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky="w", padx=(0, 16), pady=7)
            entry = ttk.Entry(form, width=36)
            entry.insert(0, initial)
            entry.grid(row=row, column=1, sticky="ew", pady=7)
            entries[label] = entry
        form.columnconfigure(1, weight=1)

        def save() -> None:
            try:
                spent_on = date.fromisoformat(entries["Date (YYYY-MM-DD)"].get().strip()).isoformat()
                category = entries["Category"].get().strip()
                description = entries["Description"].get().strip()
                amount_cents = parse_amount(entries["Amount"].get())
                if not category or not description:
                    raise ValueError("Category and description cannot be empty.")
            except ValueError as error:
                messagebox.showerror("Check expense details", str(error), parent=dialog)
                return
            try:
                self.connection.execute(
                    "INSERT INTO expenses (spent_on, category, description, amount_cents) VALUES (?, ?, ?, ?)",
                    (spent_on, category, description, amount_cents),
                )
                self.connection.commit()
            except sqlite3.Error as error:
                messagebox.showerror("Database error", str(error), parent=dialog)
                return
            self.month_var.set(spent_on[:7])
            dialog.destroy()
            self.refresh_expenses()

        buttons = ttk.Frame(form)
        buttons.grid(row=len(fields), column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Save expense", style="Accent.TButton", command=save).pack(side="left")
        entries["Date (YYYY-MM-DD)"].focus_set()
        dialog.bind("<Return>", lambda _event: save())

    def delete_expense(self) -> None:
        selection = self.table.selection()
        if not selection:
            messagebox.showinfo("Delete expense", "Select an expense to delete.", parent=self.root)
            return
        expense_id = int(selection[0])
        row = self.connection.execute(
            "SELECT spent_on, category, description, amount_cents FROM expenses WHERE id = ?",
            (expense_id,),
        ).fetchone()
        if row is None:
            self.refresh_expenses()
            return
        spent_on, category, description, amount_cents = row
        details = f"{spent_on} | {category} | {description} | {format_money(amount_cents)}"
        if not messagebox.askyesno("Delete expense?", f"Delete this expense?\n\n{details}", parent=self.root):
            return
        try:
            self.connection.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
            self.connection.commit()
        except sqlite3.Error as error:
            messagebox.showerror("Database error", str(error), parent=self.root)
            return
        self.refresh_expenses()

    def export_csv(self) -> None:
        output_path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Export expenses",
            defaultextension=".csv",
            initialfile="expenses.csv",
            filetypes=(("CSV files", "*.csv"), ("All files", "*.*")),
        )
        if not output_path:
            return
        try:
            rows = fetch_expenses(self.connection)
            with Path(output_path).open("w", newline="", encoding="utf-8") as output_file:
                writer = csv.writer(output_file)
                writer.writerow(("id", "date", "category", "description", "amount"))
                for expense_id, spent_on, category, description, amount_cents in rows:
                    writer.writerow((expense_id, spent_on, category, description, f"{amount_cents / 100:.2f}"))
        except (OSError, sqlite3.Error) as error:
            messagebox.showerror("Export failed", str(error), parent=self.root)
            return
        messagebox.showinfo("Export complete", f"Exported {len(rows)} expense(s) to:\n{output_path}", parent=self.root)


def render_app(connection: sqlite3.Connection) -> None:
    st.set_page_config(page_title="Expense Tracker", page_icon="$", layout="wide")
    st.markdown(
        """
        <style>
        :root {
            --forest: #173c35;
            --leaf: #dce9d9;
            --coral: #d9664d;
            --ink: #26332e;
            --paper: #f5f5ef;
        }
        .stApp { background: var(--paper); color: var(--ink); }
        [data-testid="stAppViewContainer"] {
            background-image: radial-gradient(#d7dfd5 0.65px, transparent 0.65px);
            background-size: 14px 14px;
        }
        .block-container { padding-top: 2rem; max-width: 1180px; }
        .tracker-header {
            background: var(--forest); color: white; padding: 1.5rem 1.8rem;
            border-left: 6px solid var(--coral); margin-bottom: 1.5rem;
        }
        .tracker-kicker { color: var(--leaf); font-size: .75rem; font-weight: 700; letter-spacing: .12em; }
        .tracker-header h1 { color: white; font-family: Georgia, serif; font-size: 2.1rem; margin: .2rem 0 0; }
        [data-testid="stMetric"] {
            background: white; border: 1px solid #dce2dc; border-radius: 4px;
            padding: 1rem 1.1rem;
        }
        [data-testid="stMetricValue"] { color: var(--forest); }
        div.stButton > button[kind="primary"], div.stFormSubmitButton > button[kind="primary"] {
            background: var(--forest); border-color: var(--forest); color: white;
        }
        </style>
        <header class="tracker-header">
            <div class="tracker-kicker">PERSONAL FINANCE</div>
            <h1>Expense Tracker</h1>
        </header>
        """,
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.subheader("Add an expense")
        with st.form("add_expense", clear_on_submit=True):
            spent_on = st.date_input("Date", value=date.today())
            category = st.text_input("Category", placeholder="e.g. Groceries")
            description = st.text_input("Description", placeholder="What was it for?")
            amount = st.number_input("Amount ($)", min_value=0.01, step=0.01, format="%.2f")
            submitted = st.form_submit_button("Save expense", type="primary", use_container_width=True)
        if submitted:
            try:
                clean_category = category.strip()
                clean_description = description.strip()
                if not clean_category or not clean_description:
                    raise ValueError("Enter both a category and a description.")
                amount_cents = parse_amount(str(amount))
                connection.execute(
                    "INSERT INTO expenses (spent_on, category, description, amount_cents) "
                    "VALUES (?, ?, ?, ?)",
                    (spent_on.isoformat(), clean_category, clean_description, amount_cents),
                )
                connection.commit()
                st.success("Expense saved.")
                st.rerun()
            except (ValueError, sqlite3.Error) as error:
                st.error(str(error))

    months = [row[0] for row in connection.execute(
        "SELECT DISTINCT substr(spent_on, 1, 7) FROM expenses ORDER BY 1 DESC"
    ).fetchall()]
    current_month = date.today().strftime("%Y-%m")
    if current_month not in months:
        months.insert(0, current_month)
    month_options = ["All months", *months]
    selected_month = st.selectbox(
        "Showing", month_options,
        index=month_options.index(current_month) if current_month in month_options else 0,
    )
    month = None if selected_month == "All months" else selected_month
    rows = fetch_expenses(connection, month)
    total_cents = sum(row[4] for row in rows)

    metric_total, metric_count, metric_average = st.columns(3)
    metric_total.metric("Total spent", format_money(total_cents))
    metric_count.metric("Expenses", f"{len(rows)}")
    metric_average.metric(
        "Average expense", format_money(total_cents // len(rows)) if rows else "$0.00"
    )

    details_column, chart_column = st.columns([1.15, 0.85], gap="large")
    with details_column:
        st.subheader("Recent expenses")
        if rows:
            st.dataframe(
                [
                    {
                        "Date": spent_on,
                        "Category": category,
                        "Description": description,
                        "Amount": format_money(amount_cents),
                    }
                    for _, spent_on, category, description, amount_cents in rows
                ],
                hide_index=True,
                use_container_width=True,
            )
        else:
            st.info("No expenses recorded for this period yet.")

    with chart_column:
        st.subheader("By category")
        category_totals: dict[str, int] = {}
        for _, _, category, _, amount_cents in rows:
            category_totals[category] = category_totals.get(category, 0) + amount_cents
        if category_totals:
            category_rows = sorted(category_totals.items(), key=lambda item: item[1], reverse=True)
            st.bar_chart({"Category": [item[0] for item in category_rows], "Total ($)": [item[1] / 100 for item in category_rows]}, x="Category", y="Total ($)")
            st.dataframe(
                [{"Category": name, "Total": format_money(value)} for name, value in category_rows],
                hide_index=True,
                use_container_width=True,
            )
        else:
            st.caption("Category totals will appear here once you add expenses.")

    all_rows = fetch_expenses(connection)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(("id", "date", "category", "description", "amount"))
    for expense_id, spent_on, category, description, amount_cents in all_rows:
        writer.writerow((expense_id, spent_on, category, description, f"{amount_cents / 100:.2f}"))
    st.download_button(
        "Download all expenses as CSV",
        data=output.getvalue(),
        file_name="expenses.csv",
        mime="text/csv",
    )

    if rows:
        with st.expander("Delete an expense"):
            expense_options = {
                f"{spent_on} · {category} · {description} · {format_money(amount_cents)} (#{expense_id})": expense_id
                for expense_id, spent_on, category, description, amount_cents in rows
            }
            with st.form("delete_expense"):
                selected_expense = st.selectbox("Choose expense", list(expense_options))
                confirmed = st.checkbox("Confirm deletion")
                delete_submitted = st.form_submit_button("Delete expense")
            if delete_submitted:
                if not confirmed:
                    st.warning("Confirm deletion before continuing.")
                else:
                    connection.execute("DELETE FROM expenses WHERE id = ?", (expense_options[selected_expense],))
                    connection.commit()
                    st.success("Expense deleted.")
                    st.rerun()


def main() -> None:
    try:
        with sqlite3.connect(DATABASE_PATH) as connection:
            initialize_database(connection)
            render_app(connection)
    except (OSError, sqlite3.Error) as error:
        st.error(f"Could not open expense database: {error}")


if __name__ == "__main__":
    main()
