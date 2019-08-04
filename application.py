import os,requests
from datetime import datetime
from flask import Flask, session, render_template, request, redirect, url_for, session, abort, jsonify
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from collections import defaultdict

app = Flask(__name__)

# Initialize goodreads api key
GOODREADS_API_KEY = ""

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))

# Index page 
@app.route("/")
def index():
	# Check if users is in session
	if session.get("users") is None:
		session["users"] = []
	return render_template("index.html", username=None)

# User page
@app.route("/users/<string:username>")
def users(username):

	# Check if user is logged in.
	if username not in session["users"]:
		return redirect(url_for('index'))

	# Fetch fullname of user and add it to session variables for that user
	fullname = db.execute("SELECT fullname FROM users WHERE username=:username", 
						{"username" : username}).fetchone()
	if session.get(username + '_fullname') is None:
		session[username + '_fullname'] = fullname[0]

	return render_template("user.html",fullname = session[username + '_fullname'], username=username)

# Process login information 
@app.route("/login", methods=['post'])
def login():

	# Get credentials from request
	username = request.form.get('username')
	password = request.form.get('password')

	# Check if credentials are correct
	user_check = db.execute("SELECT username FROM users WHERE username=:username AND password=:password",
		{"username" : username, "password" : password}).fetchone()

	# Redirect to error page if incorrect credentials are provided
	if user_check == None:
		error_msg = "Seems like the username or password was incorrect!"
		img_url = "https://www.seekclipart.com/clipng/big/62-621663_error-image-error-clipart.png"
		return render_template("error.html", error_msg=error_msg, img_url=img_url, 
			err_type="incorrect_data", prev=url_for('index'))

	# Add user to session and redirect to users page
	session["users"].append(username)
	return redirect(url_for('users',username=username))		

# Process new registrations
@app.route("/register", methods=['post'])
def register():

	# Get username from request
	username = request.form.get('username')

	# Check if username already exists 
	username_check = db.execute("SELECT username FROM users WHERE username=:username", {"username":username}).fetchone()
	if username_check is not None:
		error_msg = "Seems like the username is already taken!"
		img_url = "https://www.seekclipart.com/clipng/big/62-621663_error-image-error-clipart.png"
		return  render_template("error.html", error_msg=error_msg, 
							img_url= img_url, err_type="not_available", prev=url_for('index'))

	# If username is unique get other details from request
	password = request.form.get('password')
	fullname = request.form.get('fullname')

	# Add user to database
	insert = "INSERT INTO users(username,password,fullname) VALUES (:username,:password,:fullname)"
	db.execute(insert, {"username":username, "password":password, "fullname":fullname})
	db.commit()

	# Add user to session and redirect to users page
	session["users"].append(username)
	return redirect(url_for('users',username=username))

# Process a logout request
@app.route("/logout", methods=["post"])
def logout():
	username = request.form.get('username')

	# Remove user related information from session
	session[username] = None
	session["users"] = list(set(session["users"]))
	session["users"].remove(username)
	return redirect(url_for('index'))

# Show search results
@app.route("/search/<string:user>/<int:page_no>", methods=["post", "get"])
def search(user,page_no):
	username = user

	# Check if a new search query is made
	if request.method == "POST":

		# Get search query details
		search_type = request.form.get('search_type')
		search_query = request.form.get('query')
		sort_by = request.form.get('sort_by')
		sort_order = request.form.get('sort_order')

		# Start timer for calculating data fetch time delay
		start = datetime.now()

		# Fetch the required data
		command = f"SELECT isbn,title,author,year FROM books WHERE {search_type} ILIKE '%{search_query}%' ORDER BY {sort_by} {sort_order}"
		data = db.execute(command).fetchall()

		# End the timer and calculate delay
		end = datetime.now()
		delay = end-start
		delay = str(delay.seconds) +"."+ str(delay.microseconds)[:2]

		# Display error if nothing was found
		if len(data) is 0:
			error_msg = "Seems like nothing was found!"
			img_url = "https://cdn.dribbble.com/users/1208688/screenshots/4563859/no-found.gif"
			return render_template("error.html", error_msg=error_msg, img_url=img_url, 
				err_type="not_found", prev=url_for('users', username=username), username=username)

		# Add or update delay to the user session
		if session.get(username+'_delay') is None:
			session[username+'_delay'] = delay
		session[username+'_delay'] = delay

		# Add or update search query to session
		if session.get(username + '_query') is None:
			session[username + '_query'] = search_query
		session[username + '_query'] = search_query

		# Add the results to user session
		if session.get(username) is None:
			session[username] = []
		session[username] = data

	# Get the start and end indices for current result page
	start = (page_no-1)*20
	end = min(start + 20,len(session[username]))

	# Display the page
	return render_template("search.html", username=username, fullname=session[username+'_fullname'], count=len(session[username]),
						 delay=session[username+'_delay'], books=session[username][start:end],
						 page_no=page_no, query=session[username + '_query']) 

