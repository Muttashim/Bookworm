import os,csv
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

def create_tables(db):
	# Create table for books
	command = "CREATE TABLE books (isbn varchar PRIMARY KEY,title varchar NOT NULL,author varchar NOT NULL, year int NOT NULL);"
	db.execute(command)

	# Create table for users
	command = "CREATE TABLE users (username varchar PRIMARY KEY,password varchar NOT NULL,fullname varchar NOT NULL);"
	db.execute(command)

	# Create table for reviews
	command = "CREATE TABLE reviews (review_id int PRIMARY KEY,description varchar,rating int NOT NULL,isbn varchar REFERENCES books(isbn),username varchar REFERENCES users(username));"
	db.execute(command)
	db.commit()


def insert_data(isbn, title, author, year, db):
	# Insert details of a book to books table
	ins_command = "INSERT INTO books (isbn, title, author, year) VALUES (:isbn, :title, :author, :year)"
	db.execute(ins_command, {"isbn":isbn, "title":title, "author":author, "year":year})
	print("Added to books " + title)

def main():
	# Check for environment variable
	if not os.getenv("DATABASE_URL"):
	    raise RuntimeError("DATABASE_URL is not set")

	# Set up database
	engine = create_engine(os.getenv("DATABASE_URL"))
	db = scoped_session(sessionmaker(bind=engine))

	# Create the tables
	create_tables(db)

	# Read the books file to create database
	data = open("books.csv")
	reader = csv.reader(data)

	# Counts for the number of entries in books
	counter = -1

	for isbn,title,author,year in reader:

		# Check if the titles of columns are read
		if counter is -1:
			counter += 1
			continue

		# Insert each book to books table
		year = int(year)
		insert_data(isbn,title,author,year,db)
		counter += 1

	# Commit database modifications
	db.commit()
	print(f"Added {counter} books to database.")

if __name__== "__main__":
	main()
