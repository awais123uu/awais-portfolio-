import io
from dataclasses import dataclass
from typing import Dict

import pandas as pd
from fpdf import FPDF
from flask import Flask, render_template, request, redirect, url_for, session, send_file

app = Flask(__name__)
app.secret_key = "dev-secret"  # For demo purposes only

# In-memory storage for demo use
users: Dict[str, str] = {}
data_store: Dict[str, pd.DataFrame] = {}

@dataclass
class Metrics:
    """Calculated inventory metrics."""
    stock_turnover: float
    days_of_inventory: float
    low_stock: bool


def current_user() -> str:
    """Return the username stored in session or None."""
    return session.get("user")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    """Register a new user. In-memory only."""
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        users[username] = password
        session["user"] = username
        return redirect(url_for("dashboard"))
    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Simple login form."""
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        if users.get(username) == password:
            session["user"] = username
            return redirect(url_for("dashboard"))
    return render_template("login.html")


@app.route("/logout")
def logout():
    """Log the current user out."""
    session.pop("user", None)
    return redirect(url_for("login"))


@app.route("/upload", methods=["GET", "POST"])
def upload():
    """Upload inventory CSV data or add an item manually."""
    if not current_user():
        return redirect(url_for("login"))
    if request.method == "POST":
        if "file" in request.files and request.files["file"].filename:
            file = request.files["file"]
            df = pd.read_csv(file)
        else:
            item = request.form["item"]
            quantity = int(request.form["quantity"])
            daily_sales = float(request.form["daily_sales"])
            df = data_store.get(current_user(), pd.DataFrame(columns=["item", "quantity", "daily_sales"]))
            df = df.append({"item": item, "quantity": quantity, "daily_sales": daily_sales}, ignore_index=True)
        data_store[current_user()] = df
        return redirect(url_for("dashboard"))
    return render_template("upload.html")


def compute_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Compute inventory metrics for each item."""
    metrics = []
    for _, row in df.iterrows():
        daily_sales = row["daily_sales"] if row["daily_sales"] else 0
        quantity = row["quantity"] if row["quantity"] else 0
        stock_turnover = daily_sales / quantity if quantity else 0
        days_of_inventory = quantity / daily_sales if daily_sales else float("inf")
        low_stock = quantity < 10
        metrics.append(Metrics(stock_turnover, days_of_inventory, low_stock))
    metric_df = df.copy()
    metric_df["stock_turnover"] = [m.stock_turnover for m in metrics]
    metric_df["days_of_inventory"] = [m.days_of_inventory for m in metrics]
    metric_df["low_stock"] = [m.low_stock for m in metrics]
    return metric_df


@app.route("/")
@app.route("/dashboard")
def dashboard():
    """Display metrics and charts."""
    if not current_user():
        return redirect(url_for("login"))
    df = data_store.get(current_user())
    metric_df = compute_metrics(df) if df is not None else None
    labels = metric_df["item"].tolist() if metric_df is not None else []
    sales = metric_df["daily_sales"].tolist() if metric_df is not None else []
    inventory = metric_df["quantity"].tolist() if metric_df is not None else []
    return render_template(
        "dashboard.html",
        table=metric_df,
        labels=labels,
        sales=sales,
        inventory=inventory,
    )


@app.route("/export/excel")
def export_excel():
    """Export metrics as an Excel file."""
    df = data_store.get(current_user())
    if df is None:
        return redirect(url_for("dashboard"))
    metric_df = compute_metrics(df)
    output = io.BytesIO()
    metric_df.to_excel(output, index=False)
    output.seek(0)
    return send_file(output, download_name="report.xlsx", as_attachment=True)


@app.route("/export/pdf")
def export_pdf():
    """Export metrics as a simple PDF file."""
    df = data_store.get(current_user())
    if df is None:
        return redirect(url_for("dashboard"))
    metric_df = compute_metrics(df)
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    for col in metric_df.columns:
        pdf.cell(40, 10, col, 1)
    pdf.ln()
    for _, row in metric_df.iterrows():
        for col in metric_df.columns:
            pdf.cell(40, 10, str(row[col]), 1)
        pdf.ln()
    output = io.BytesIO(pdf.output(dest="S").encode("latin-1"))
    return send_file(output, download_name="report.pdf", as_attachment=True)


if __name__ == "__main__":
    app.run(debug=True)
