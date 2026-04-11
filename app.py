import os
import bcrypt
import secrets
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for
from flask_login import (LoginManager, login_user, logout_user,
                         login_required, UserMixin, current_user)

try:
    import psycopg2
    import psycopg2.extras
    USE_POSTGRES = True
except ImportError:
    import sqlite3
    USE_POSTGRES = False

# ════════════════════════════════════════════════════════════
#  CONFIG
# ════════════════════════════════════════════════════════════
BASE_DIR       = os.path.dirname(os.path.abspath(__file__))
DATABASE_URL   = os.environ.get("DATABASE_URL", "")
GMAIL_USER     = os.environ.get("GMAIL_USER", "votre.email@gmail.com")
GMAIL_PASSWORD = os.environ.get("GMAIL_PASSWORD", "xxxx xxxx xxxx xxxx")
APP_URL        = os.environ.get("APP_URL", "http://127.0.0.1:5000")

# ════════════════════════════════════════════════════════════
#  CONNEXION BASE DE DONNEES
#  PostgreSQL si disponible, SQLite sinon (local)
# ════════════════════════════════════════════════════════════
def get_conn():
    if DATABASE_URL and USE_POSTGRES:
        url = DATABASE_URL.replace("postgres://", "postgresql://", 1)
        conn = psycopg2.connect(url)
        conn.autocommit = False
        return conn, "pg"
    else:
        import sqlite3
        users_db = os.path.join(BASE_DIR, "users.db")
        conn = sqlite3.connect(users_db)
        conn.row_factory = sqlite3.Row
        return conn, "sqlite"

def get_thermo_conn():
    import sqlite3
    thermo_db = os.path.join(BASE_DIR, "thermo.db")
    conn = sqlite3.connect(thermo_db)
    return conn

def ph(n):
    """Placeholder : %s pour postgres, ? pour sqlite"""
    if DATABASE_URL and USE_POSTGRES:
        return "%s"
    return "?"

def fetchall(cur):
    rows = cur.fetchall()
    if DATABASE_URL and USE_POSTGRES:
        return [tuple(r) for r in rows]
    return [tuple(r) for r in rows]

def fetchone(cur):
    row = cur.fetchone()
    if row is None:
        return None
    return tuple(row)

# ════════════════════════════════════════════════════════════
#  INIT BASE DE DONNEES
# ════════════════════════════════════════════════════════════
def init_db():
    conn, mode = get_conn()
    cur = conn.cursor()

    if mode == "pg":
        # PostgreSQL — utilise SERIAL et TIMESTAMP
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id               SERIAL PRIMARY KEY,
                nom              TEXT    NOT NULL,
                email            TEXT    UNIQUE NOT NULL,
                password_hash    TEXT    NOT NULL,
                is_admin         INTEGER DEFAULT 0,
                ip_address       TEXT,
                pays             TEXT,
                user_agent       TEXT,
                date_inscription TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_logs (
                id             SERIAL PRIMARY KEY,
                user_id        INTEGER,
                ip_address     TEXT,
                pays           TEXT,
                user_agent     TEXT,
                date_connexion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS password_reset (
                id            SERIAL PRIMARY KEY,
                user_id       INTEGER NOT NULL,
                token         TEXT    UNIQUE NOT NULL,
                date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                utilise       INTEGER DEFAULT 0
            )
        """)
    else:
        # SQLite — local
        cur.execute("""CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL, is_admin INTEGER DEFAULT 0,
            ip_address TEXT, pays TEXT, user_agent TEXT,
            date_inscription DATETIME DEFAULT CURRENT_TIMESTAMP
        )""")
        cur.execute("""CREATE TABLE IF NOT EXISTS user_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
            ip_address TEXT, pays TEXT, user_agent TEXT,
            date_connexion DATETIME DEFAULT CURRENT_TIMESTAMP
        )""")
        cur.execute("""CREATE TABLE IF NOT EXISTS password_reset (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL, token TEXT UNIQUE NOT NULL,
            date_creation DATETIME DEFAULT CURRENT_TIMESTAMP,
            utilise INTEGER DEFAULT 0
        )""")

    P = ph(None)

    # Admin par defaut
    cur.execute(f"SELECT COUNT(*) FROM users WHERE is_admin=1")
    row = fetchone(cur)
    if row[0] == 0:
        pwd = bcrypt.hashpw(b"admin123", bcrypt.gensalt()).decode()
        cur.execute(f"INSERT INTO users (nom,email,password_hash,is_admin) VALUES ({P},{P},{P},{P}) ON CONFLICT (email) DO NOTHING" if mode=="pg" else
                    f"INSERT OR IGNORE INTO users (nom,email,password_hash,is_admin) VALUES ({P},{P},{P},{P})",
                    ("thermonouha","admin@thermo.app", pwd, 1))

    # Utilisateur par defaut
    cur.execute(f"SELECT COUNT(*) FROM users WHERE email={P}", ("user@thermo.app",))
    row = fetchone(cur)
    if row[0] == 0:
        pwd = bcrypt.hashpw(b"123456", bcrypt.gensalt()).decode()
        cur.execute(f"INSERT INTO users (nom,email,password_hash,is_admin) VALUES ({P},{P},{P},{P}) ON CONFLICT (email) DO NOTHING" if mode=="pg" else
                    f"INSERT OR IGNORE INTO users (nom,email,password_hash,is_admin) VALUES ({P},{P},{P},{P})",
                    ("Utilisateur","user@thermo.app", pwd, 0))

    conn.commit()
    conn.close()

def init_thermo():
    conn = get_thermo_conn()
    cur  = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS composants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT, Psat REAL, temperature REAL
    )""")
    cur.execute("SELECT COUNT(*) FROM composants")
    if cur.fetchone()[0] == 0:
        cur.execute("INSERT INTO composants (nom,Psat,temperature) VALUES (?,?,?)", ("benzene",101.3,80))
    cur.execute("INSERT INTO composants (nom,Psat,temperature) VALUES (?,?,?)", ("toluene",40.0,80))
    conn.commit()
    conn.close()