# Detailed information of a book
@app.route("/books/<string:user>/<string:isbn>")
def books(user,isbn):
	username = user


	# Fetch details of the book with given isbn		
	data = db.execute("SELECT isbn,title,author,year FROM books WHERE isbn LIKE :isbn", {"isbn":isbn}).fetchone()
	if data is None:
		error_msg = "Some internal error occurred!"
		img_url = "https://www.seekclipart.com/clipng/big/62-621663_error-image-error-clipart.png"
		return render_template("error.html", error_msg=error_msg, img_url=img_url, 
			err_type="internal", prev=url_for('users', username=user), username=username)

	data = list(data)

	# Specify Goodreads API key 
	api_key = GOODREADS_API_KEY

	# Get rating information from Goodreads API
	ratings = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": api_key, "isbns": data[0]})
	ratings = ratings.json()['books'][0]

	# Add goodreads data to book data
	data.append(ratings['work_ratings_count'])
	data.append(ratings['average_rating'])

	# Fetch reviews for this book
	review_data = db.execute("SELECT rating,fullname,description FROM reviews NATURAL JOIN users WHERE isbn LIKE :isbn", {"isbn":isbn}).fetchall()
	return render_template("books.html", username=user, fullname= session[user+'_fullname'],
							details=data, reviews=review_data)

# Process a review submission
@app.route("/submit_review", methods=["post"])
def submit_review():

	# Get the details from request
	username= request.form.get('username')
	rating = request.form.get('rating')
	description = request.form.get('description')
	isbn = request.form.get('isbn')

	# Check if user has already posted a review for current book
	check_repeat = db.execute("SELECT * FROM reviews WHERE username LIKE :username AND isbn LIKE :isbn", 
							{"username":username, "isbn":isbn }).fetchone()

	if not check_repeat is None:
		error_msg = "You have already posted a reviewed for this book!"
		img_url = "https://www.seekclipart.com/clipng/big/62-621663_error-image-error-clipart.png"
		return render_template("error.html", error_msg=error_msg, img_url=img_url, 
			err_type="repeat", prev=url_for('books', user=username, isbn=isbn), username=username)

	# Generate a review_id
	review_id = db.execute("SELECT review_id FROM reviews ORDER BY review_id DESC").fetchone()
	review_id = review_id[0]
	if review_id is None:
		review_id = 100
	else:
		review_id += 1

	# Insert the review details into reviews table
	db.execute("INSERT INTO reviews(review_id, description, rating, isbn, username) VALUES (:review_id, :description, :rating, :isbn, :username)",
				{"review_id":review_id, "description":description, "rating":rating, "isbn":isbn, "username":username}) 
	db.commit()
	return redirect(url_for('books', user=username, isbn=isbn))

# Process an API request
@app.route("/api/<string:isbn>")
def api(isbn):

	# Check if a book with given isbn is present in database
	data = db.execute("SELECT title, author, year FROM books WHERE isbn LIKE :isbn", {"isbn":isbn}).fetchone()
	if data is None:
		# Return a 404 not found error 
		abort(404)
	details = defaultdict()
	details['title'] = data[0]
	details['author'] = data[1]
	details['year'] = data[2]
	details['isbn'] = isbn

	# Get goodreads rating details
	api_key = GOODREADS_API_KEY
	ratings = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": api_key, "isbns": isbn})
	ratings = ratings.json()['books'][0]
	details['review_count'] = ratings['work_ratings_count']
	details['average_rating'] = ratings['average_rating']

	# Return a JSON object as response
	return jsonify(details) 