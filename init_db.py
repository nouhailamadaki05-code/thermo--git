import os
import sqlite3
import bcrypt

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
USERS_DB  = os.path.join(BASE_DIR, "users.db")
THERMO_DB = os.path.join(BASE_DIR, "thermo.db")

print("Creation des bases de donnees...")

# ══════════════════════════════════════════
#   users.db
# ══════════════════════════════════════════
conn = sqlite3.connect(USERS_DB)
cur  = conn.cursor()

cur.execute("""CREATE TABLE IF NOT EXISTS users (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    nom              TEXT    NOT NULL,
    email            TEXT    UNIQUE NOT NULL,
    password_hash    TEXT    NOT NULL,
    is_admin         INTEGER DEFAULT 0,
    ip_address       TEXT,
    pays             TEXT,
    user_agent       TEXT,
    date_inscription DATETIME DEFAULT CURRENT_TIMESTAMP
)""")

cur.execute("""CREATE TABLE IF NOT EXISTS user_logs (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id        INTEGER,
    ip_address     TEXT,
    pays           TEXT,
    user_agent     TEXT,
    date_connexion DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id)
)""")

cur.execute("""CREATE TABLE IF NOT EXISTS password_reset (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL,
    token         TEXT    UNIQUE NOT NULL,
    date_creation DATETIME DEFAULT CURRENT_TIMESTAMP,
    utilise       INTEGER DEFAULT 0,
    FOREIGN KEY(user_id) REFERENCES users(id)
)""")

# Admin
pwd_admin = bcrypt.hashpw(b"admin123", bcrypt.gensalt()).decode()
cur.execute("""INSERT OR IGNORE INTO users (nom, email, password_hash, is_admin)
    VALUES ('thermonouha', 'admin@thermo.app', ?, 1)""", (pwd_admin,))

# Utilisateur par defaut
pwd_user = bcrypt.hashpw(b"user123", bcrypt.gensalt()).decode()
cur.execute("""INSERT OR IGNORE INTO users (nom, email, password_hash, is_admin)
    VALUES ('Utilisateur', 'user@thermo.app', ?, 0)""", (pwd_user,))

conn.commit()
conn.close()
print("  users.db   OK")

# ══════════════════════════════════════════
#   thermo.db
# ══════════════════════════════════════════
conn = sqlite3.connect(THERMO_DB)
cur  = conn.cursor()

cur.execute("""CREATE TABLE IF NOT EXISTS composants (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nom         TEXT,
    Psat        REAL,
    temperature REAL
)""")

cur.execute("SELECT COUNT(*) FROM composants")
if cur.fetchone()[0] == 0:
    cur.execute("""INSERT INTO composants (nom, Psat, temperature)
        VALUES ('benzene', 101.3, 80), ('toluene', 40.0, 80)""")

conn.commit()
conn.close()
print("  thermo.db  OK")

print("")
print("=" * 50)
print("  COMPTES DISPONIBLES")
print("-" * 50)
print("  ADMIN")
print("    Email    : admin@thermo.app")
print("    Mdp      : admin123")
print("    Acces    : Panneau Admin")
print("-" * 50)
print("  UTILISATEUR")
print("    Email    : user@thermo.app")
print("    Mdp      : user123")
print("    Acces    : Page Calculs")
print("=" * 50)
