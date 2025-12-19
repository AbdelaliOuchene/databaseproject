from flask import Flask, render_template, request, redirect, url_for, flash
import mysql.connector
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'votre_cle_secrete_123'

# --------------------------------------
# Configuration MySQL
# --------------------------------------
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '',      # Ajouter password si nécessaire
    'database': 'medical_images'
}


# ------------------------------------------------------------
# HOME PAGE
# ------------------------------------------------------------
# ------------------------------------------------------------
# HOME PAGE
# ------------------------------------------------------------
@app.route('/')
def home():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    # Récupération des statistiques
    cursor.execute("SELECT COUNT(*) AS total FROM Patient")
    total_patients = cursor.fetchone()['total']

    cursor.execute("SELECT COUNT(*) AS total FROM Medecin")
    total_medecins = cursor.fetchone()['total']

    cursor.execute("SELECT COUNT(*) AS total FROM Radiologue")
    total_radiologues = cursor.fetchone()['total']

    cursor.execute("SELECT COUNT(*) AS total FROM ImageMedicale")
    total_images = cursor.fetchone()['total']

    cursor.close()
    db.close()

    return render_template(
        'home.html',
        total_patients=total_patients,
        total_medecins=total_medecins,
        total_radiologues=total_radiologues,
        total_images=total_images
    )

# --------------------------------------
# Upload folder
# --------------------------------------
UPLOAD_FOLDER = 'static/images'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'dcm', 'dicom'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def get_db():
    """Connexion MySQL"""
    conn = mysql.connector.connect(**DB_CONFIG)
    return conn


# ------------------------------------------------------------
# INDEX
# ------------------------------------------------------------
@app.route('/index')
def index():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute('SELECT id_patient, nom, prenom FROM Patient ORDER BY nom')
    patients = cursor.fetchall()

    cursor.execute('SELECT id_medecin, nom, prenom FROM Medecin ORDER BY nom')
    medecins = cursor.fetchall()

    cursor.execute('SELECT id_radiologue, nom, prenom FROM Radiologue ORDER BY nom')
    radiologues = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template('index.html',
                           patients=patients,
                           medecins=medecins,
                           radiologues=radiologues)


# ------------------------------------------------------------
# SEARCH
# ------------------------------------------------------------
@app.route('/search', methods=['POST'])
def search():
    patient_id = request.form.get('patient_id')
    medecin_id = request.form.get('medecin_id')
    radiologue_id = request.form.get('radiologue_id')
    date_debut = request.form.get('date_debut')
    date_fin = request.form.get('date_fin')
    type_examen = request.form.get('type_examen')

    query = '''
        SELECT 
            i.id_image, i.date_image, i.type_examen, i.description,
            i.chemin_image, i.format_image, i.taille,
            p.nom AS patient_nom, p.prenom AS patient_prenom,
            m.nom AS medecin_nom, m.prenom AS medecin_prenom,
            r.nom AS radiologue_nom, r.prenom AS radiologue_prenom
        FROM ImageMedicale i
        LEFT JOIN Patient p ON i.id_patient = p.id_patient
        LEFT JOIN Medecin m ON i.id_medecin = m.id_medecin
        LEFT JOIN Radiologue r ON i.id_radiologue = r.id_radiologue
        WHERE 1=1
    '''

    params = []

    if patient_id:
        query += " AND i.id_patient = %s"
        params.append(patient_id)

    if medecin_id:
        query += " AND i.id_medecin = %s"
        params.append(medecin_id)

    if radiologue_id:
        query += " AND i.id_radiologue = %s"
        params.append(radiologue_id)

    if date_debut:
        query += " AND i.date_image >= %s"
        params.append(date_debut)

    if date_fin:
        query += " AND i.date_image <= %s"
        params.append(date_fin)

    if type_examen:
        query += " AND i.type_examen = %s"
        params.append(type_examen)

    query += " ORDER BY i.date_image DESC"

    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute(query, params)
    images = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template('results.html', images=images)


# ------------------------------------------------------------
# IMAGE DETAIL
# ------------------------------------------------------------
@app.route('/image/<int:id>')
def image_detail(id):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute('''
        SELECT 
            i.*,
            p.nom as patient_nom, p.prenom as patient_prenom,
            p.date_naissance, p.sexe,
            m.nom as medecin_nom, m.prenom as medecin_prenom, m.specialite,
            r.nom as radiologue_nom, r.prenom as radiologue_prenom
        FROM ImageMedicale i
        LEFT JOIN Patient p ON i.id_patient = p.id_patient
        LEFT JOIN Medecin m ON i.id_medecin = m.id_medecin
        LEFT JOIN Radiologue r ON i.id_radiologue = r.id_radiologue
        WHERE i.id_image = %s
    ''', (id,))

    image = cursor.fetchone()
    cursor.close()
    db.close()

    if image is None:
        flash("Image non trouvée", "error")
        return redirect(url_for("index"))

    return render_template("detail.html", image=image)


# ------------------------------------------------------------
# UPLOAD
# ------------------------------------------------------------
@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        patient_id = request.form.get('patient_id') or None
        medecin_id = request.form.get('medecin_id') or None
        radiologue_id = request.form.get('radiologue_id') or None
        type_examen = request.form.get('type_examen')
        description = request.form.get('description')

        if "image_file" not in request.files:
            flash("Aucun fichier sélectionné", "error")
            return redirect(request.url)

        file = request.files["image_file"]

        if file.filename == "":
            flash("Aucun fichier sélectionné", "error")
            return redirect(request.url)

        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"image_{timestamp}_{file.filename}"

        # Save only relative path in DB
        relative_path = f"images/{filename}"

        # Real path on disk
        filepath = os.path.join("static", "images", filename)

        file.save(filepath)

        # Insert in DB
        db = get_db()
        cursor = db.cursor()

        cursor.execute('''
            INSERT INTO ImageMedicale
            (id_patient, id_medecin, id_radiologue, date_image, 
             type_examen, description, chemin_image, format_image)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ''', (
            patient_id, medecin_id, radiologue_id,
            datetime.now().date(),
            type_examen, description,
            relative_path, file.filename.split('.')[-1]
        ))

        db.commit()
        cursor.close()
        db.close()

        flash("Image uploadée avec succès!", "success")
        return redirect(url_for("index"))

    # GET — Charger listes
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT id_patient, nom, prenom FROM Patient ORDER BY nom")
    patients = cursor.fetchall()

    cursor.execute("SELECT id_medecin, nom, prenom FROM Medecin ORDER BY nom")
    medecins = cursor.fetchall()

    cursor.execute("SELECT id_radiologue, nom, prenom FROM Radiologue ORDER BY nom")
    radiologues = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template('upload.html',
                           patients=patients,
                           medecins=medecins,
                           radiologues=radiologues)


# ------------------------------------------------------------
# RUN SERVER
# ------------------------------------------------------------
if __name__ == '__main__':
    app.run(debug=True, port=5000)
