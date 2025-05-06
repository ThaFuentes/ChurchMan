import sqlite3
from db_handler import get_db_connection

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # ----- USERS TABLE -----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name       TEXT    NOT NULL,
            last_name        TEXT    NOT NULL,
            email            TEXT    UNIQUE,
            phone            TEXT,
            address          TEXT,
            username         TEXT    UNIQUE,
            password         TEXT,
            role             TEXT    NOT NULL,
            accepts_emails   BOOLEAN,
            birthday         TEXT,
            show_birthday    BOOLEAN DEFAULT 0,
            created_by       INTEGER,
            last_edited_by   INTEGER,
            needs_approval   BOOLEAN DEFAULT 1,
            approved_by      INTEGER,
            FOREIGN KEY(created_by)     REFERENCES users(id),
            FOREIGN KEY(last_edited_by) REFERENCES users(id),
            FOREIGN KEY(approved_by)    REFERENCES users(id)
        );
    """)
    existing = {col[1] for col in cursor.execute("PRAGMA table_info(users);").fetchall()}
    for col_def in [
        ("birthday", "TEXT"),
        ("show_birthday", "BOOLEAN DEFAULT 0"),
        ("created_by", "INTEGER"),
        ("last_edited_by", "INTEGER"),
        ("needs_approval", "BOOLEAN DEFAULT 1"),
        ("approved_by", "INTEGER")
    ]:
        if col_def[0] not in existing:
            cursor.execute(f"ALTER TABLE users ADD COLUMN {col_def[0]} {col_def[1]};")

    # ----- ANNOUNCEMENTS TABLE -----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS announcements (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            title                 TEXT    NOT NULL,
            content               TEXT    NOT NULL,
            user_id               INTEGER NOT NULL,
            created_at            DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at            DATETIME DEFAULT CURRENT_TIMESTAMP,
            effective_date        DATETIME,
            expiration_date       DATETIME,
            is_active             BOOLEAN DEFAULT 1,
            comments_enabled      BOOLEAN DEFAULT 1,
            created_by            INTEGER NOT NULL,
            updated_by            INTEGER,
            FOREIGN KEY(user_id)   REFERENCES users(id),
            FOREIGN KEY(created_by) REFERENCES users(id),
            FOREIGN KEY(updated_by) REFERENCES users(id)
        );
    """)

    # ----- ANNOUNCEMENT_COMMENTS TABLE -----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS announcement_comments (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            announcement_id  INTEGER NOT NULL,
            user_id          INTEGER NOT NULL,
            comment          TEXT    NOT NULL,
            date_added       DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(announcement_id) REFERENCES announcements(id),
            FOREIGN KEY(user_id)            REFERENCES users(id)
        );
    """)

    # ----- FAMILY_RELATIONS TABLE -----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS family_relations (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id             INTEGER NOT NULL,
            relative_user_id    INTEGER NOT NULL,
            relation_type       TEXT    NOT NULL,
            created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
            status              TEXT    DEFAULT 'pending',
            approved_by         INTEGER,
            FOREIGN KEY(user_id)          REFERENCES users(id),
            FOREIGN KEY(relative_user_id) REFERENCES users(id),
            FOREIGN KEY(approved_by)      REFERENCES users(id)
        );
    """)
    existing = {col[1] for col in cursor.execute("PRAGMA table_info(family_relations);").fetchall()}
    for col_def in [
        ("created_at", "DATETIME DEFAULT CURRENT_TIMESTAMP"),
        ("status", "TEXT DEFAULT 'pending'"),
        ("approved_by", "INTEGER")
    ]:
        if col_def[0] not in existing:
            cursor.execute(f"ALTER TABLE family_relations ADD COLUMN {col_def[0]} {col_def[1]};")

    # ----- DONATIONS TABLE -----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS donations (
            id     INTEGER PRIMARY KEY AUTOINCREMENT,
            name   TEXT    NOT NULL,
            amount REAL    NOT NULL,
            date   TEXT    NOT NULL,
            method TEXT    NOT NULL,
            notes  TEXT
        );
    """)

    # ----- CHANGE_RECORDS TABLE -----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS change_records (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER,
            action          TEXT    NOT NULL,
            target_id       INTEGER,
            target_username TEXT,
            change_details  TEXT,
            timestamp       DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
    """)

    # ----- EVENTS TABLE -----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id                        INTEGER PRIMARY KEY AUTOINCREMENT,
            event_name                TEXT    NOT NULL,
            event_date                TEXT    NOT NULL,
            event_time                TEXT    NOT NULL,
            location                  TEXT,
            description               TEXT,
            speaker_host              TEXT,
            special_guests            TEXT,
            theme                     TEXT,
            agenda                    TEXT,
            registration_info         TEXT,
            cost_fees                 REAL,
            contact_info              TEXT,
            childcare_availability    TEXT,
            accessibility             TEXT,
            promotional_materials     TEXT,
            volunteer_opportunities   TEXT,
            parking_info              TEXT,
            dress_code                TEXT,
            food_beverages            TEXT,
            event_sponsor             TEXT,
            social_media_hashtag      TEXT,
            donation_info             TEXT,
            safety_protocols          TEXT,
            follow_up                 TEXT,
            event_coordinator         TEXT,
            announcements_reminders   TEXT,
            feedback_form             TEXT,
            live_streaming_details    TEXT,
            event_objectives          TEXT,
            is_potluck                INTEGER DEFAULT 0
        );
    """)

    # ----- POTLUCK_CONTRIBUTIONS TABLE -----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS potluck_contributions (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id     INTEGER NOT NULL,
            user_id      INTEGER,
            contribution TEXT    NOT NULL,
            created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(event_id) REFERENCES events(id),
            FOREIGN KEY(user_id)  REFERENCES users(id)
        );
    """)

    # ----- APP_EMAIL_SETTINGS TABLE -----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS app_email_settings (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            app_name       TEXT    NOT NULL,
            email_server   TEXT,
            email_port     INTEGER,
            smtp_server    TEXT,
            smtp_port      INTEGER,
            email_mode     TEXT,
            email_address  TEXT,
            email_password TEXT
        );
    """)

    # ----- CHURCH_EMAIL_SETTINGS TABLE -----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS church_email_settings (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            church_name    TEXT    NOT NULL,
            email_server   TEXT,
            email_port     INTEGER,
            smtp_server    TEXT,
            smtp_port      INTEGER,
            email_mode     TEXT,
            email_address  TEXT,
            email_password TEXT
        );
    """)

    # ----- SETTINGS TABLE (includes POP3/SMTP fields) -----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            export_location         TEXT,
            sermon_folder_location  TEXT,
            church_name             TEXT,
            tax_status              TEXT,
            address                 TEXT,
            phone_number            TEXT,
            pastor                  TEXT,
            icon_path               TEXT,
            incoming_protocol       TEXT,
            incoming_server         TEXT,
            incoming_port           INTEGER,
            incoming_encryption     TEXT,
            incoming_username       TEXT,
            incoming_password       TEXT,
            outgoing_server         TEXT,
            outgoing_port           INTEGER,
            outgoing_encryption     TEXT,
            outgoing_username       TEXT,
            outgoing_password       TEXT
        );
    """)

    # ----- PRAYERS TABLE -----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS prayers (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            title        TEXT    NOT NULL,
            description  TEXT    NOT NULL,
            user_id      INTEGER NOT NULL,
            date_posted  TEXT    NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
    """)

    # ----- PRAYERS_ADDED TABLE -----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS prayers_added (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            prayer_request_id  INTEGER NOT NULL,
            user_id            INTEGER NOT NULL,
            prayer             TEXT    NOT NULL,
            date_added         TEXT    NOT NULL,
            FOREIGN KEY(prayer_request_id) REFERENCES prayers(id),
            FOREIGN KEY(user_id)            REFERENCES users(id)
        );
    """)

    # ----- MEMBER_ROLES TABLE -----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS member_roles (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id   INTEGER NOT NULL,
            role_name TEXT    NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
    """)

    # ----- USER_WIDGETS TABLE -----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_widgets (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            widget_name TEXT    NOT NULL,
            is_enabled  BOOLEAN DEFAULT 1,
            UNIQUE(user_id, widget_name),
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
    """)

    # ----- SERMONS TABLE -----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sermons (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            title           TEXT    NOT NULL,
            author          TEXT    NOT NULL,
            notes           TEXT,
            details         TEXT,
            sermon_file     TEXT,
            external_link   TEXT,
            uploaded_by     INTEGER NOT NULL,
            uploaded_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(uploaded_by) REFERENCES users(id)
        );
    """)

    # ----- SERMON_COMMENTS TABLE -----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sermon_comments (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            sermon_id   INTEGER NOT NULL,
            user_id     INTEGER NOT NULL,
            comment     TEXT    NOT NULL,
            date_added  DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(sermon_id) REFERENCES sermons(id),
            FOREIGN KEY(user_id)    REFERENCES users(id)
        );
    """)

    # ----- DREAMS TABLE -----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dreams (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id          INTEGER NOT NULL,
            title            TEXT    NOT NULL,
            description      TEXT    NOT NULL,
            notes            TEXT,
            is_personal      BOOLEAN NOT NULL DEFAULT 1,
            date_posted      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            date_occurred    TIMESTAMP,
            visibility       TEXT    NOT NULL DEFAULT 'public',
            comments_count   INTEGER DEFAULT 0,
            category         TEXT,
            is_approved      BOOLEAN DEFAULT 1,
            approved_by      INTEGER,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(approved_by) REFERENCES users(id)
        );
    """)

    # ----- DREAM_COMMENTS TABLE -----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dream_comments (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            dream_id     INTEGER NOT NULL,
            user_id      INTEGER NOT NULL,
            comment      TEXT    NOT NULL,
            date_posted  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(dream_id) REFERENCES dreams(id),
            FOREIGN KEY(user_id)  REFERENCES users(id)
        );
    """)

    # ----- PROPHECIES TABLE -----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS prophecies (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            title        TEXT    NOT NULL,
            description  TEXT,
            user_id      INTEGER,
            date_posted  DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
    """)

    # ----- PROPHECY_COMMENTS TABLE -----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS prophecy_comments (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            prophecy_id  INTEGER NOT NULL,
            user_id      INTEGER NOT NULL,
            comment      TEXT    NOT NULL,
            date_added   DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(prophecy_id) REFERENCES prophecies(id),
            FOREIGN KEY(user_id)     REFERENCES users(id)
        );
    """)

    conn.commit()
    conn.close()


if __name__ == '__main__':
    init_db()
    print("Database initialized successfully.")
