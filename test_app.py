import sys

print("1. Python Version:", sys.version.split()[0])

try:
    import flask
    print("2. Flask is installed properly!")
except ImportError as e:
    print("2. Flask import FAILED:", e)

try:
    import mysql.connector
    print("3. MySQL Connector is installed properly!")
except ImportError as e:
    print("3. MySQL Connector import FAILED:", e)

try:
    db = mysql.connector.connect(
        host='localhost',
        user='root',
        password='Bw@ing404', # Put your MySQL root password here if you have one
        database='carbon_db'
    )
    print("4. Connected to MySQL database 'carbon_db' successfully!")
    db.close()
except Exception as e:
    print("4. MySQL Connection FAILED:", e)

print("--- DIAGNOSTIC COMPLETE ---")