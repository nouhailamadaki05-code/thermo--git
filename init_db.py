import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Table composants
cursor.execute("""
CREATE TABLE IF NOT EXISTS composants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT,
    Psat REAL,
    temperature REAL
)
""")

# Supprimer anciennes données (optionnel)
cursor.execute("DELETE FROM composants")

# Insérer données fixes
cursor.execute("""
INSERT INTO composants (nom, Psat, temperature)
VALUES 
('benzene', 101.3, 80),
('toluene', 40.0, 80)
""")

conn.commit()
conn.close()

print("Base initialisée avec données !")