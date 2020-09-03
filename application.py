import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
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
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
# FOURTH: Display a table with all of the current user's stocks, the number of shares of each, the current price and total value of each holding
# Display the user's current cash balance
# run query to find all the stocks that the currently logged in user has - take a value at session[id]
# use lookup to get values of each stock

    # Self-explanatory
    currentCash = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id = session["user_id"])
    # query to find what current stocks the user has
    currHoldings = db.execute("SELECT symbol, shares FROM holdings WHERE user_id = :user_id",
                                user_id = session["user_id"])
    # sum total of all the shares the current user has
    sumVal = 0

    #loop through each row of the holdings table to find company name, stock symbol, shares, price and the total value held of the stock
    for holding in currHoldings:

        holding["company"] = lookup(holding["symbol"])["name"]
        holding["companySym"] = holding["symbol"]
        holding["companyShares"] = holding["shares"]
        holding["price"] = lookup(holding["symbol"])["price"]
        holding["value"] = holding["price"] * holding["companyShares"]

        sumVal += holding["value"]

    # add the total value of the current stocks to the current amount of cash the user has
    totalVal = sumVal + currentCash[0]["cash"]
    return render_template("index.html", currHoldings = currHoldings, currentCash = currentCash[0]["cash"], totalVal = totalVal)

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
# THIRD: When requested via GET, should display form to buy a stock
# When form is submitted via POST, purchase the stock so long as the user can afford it
# May want to create a new table
# create a way to track what the user has bought

    if request.method == "POST":
        if not request.form.get("symbol"):
            return apology("Must provide a stock symbol", 403)
        elif not request.form.get("shares"):
            return apology("Must indicate how many shares you want to purchase", 403)
        elif int(request.form.get("shares")) < 1:
            return apology("Must input a positive number of shares", 403)
        else:
            quote = lookup(request.form.get("symbol"))
            if not quote:
                return apology("That stock symbol does not exist", 403)

            currentCash = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id = session["user_id"])
            # cash remaining after a stock is purchased
            remainder = currentCash[0]['cash'] - (quote["price"] * int(request.form.get("shares")))

            if remainder < 0:
                return apology("Sorry, you do not have enough balance to make this purchase")
            else:
                # Update user's remaining balance in user's table
                db.execute("UPDATE users SET cash = :remainder WHERE id = :user_id", remainder = remainder, user_id = session["user_id"])
                # First check if user already has any shares of the stock, then update user's shares and total value in transaction's table.
                currentShares = db.execute("SELECT shares FROM holdings WHERE user_id = :user_id AND symbol = :symbol",
                                user_id = session["user_id"], symbol = quote["symbol"])
                shares = int(request.form.get("shares"))

                # add the transaction to a table that records all transactions
                db.execute("INSERT INTO history (user_id, symbol, transactionType, shares, price) VALUES (:user_id, :symbol, :transactionType, :shares, :price)",
                                user_id = session["user_id"], symbol = quote['symbol'], transactionType = "buy", shares = shares,
                                price = shares * float(lookup(request.form.get("symbol"))['price']))

                # if the user has no shares of the stock being bought, insert a row in holdings to record it
                if len(currentShares) == 0:
                    db.execute("INSERT INTO holdings (user_id, symbol, shares, value) VALUES (:user_id, :symbol, :shares, :value)",
                                user_id = session["user_id"], symbol = quote['symbol'], shares = shares,
                                value = shares * float(lookup(request.form.get("symbol"))['price']))

                else:
                    # if the user already has shares, add the bought shares to the existing shares
                    shares = shares + currentShares[0]['shares']
                    db.execute("UPDATE holdings SET shares = :shares WHERE user_id = :user_id AND symbol = :symbol",
                                shares = shares, user_id = session["user_id"], symbol = quote['symbol'])


                flash("Transaction Complete")
                return redirect("/")

    elif request.method == "GET":
        return render_template("buy.html")

