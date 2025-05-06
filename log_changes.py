from db_handler import get_db_connection


def log_change(user_id, action, target_id=None, target_username=None, change_details=None):
    """
    Logs changes made by users into the change_records table.

    :param user_id: ID of the user performing the action
    :param action: Description of the action performed
    :param target_id: ID of the target affected by the action (optional)
    :param target_username: Username of the target affected (optional)
    :param change_details: Additional details about the change (optional)
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO change_records (user_id, action, target_id, target_username, change_details)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, action, target_id, target_username, change_details))
    conn.commit()
    conn.close()


if __name__ == "__main__":
    # Example usage
    log_change(user_id=1, action='update', target_id=2, target_username='example_user',
               change_details='Updated user profile.')
    print("Change logged successfully.")
