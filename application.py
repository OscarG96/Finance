import os, datetime

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
#from dotenv import load_dotenv

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

#load_dotenv()

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
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    user = session["user_id"]

    #get user stocks
    user_stocks = db.execute("SELECT *, SUM(shares_amount) AS shares_sum FROM purchases WHERE user_id = ? GROUP BY stock;", user)

    for purchase in user_stocks:
        purchase["current_price"] = lookup(purchase["stock"])["price"]
        purchase["stock_name"] = lookup(purchase["stock"])["name"]

    print(user_stocks)

    total = sum(item['current_price'] * item["shares_sum"] for item in user_stocks)
    user_cash = db.execute("SELECT cash from users WHERE id = ?", user)[0]["cash"]
    grand_total = total + user_cash

    print("grand total" ,grand_total)


    return render_template("index.html", purchases=user_stocks, grand_total=grand_total, user_cash=user_cash)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        if not request.form.get("symbol"):
            return apology("must provide symbol", 400)

        symbol = request.form.get("symbol")

        if not request.form.get("shares"):
            return apology("must provide shares", 400)

        shares = request.form.get("shares")
        print("type of shares" ,type(shares))

        #if shares.isdigit() == False or type(shares) !== int:
         #   return apology("shares type must be digit", 400)
        if shares.isnumeric() == False:
            return apology("shares must be positive integrer", 400)

        shares = int(shares)

        if shares < 1:
            return apology("shares must be positive integrer", 400)


        quote = lookup(symbol)
        if not quote:
            return apology("quote not found", 400)

        userCash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"]);

        """If user can´t afford ir return message"""
        price = quote["price"]
        totalPurchase = price * shares

        cash = userCash[0]["cash"]

        if totalPurchase > cash:
            return apology("insufficient cash :(", 400)

        #query to see if stock already exists
        exists = db.execute("SELECT * FROM purchases WHERE stock = ?", symbol)

        if len(exists) > 0:
            #update
            db.execute("UPDATE purchases SET shares_amount = shares_amount + ? WHERE stock = ? AND user_id = ?", shares, symbol, session["user_id"])
        else:
            db.execute("INSERT INTO purchases (user_id, stock, price, created_at, shares_amount) VALUES (?, ?, ? , ?, ?)", session["user_id"], symbol, price, datetime.datetime.now(), shares)

        #update user's cash
        db.execute("UPDATE users SET cash = cash - ? WHERE id = ?", price * shares, session["user_id"])

        #register transaction
        db.execute("INSERT INTO transactions (user_id, stock, price, created_at, shares_amount, type) VALUES (?, ?, ? , ?, ?, ?)", session["user_id"], symbol, price, datetime.datetime.now(), shares, "purchase")

        return redirect("/")

    else:
        return render_template("buy.html")

@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    user = session["user_id"]

    #get user stocks
    transactions = db.execute("SELECT * FROM transactions WHERE user_id = ? ;", user)

    return render_template("history.html", transactions=transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 400)

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
    if request.method == "POST":
        if not request.form.get("symbol"):
            return apology("must symbol", 400)

        quote = lookup(request.form.get("symbol"))

        if not quote:
            return apology("quote not found", 400)
        quote["price"] = usd(quote["price"])
        return render_template("quoted.html", quote=quote)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Ensure password was submitted
        elif not request.form.get("confirmation"):
            return apology("must provide confirmation", 400)

        # Ensure password was submitted
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("Password and confirmation must be equal", 400)

        username = request.form.get("username")
        hashed = generate_password_hash(request.form.get("password"))

        user_exists = db.execute("SELECT username FROM users WHERE username = ?", username)
        if len(user_exists) > 0:
            return apology("user already exists, please login", 400)

        db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, hashed)

        return render_template("login.html")

    else:
        return render_template("register.html")



@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        if not request.form.get("symbol"):
            return apology("must provide symbol", 400)

        symbol = request.form.get("symbol")

        if not request.form.get("shares"):
            return apology("must provide shares", 400)

        shares = request.form.get("shares")
        shares = int(shares)

        if shares < 1:
            return apology("shares must be positive integrer", 400)

        #get user current stocks
        user = session["user_id"]
        user_stocks = db.execute("SELECT *, SUM(shares_amount) AS shares_sum FROM purchases WHERE user_id = ? GROUP BY stock;", user)

        #search stock in user stocks
        exists = filter(lambda stock: stock['symbol'] == symbol, user_stocks)

        if not exists:
            return apology("user does not own such stock")


        quote = lookup(symbol)
        #print("symbol" ,symbol)
        #print("quote" ,quote)
        price = quote["price"]

        #check amount of stocks user can sell
        user_stock = db.execute("SELECT *, SUM(shares_amount) AS shares_sum FROM purchases WHERE user_id = ? WHERE stock = ? GROUP BY stock;", user, symbol)[0]

        if user_stock["shares_amount"] < shares:
            return apology("Cannot sale more shares than owned", 400)



        #register transaction
        db.execute("INSERT INTO transactions (user_id, stock, price, created_at, shares_amount, type) VALUES (?, ?, ? , ?, ?, ?)", user, symbol, price, datetime.datetime.now(), shares, "sale")

        #update user purchases, substract shares
        db.execute("UPDATE purchases SET shares_amount = shares_amount - ? WHERE stock = ? AND user_id = ?", shares, symbol, user)

        #add cash to user
        db.execute("UPDATE users SET cash = cash + ? WHERE id = ?", price * shares, user)

        return redirect("/")

    else:
        #get users symbols
        user = session["user_id"]
        user_stocks = db.execute("SELECT *, SUM(shares_amount) AS shares_sum FROM purchases WHERE user_id = ? GROUP BY stock;", user)
        return render_template("sell.html", user_stocks=user_stocks)

@app.route("/addCash", methods=["GET", "POST"])
@login_required
def addCash():
    if request.method == "POST":
        if not request.form.get("cash"):
            return apology("must provide cash", 400)

        user = session["user_id"]
        cash_to_add = request.form.get("cash")

        db.execute("UPDATE users SET cash = cash + ?", cash_to_add)

        return redirect("/")

    else:
        return render_template("addCash.html")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