@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
# SIXTH: display table with a history of all transactions, listing row by row every buy and every sell

    if request.method == "GET":
        # query the history table for all of its rows
        history = db.execute("SELECT symbol, transactionType, shares, price, time FROM history WHERE user_id = :user_id ORDER BY time DESC",
                              user_id = session["user_id"])

        # loop through every row of the table to extract the relevant information for rendering
        for story in history:

            story["companySym"] = story["symbol"]
            story["transactionType"] = story["transactionType"]
            story["companyShares"] = story["shares"]
            story["value"] = story["price"]
            story["stockPrice"] = lookup(story["symbol"])["price"]

        return render_template("history.html", history = history)
    else:
        return redirect("/")

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
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

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
# SECOND: When requested via GET, should display form to request stock quote
# When form is submitted via POST, lookup the stock symbol by calling the lookup function, and display the results
# Handle incorrect stock values - error message saying stock DNE

    if request.method == "POST":
        if not request.form.get("symbol"):
            return apology("You must provide a stock symbol", 403)
        else:
            # Contact the API to get information regarding the stock symbol
            quote = lookup(request.form.get("symbol"))

            if not quote:
                return apology("That stock symbol does not exist", 403)
            else:
                # display the information of the stock
                return render_template("quoted.html", quote = lookup(request.form.get("symbol")))

    elif request.method == "GET":
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
# FIRST: When requested via GET, should display registration form
# When form is submitted via POST, insert the new user into users table
# Be sure to check for invalid inputs and to hash the user's password
# Add a password confirmation field, otherwise it should look just like login.html

    # clear any previous session
    session.clear()

    if request.method == "POST":
        if not request.form.get("username"):
            return apology("You must provide a username", 403)
        elif not request.form.get("password"):
            return apology("You must provide a password", 403)
        elif not request.form.get("confirmation"):
            return apology("You must confirm your password", 403)
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("Your passwords do not match", 403)

        # if all the above is satisfied, query the database to make sure the username DNE
        userQuery = db.execute("SELECT * FROM users WHERE username = :username", username = request.form.get("username"))

        # if there is result from the query above, the username is taken
        if len(userQuery) != 0:
            return apology("Sorry, this username already exists in our database", 403)

        # enter user into database if the aabove code isn't executed
        rows = db.execute("INSERT INTO users (username, hash) VALUES (:username, :password)",
                username = request.form.get("username"),
                password = generate_password_hash(request.form.get("password"), method ='pbkdf2:sha256', salt_length = 8))

        # Establish a session for this new entry
        session["user_id"] = rows[0]["id"]

        # Send user to their homepage
        return redirect("/")
    else:
        return render_template("register.html")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
# FIFTH: when requested via GET, should display form to sell a stock
# when a form is submitted via POST, sell the specified number of shares of stock, and update the user's cash
# Error check to make sure they have the number of stocks they want to sell, then update table to reflect new balance and shares

    if request.method == "POST":
        if not request.form.get("symbol"):
            return apology("Must provide a stock symbol", 403)
        elif not request.form.get("shares"):
            return apology("Must indicate how many shares you want to purchase", 403)
        elif int(request.form.get("shares")) < 1:
            return apology("Must input a positive number of shares", 403)
        else:
            # contac the API for information about the submitted stock symbol
            quote = lookup(request.form.get("symbol"))
            if not quote:
                return apology("That stock symbol does not exist", 403)

            # the shares entered in by the user
            shares = int(request.form.get("shares"))
            currentCash = db.execute("SELECT cash FROM users WHERE id = :user_id",
                                     user_id = session["user_id"])

            # the resulting balance after the stock sale has been made
            remainder = currentCash[0]['cash'] + (quote["price"] * shares)

            # First check if user already has any shares of the stock, then update user's shares and total value in transaction's table.
            currentShares = db.execute("SELECT shares FROM holdings WHERE user_id = :user_id AND symbol = :symbol",
                            user_id = session["user_id"], symbol = quote['symbol'])
            remainingShares = currentShares[0]["shares"] - shares

            # if there are no shares left, remove them from the table so that they do not show in overview
            if remainingShares == 0:
                db.execute("DELETE FROM holdings WHERE user_id = :user_id and symbol = :symbol",
                           user_id = session["user_id"], symbol = quote['symbol'])
            if remainingShares < 0:
                return apology("Sorry, you don't have enough of that stock to sell", 403)
            else:
                # Update user's balance in user's table
                db.execute("UPDATE users SET cash = :remainder WHERE id = :user_id",
                            remainder = remainder, user_id = session["user_id"])
                # update the holdings table to record the current amount of shares held
                db.execute("UPDATE holdings SET shares = :remainingShares WHERE user_id = :user_id AND symbol = :symbol",
                            remainingShares = remainingShares, user_id = session["user_id"], symbol = quote['symbol'])
                # enter in the sale of stock into the history table
                db.execute("INSERT INTO history (user_id, symbol, transactionType, shares, price) VALUES (:user_id, :symbol, :transactionType, :shares, :price)",
                                user_id = session["user_id"], symbol = quote['symbol'], transactionType = "sell", shares = shares,
                                price = shares * float(lookup(request.form.get("symbol"))['price']))

            flash("Transaction Complete")
            return redirect("/")

    elif request.method == "GET":
        return render_template("sell.html")

@app.route("/addcash", methods=["GET", "POST"])
@login_required
def addcash():

    if request.method == "POST":

        currentCash = db.execute("SELECT cash FROM users WHERE id = :user_id",
                                user_id = session["user_id"])
        # cash after top-up
        remainder = currentCash[0]['cash'] + float(request.form.get("amount"))

        db.execute("UPDATE users SET cash = :remainder WHERE id = :user_id",
                   remainder = remainder, user_id = session["user_id"])

        flash("Transaction Complete")
        return redirect("/")

    elif request.method == "GET":
        return render_template("addcash.html")



def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)

# My personal touches: allow users to add cash, allow selling stock from the index page and change the app to dark mode
