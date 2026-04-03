import sqlite3

conn = sqlite3.connect("database.db")
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