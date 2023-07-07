from dotenv import load_dotenv, find_dotenv
import os
from mysql.connector import connect

load_dotenv(find_dotenv())

connection = connect(
    host =  os.getenv("host"),
    user = os.getenv("user"),
    password = os.getenv("password"),
    database = os.getenv("database")
)