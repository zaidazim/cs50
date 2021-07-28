import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):         # pk_b81b55cb82ad4c54ad3c57a45b1b8bb1
    raise RuntimeError("API_KEY not set")


@app.route("/change_password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        old = request.form.get("password")
        new = request.form.get("changePassword")
        confirm = request.form.get("confirmation")

        rows = db.execute("SELECT * FROM users WHERE id=:user_id", user_id=session["user_id"])
        pwhash = rows["hash"]

        if not old or not new or not confirmation:
            return apology("Could not change password", 403)
        elif new != confirm:
            return apology("New passwords must match", 403)
        elif not check_password_hash(pwhash, new):
            return apology("Incorrect current password", 403)

        try:
            db.execute("UPDATE users SET hash=:newhashed WHERE id=:user_id"
            , newhashed=generate_password_hash(new), id=session["user_id"])
        except:
            return apology("Couldn't change password!", 400)

        flash("Password changed sucessfully!")
        return redirect("/")

    else:
        return render_template("password.html")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    transactions = db.execute("""
    SELECT symbol, SUM(shares) as totalShares, price
    FROM transactions WHERE user_id=:user_id
    GROUP BY symbol
    HAVING totalShares > 0
    """, user_id=session["user_id"])

    # A list of dictionaries to store stock details
    portfolio = []
    grandTotal = 0
    for row in transactions:
        stock = lookup(row["symbol"])
        portfolio.append({
            "symbol": stock["symbol"],
            "name": stock["name"],
            "shares": row["totalShares"],
            "price": usd(row["price"]),
            "total": usd(row["price"] * row["totalShares"])
        })
        grandTotal += row["price"] * row["totalShares"]

    rows = db.execute("SELECT cash FROM users WHERE id=:user_id", user_id=session["user_id"])
    cash = rows[0]["cash"]
    grandTotal += cash

    return render_template("index.html", portfolio=portfolio, cash=usd(cash), grandTotal=usd(grandTotal))



@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    # User submits a form with stock symbol and number of shares to buy via POST
    if request.method == "POST":

        symbol = request.form.get("symbol").upper()
        shares = request.form.get("shares")

        stock = lookup(symbol)

        if not symbol or not shares:
            return apology("Missing symbol/shares", 400)
        # User enters an invalid symbol
        if stock == None:
            return apology("Invalid symbol", 400)
        # User enters a decimal value in the shares field
        elif not shares.isnumeric():
            return apology("Invalid number of shares", 400)

        shares = int(shares)
        rows = db.execute("SELECT cash FROM users WHERE id=:id", id=session["user_id"])
        cash = rows[0]["cash"]

        updated_cash = cash - shares * stock["price"]

        # Check if the user can afford the purchase
        if cash > shares * stock["price"]:
            # Update the cash in the users table after user has bought the stock
            db.execute("UPDATE users SET cash=:updated_cash WHERE id=:id",
            updated_cash=updated_cash, id= session["user_id"])

            # Record the transaction in the transactions table
            db.execute("""
            INSERT INTO transactions
            (user_id, symbol, shares, price)
            VALUES(:user_id, :symbol, :shares, :price)
            """,
            user_id = session["user_id"],
            symbol = symbol,
            shares = shares,
            price = stock["price"]
            )

            flash("Bought!")

            # Redirect user to the index page
            return redirect("/")

        else:
            return apology("Cannot afford stock")

    # Display the buy form if the user requests it via GET
    else:
        return render_template("buy.html")



@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    # Query transaction details for the currently logged in user
    transactions = db.execute("""
    SELECT symbol, shares, price, transacted_at
    FROM transactions WHERE user_id=:user_id
    ORDER BY transacted_at DESC
    """, user_id=session["user_id"])

    # A list of dictionaries where each list is a record of the transaction made by the user
    portfolio = []

    for row in transactions:
        stock = lookup(row["symbol"])
        portfolio.append({
            "symbol": stock["symbol"],
            "shares": row["shares"],
            "price": usd(row["price"]),
            "transacted_at": row["transacted_at"]
        })


    return render_template("history.html", portfolio=portfolio)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    # User quotes for a stock via POST
    if request.method == "POST":
        symbol = request.form.get("symbol")
        if not symbol:
            return apology("Missing symbol", 400)
        symbol = symbol.upper()
        stock = lookup(symbol)

        # lookup returns a dictionary if it finds the stock quote, else it returns None
        # stock{'name': 'Apple Inc', 'symbol': 'AAPL', 'price': 121.03}
        if stock == None:
            return apology("Invalid symbol", 400)

        return render_template("/quoted.html", stock=stock)

    else:
        return render_template("quote.html")



@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # User registers by submitting the registration form via POST
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        if not username:
            return apology("Must provide username", 400)

        elif not password:
            return apology("Must provide password", 400)

        elif password != confirmation:
            return apology("Passwords fields should match", 400)

        try:
            rows = db.execute("INSERT INTO users (username, hash) VALUES(:username, :hash)",
            username=username, hash=generate_password_hash(password))
            flash("Registered!")
        except:
            return apology("Username already exists", 400)

        if rows is None:
            return apology("Registration error", 400)

        session["user_id"] = rows

        return redirect("/")

    # User reaches route via GET (display the form for the user to register)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    rows = db.execute("""
        SELECT symbol, SUM(shares) as totalShares
        FROM transactions WHERE user_id=:user_id
        GROUP BY symbol
        HAVING totalShares > 0
        """, user_id=session["user_id"])


    if request.method == "POST":
        symbol = request.form.get("symbol").upper()
        shares = request.form.get("shares")

        if not symbol or not shares:
            return apology("Missing symbol/shares", 400)
        if not shares.isnumeric():
            return apology("Invalid number of shares", 400)
        stock = lookup(symbol)
        if stock == None:
            return apology("Invalid symbol", 400)
        for row in rows:
            if row["symbol"] == symbol:
                if int(shares) > row["totalShares"]:
                    return apology("Selected number of shares more than currently owned", 400)

        rows = db.execute("SELECT cash FROM users WHERE id=:id", id=session["user_id"])
        cash = rows[0]["cash"]
        shares = int(shares)

        updated_cash = cash + shares * stock["price"]
        # Update cash after user has sold the stock
        db.execute("UPDATE users SET cash=:updated_cash WHERE id=:id",
        updated_cash=updated_cash, id=session["user_id"])

        # Insert the transaction into the transactions table as a negative stock purchase
        db.execute("""
        INSERT INTO transactions (user_id, symbol, shares, price)
        VALUES(:user_id, :symbol, :shares, :price)
        """,
        user_id = session["user_id"],
        symbol = stock["symbol"],
        shares = -1 * shares,
        price = stock["price"]
        )

        flash("Sold!")
        return redirect("/")

    # User reaches the route via GET (display the form with a select menu)
    else:
        symbols = []
        for row in rows:
            symbols.append(row["symbol"])
            # symbols = ["AAPL", "TSLA", "FB"] say

        return render_template("sell.html", symbols=symbols)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
