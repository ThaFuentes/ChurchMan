import sqlite3

DATABASE = 'church_management.db'


def get_db_connection():
    """Establish and return a database connection with row factory enabled."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row  # Enables column access by name
    return conn
