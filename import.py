import os
import csv

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

engine = create_engine(os.getenv("DATABASE_URL"))                                             
db = scoped_session(sessionmaker(bind=engine))

# open the csv containing all the 
with open("books.csv") as file:
    reader = csv.reader(file)
    # skip header
    header = next(reader)
    for isbn, title, author, year in reader:
        db.execute("INSERT INTO books (\"ISBN\", title, author, year) VALUES (:isbn, :title, :author, :year)", {"isbn" : isbn, "title": title,"author": author,"year": year})
        print(f"Added {title} written by {author} in {year}, isbn is {isbn}")
    db.commit()
    print("Upload complete")