init_db()
init_thermo()

# ════════════════════════════════════════════════════════════
#  FLASK
# ════════════════════════════════════════════════════════════
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "thermo_v2_secret_2026")

login_manager = LoginManager(app)
login_manager.login_view = "welcome"

class User(UserMixin):
    def __init__(self, id, nom, email, is_admin=False):
        self.id = id; self.nom = nom
        self.email = email; self.is_admin = bool(is_admin)

@login_manager.user_loader
def load_user(user_id):
    conn, _ = get_conn()
    cur = conn.cursor()
    P = ph(None)
    cur.execute(f"SELECT id,nom,email,is_admin FROM users WHERE id={P}", (user_id,))
    row = fetchone(cur)
    conn.close()
    return User(*row) if row else None

def get_country(ip):
    try:
        r = requests.get(f"https://ipapi.co/{ip}/country_name/", timeout=3)
        return r.text.strip()
    except:
        return "Inconnu"

def parse_date(s):
    if not s: return None
    if isinstance(s, datetime): return s
    s = str(s).strip().replace("T"," ")
    if "." in s: s = s.split(".")[0]
    try: return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
    except: return None

def send_reset_email(email_dest, token):
    lien = f"{APP_URL}/reset-password/{token}"
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Reinitialisation mot de passe ThermoApp"
        msg["From"] = GMAIL_USER; msg["To"] = email_dest
        msg.attach(MIMEText(f"Lien : {lien}\nExpire dans 24h.", "plain"))
        html = f"""<html><body style="font-family:Arial;background:#0a0a0f;padding:40px;">
        <div style="max-width:480px;margin:0 auto;background:#1a1a26;border-radius:16px;padding:32px;border:1px solid #2a2a40;">
          <h2 style="color:#6c63ff;">ThermoApp V2</h2>
          <h3 style="color:#e8e8f0;">Reinitialisation du mot de passe</h3>
          <a href="{lien}" style="display:inline-block;margin:20px 0;padding:14px 28px;
             background:#6c63ff;color:#fff;border-radius:10px;text-decoration:none;font-weight:bold;">
             Reinitialiser mon mot de passe
          </a>
          <p style="color:#7070a0;font-size:13px;">Expire dans 24 heures.</p>
          <p style="color:#555580;font-size:11px;"><a href="{lien}" style="color:#6c63ff;">{lien}</a></p>
        </div></body></html>"""
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(GMAIL_USER, GMAIL_PASSWORD)
            smtp.send_message(msg)
        return True, None
    except smtplib.SMTPAuthenticationError:
        return False, "auth"
    except Exception as e:
        return False, str(e)

