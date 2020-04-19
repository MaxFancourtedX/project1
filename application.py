import os
import requests

from flask import Flask, session, render_template, request, flash, redirect, url_for, jsonify
from flask_session import Session
from sqlalchemy import create_engine,text
from sqlalchemy.orm import scoped_session, sessionmaker
from helpers import login_required
from werkzeug.security import check_password_hash, generate_password_hash
 
app = Flask(__name__, instance_relative_config=True)
app.config.from_object('config')
app.config.from_pyfile('config.py')

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

if not os.getenv("GOODREADS_APIKEY"):
    raise RuntimeError("GoodReads_APIKey is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))

@app.route("/")
@app.route("/index", methods=["GET"])
def index():
    return render_template("index.html")

# App route to allow users to login
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        # query database for the username 
        username_data = db.execute("SELECT * FROM users WHERE email = :email", {"email": request.form.get('emailAddress')}).fetchone()
        if username_data is None or not check_password_hash(request.form.get('password'), username_data['password']):
            session["user_id"] = username_data['ID']
            flash("Login successful","success")
            return redirect("/search")
        else:
            flash("Username and/or password incorrect, please try again")
            return render_template("login.html")
    else:
        return render_template("login.html")

# App route to allow new users to register
@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        email = request.form.get('emailAddress')
        if email is None:
            flash('No email provided','warning')
            return render_template("register.html")
        # if email provided by user already exists then return error else submit to database
        if db.execute("SELECT * FROM users WHERE email = :email", {"email": email}).rowcount == 0:
            db.execute("INSERT INTO users (\"familyName\", \"firstName\", password, email) VALUES (:familyName, :firstName, :password, :email)", 
            {"familyName": request.form.get('familyName'), "firstName": request.form.get('firstName'), "password": generate_password_hash(request.form.get('password'), salt_length=8), "email": email})
            db.commit()
            flash("Registeration Successful, Login to Continue","success")
            return render_template("login.html")
        else:
            flash('Email already registered, please choose another','warning')
            return render_template("register.html")
    else:
        return render_template("register.html")

# App route to allow users to logout    
@app.route("/logout", methods=["GET"])
def logout():
    # Forget session data
    session.clear()
    flash("You have logged out successfully", "success")
    return redirect("/login")

# App route to open the search page
@app.route("/search", methods=["GET"])
@login_required
def search():   
    return render_template("search.html")

# App route to show the results of a users search
@app.route("/results", methods=["GET"])
@login_required
def books():
    #Search author, title and ISBN and return all partial matches
    books = db.execute(text("SELECT * FROM books WHERE LOWER(title) LIKE LOWER(:search) OR LOWER(\"ISBN\") LIKE LOWER(:search) OR LOWER(author) LIKE LOWER(:search)"), {"search": f"%{request.args.get('q')}%"}).fetchall()
    return render_template("results.html", books=books)

# App route to show individual book info, allow users to see reviews left on this website, and goodbooks api data
@app.route("/results/<int:bookID>", methods=["GET", "POST"])
@login_required
def bookInfo(bookID):
    if request.method == "POST":
        # first check if the user has already submitted a review for this book, if so then redirect and flash warning
        reviews = db.execute("SELECT * FROM reviews WHERE \"userID\" = :userID AND \"bookID\" = :ID", {"userID": session["user_id"], "ID": bookID}).fetchone()
        # If no review by this user, for this book found then submit data to database
        if reviews == None:
            db.execute("INSERT INTO reviews (review, rating, \"userID\", \"bookID\", title) VALUES (:text_review, :rating, :user_id, :book_id, :title)", 
            {"text_review": request.form.get('text_review'), "rating": request.form.get('user_rating'), "user_id": session["user_id"], "book_id": bookID, "title": request.form.get('review_title')})
            db.commit()
            flash("Thank you for submitting your review!", "success")

        # If review for this user found then flash warning and redirect
        else:
            flash("You have already submitted a review for this book", "warning")
        return redirect(url_for('bookInfo', bookID=bookID))
    else:
        # Make sure that the book ID exists
        book = db.execute("SELECT * FROM public.books WHERE \"ID\" = :ID", {"ID":bookID}).fetchone()
        if book == None: 
            flash("Book ID not found please try another book", "Warning")
            return render_template("search.html")
        # Get goodreads data
        goodreadsdata = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": os.getenv("GOODREADS_APIKEY"), "isbns": book["ISBN"]}).json()
        # Get any reviews that have been written on this website
        own_reviews = db.execute("SELECT review, rating, \"bookID\", \"firstName\", title FROM reviews JOIN users ON users.\"ID\" = reviews.\"userID\" WHERE \"bookID\" = :ID", {"ID":bookID}).fetchall()
        if len(own_reviews) == 0:
            own_reviews = [{"review": "No Reviews have been left for this book yet, be the first and leave your review now"}]
        return render_template("book.html", book=book, goodreadsdata=goodreadsdata, own_reviews=own_reviews)

@app.route("/api/<isbn>", methods=["GET"])
@login_required
def book_api(isbn):
    # First make sure that the book requested actually exists
    book = db.execute("SELECT * FROM public.books WHERE \"ISBN\" = :isbn", {"isbn":str(isbn)}).fetchone()
    print(book)
    if book is None:
        return jsonify({"error": "Invalid isbn"}), 422

    # get the goodreads data needed
    goodreadsdata = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": os.getenv("GOODREADS_APIKEY"), "isbns": book["ISBN"]}).json()
    
    # return api request data
    return jsonify({
        "title": book["title"],
        "author": book["author"],
        "year": book["year"],
        "isbn": book["ISBN"],
        "review_count": goodreadsdata['books'][0]['work_ratings_count'],
        "average_score": goodreadsdata['books'][0]['average_rating']
    })


    
