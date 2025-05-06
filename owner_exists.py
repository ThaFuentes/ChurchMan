from db_handler import get_db_connection


def owner_exists():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM users WHERE role = ?', ('Owner',))
    count = cursor.fetchone()[0]
    conn.close()
    return count > 0


if __name__ == "__main__":
    if owner_exists():
        print("Owner exists in the database.")
    else:
        print("No owner found in the database.")