# ════════════════════════════════════════════════════════════
#  PAGE ACCUEIL
# ════════════════════════════════════════════════════════════
@app.route("/", methods=["GET","POST"])
def welcome():
    if current_user.is_authenticated:
        return redirect(url_for("admin") if current_user.is_admin else url_for("calcul"))
    error_login = error_register = success = reset_link = None
    if request.method == "POST":
        action = request.form.get("action")
        P = ph(None)

        if action == "login":
            email    = request.form.get("email","").strip()
            password = request.form.get("password","").encode()
            conn, _ = get_conn(); cur = conn.cursor()
            cur.execute(f"SELECT id,nom,email,password_hash,is_admin FROM users WHERE email={P}", (email,))
            row = fetchone(cur); conn.close()
            if row and bcrypt.checkpw(password, row[3].encode()):
                user = User(row[0], row[1], row[2], row[4])
                login_user(user)
                ip = request.remote_addr
                conn2, _ = get_conn()
                conn2.cursor().execute(
                    f"INSERT INTO user_logs (user_id,ip_address,pays,user_agent) VALUES ({P},{P},{P},{P})",
                    (user.id, ip, get_country(ip), request.headers.get("User-Agent","")))
                conn2.commit(); conn2.close()
                return redirect(url_for("admin") if user.is_admin else url_for("calcul"))
            else:
                error_login = "Email ou mot de passe incorrect."

        elif action == "register":
            nom      = request.form.get("nom","").strip()
            email    = request.form.get("reg_email","").strip()
            password = request.form.get("reg_password","")
            confirm  = request.form.get("reg_confirm","")
            if not nom or not email or not password:
                error_register = "Tous les champs sont obligatoires."
            elif password != confirm:
                error_register = "Les mots de passe ne correspondent pas."
            elif len(password) < 6:
                error_register = "Mot de passe trop court (minimum 6 caracteres)."
            else:
                hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
                ip = request.remote_addr
                try:
                    conn, mode = get_conn(); cur = conn.cursor()
                    if mode == "pg":
                        cur.execute(f"INSERT INTO users (nom,email,password_hash,ip_address,pays,user_agent) VALUES ({P},{P},{P},{P},{P},{P}) ON CONFLICT (email) DO NOTHING",
                            (nom, email, hashed, ip, get_country(ip), request.headers.get("User-Agent","")))
                    else:
                        cur.execute(f"INSERT OR IGNORE INTO users (nom,email,password_hash,ip_address,pays,user_agent) VALUES ({P},{P},{P},{P},{P},{P})",
                            (nom, email, hashed, ip, get_country(ip), request.headers.get("User-Agent","")))
                    conn.commit(); conn.close()
                    success = f"Compte cree ! Bienvenue {nom}, connectez-vous."
                except Exception:
                    error_register = "Cet email est deja utilise."

        elif action == "forgot":
            email = request.form.get("forgot_email","").strip()
            conn, mode = get_conn(); cur = conn.cursor()
            cur.execute(f"SELECT id FROM users WHERE email={P}", (email,))
            row = fetchone(cur)
            if row:
                cur.execute(f"DELETE FROM password_reset WHERE user_id={P} AND utilise=0", (row[0],))
                token = secrets.token_urlsafe(32)
                cur.execute(f"INSERT INTO password_reset (user_id,token) VALUES ({P},{P})", (row[0], token))
                conn.commit(); conn.close()
                ok, err = send_reset_email(email, token)
                if ok:
                    success = f"Email envoye a {email} ! Verifiez votre boite mail."
                else:
                    reset_link = f"{APP_URL}/reset-password/{token}"
                    success = "Cliquez sur le bouton ci-dessous pour reinitialiser :"
            else:
                conn.close()
                error_login = "Aucun compte trouve avec cet email."

    return render_template("welcome.html",
        error_login=error_login, error_register=error_register,
        success=success, reset_link=reset_link)

