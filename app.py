from flask import Flask, render_template, request
import sqlite3

app = Flask(__name__)

def calculer(x1, x2, P1_sat, P2_sat):
    P_bulle = x1 * P1_sat + x2 * P2_sat
    y1 = (x1 * P1_sat) / P_bulle
    y2 = (x2 * P2_sat) / P_bulle
    return P_bulle, y1, y2

@app.route("/", methods=["GET", "POST"])
def index():
    resultats = None

    # Récupérer données depuis DB
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM composants")
    data = cursor.fetchall()
    conn.close()

    # benzene = data[0], toluene = data[1]
    P1_sat = data[0][2]
    P2_sat = data[1][2]
    T = data[0][3]

    if request.method == "POST":
        x1 = float(request.form["x1"])
        x2 = float(request.form["x2"])

        P_bulle, y1, y2 = calculer(x1, x2, P1_sat, P2_sat)

        resultats = {
            "P_bulle": round(P_bulle, 2),
            "y1": round(y1, 4),
            "y2": round(y2, 4),
            "somme": round(y1 + y2, 4),
            "T": T,
            "P1": P1_sat,
            "P2": P2_sat
        }

    return render_template("index.html", resultats=resultats)

if __name__ == "__main__":
    app.run(debug=True)