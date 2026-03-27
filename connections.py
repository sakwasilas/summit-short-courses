from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Correct connection string
path = "mysql+pymysql://root:2480@localhost/shortcourse_db"

engine = create_engine(path)

SessionLocal = sessionmaker(bind=engine)
Session = SessionLocal()

Base = declarative_base()