# ════════════════════════════════════════════════════════════
#  RESET MOT DE PASSE
# ════════════════════════════════════════════════════════════
@app.route("/reset-password/<token>", methods=["GET","POST"])
def reset_password(token):
    P = ph(None)
    conn, _ = get_conn(); cur = conn.cursor()
    cur.execute(f"SELECT id,user_id,date_creation,utilise FROM password_reset WHERE token={P}", (token,))
    row = fetchone(cur)
    if not row:
        conn.close()
        return render_template("reset_password.html", error="Lien invalide.", token=None)
    reset_id, user_id, date_creation, utilise = row
    if utilise:
        conn.close()
        return render_template("reset_password.html", error="Ce lien a deja ete utilise.", token=None)
    created = parse_date(date_creation)
    if not created or datetime.now() - created > timedelta(hours=24):
        conn.close()
        return render_template("reset_password.html", error="Ce lien a expire. Faites une nouvelle demande.", token=None)
    error = success = None
    if request.method == "POST":
        new_pwd = request.form.get("new_password","")
        confirm = request.form.get("confirm_password","")
        if len(new_pwd) < 6:
            error = "Mot de passe trop court (minimum 6 caracteres)."
        elif new_pwd != confirm:
            error = "Les mots de passe ne correspondent pas."
        else:
            h = bcrypt.hashpw(new_pwd.encode(), bcrypt.gensalt()).decode()
            cur.execute(f"UPDATE users SET password_hash={P} WHERE id={P}", (h, user_id))
            cur.execute(f"UPDATE password_reset SET utilise=1 WHERE id={P}", (reset_id,))
            conn.commit(); conn.close()
            return render_template("reset_password.html",
                success="Mot de passe change ! Connectez-vous maintenant.", token=None)
    conn.close()
    return render_template("reset_password.html", token=token, error=error, success=success)

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("welcome"))

# ════════════════════════════════════════════════════════════
#  CALCULS
# ════════════════════════════════════════════════════════════
@app.route("/calcul", methods=["GET","POST"])
@login_required
def calcul():
    resultats = None
    conn = get_thermo_conn(); cursor = conn.cursor()
    cursor.execute("SELECT * FROM composants")
    data = cursor.fetchall(); conn.close()
    P1_sat = data[0][2]; P2_sat = data[1][2]; T = data[0][3]
    if request.method == "POST":
        x1 = float(request.form["x1"]); x2 = float(request.form["x2"])
        P_bulle = x1*P1_sat + x2*P2_sat
        y1 = (x1*P1_sat)/P_bulle; y2 = (x2*P2_sat)/P_bulle
        resultats = {"P_bulle": round(P_bulle,2), "y1": round(y1,4),
            "y2": round(y2,4), "somme": round(y1+y2,4),
            "T": T, "P1": P1_sat, "P2": P2_sat}
    return render_template("calcul.html", resultats=resultats)

# ════════════════════════════════════════════════════════════
#  ADMIN
# ════════════════════════════════════════════════════════════
@app.route("/admin")
@login_required
def admin():
    if not current_user.is_admin:
        return redirect(url_for("calcul"))
    conn, _ = get_conn(); cursor = conn.cursor()
    cursor.execute("SELECT id,nom,email,pays,date_inscription FROM users WHERE is_admin=0 ORDER BY date_inscription DESC")
    users = fetchall(cursor)
    cursor.execute("""SELECT u.nom,u.email,l.ip_address,l.pays,l.date_connexion
        FROM user_logs l JOIN users u ON u.id=l.user_id
        ORDER BY l.date_connexion DESC LIMIT 50""")
    logs = fetchall(cursor)
    cursor.execute("SELECT pays,COUNT(*) FROM users WHERE is_admin=0 GROUP BY pays ORDER BY COUNT(*) DESC")
    stats_pays = fetchall(cursor)
    cursor.execute("""SELECT pr.id,u.nom,u.email,pr.token,pr.date_creation,pr.utilise
        FROM password_reset pr JOIN users u ON u.id=pr.user_id
        ORDER BY pr.date_creation DESC LIMIT 30""")
    resets = fetchall(cursor)
    conn.close()
    return render_template("admin.html", users=users, logs=logs,
        stats_pays=stats_pays, resets=resets, total_users=len(users))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
