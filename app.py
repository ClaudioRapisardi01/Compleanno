from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import json
from datetime import datetime, timedelta
import secrets
import os
import uuid

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Cambia con una chiave sicura

# Configurazione sessione permanente (non scade mai)
app.permanent_session_lifetime = timedelta(days=365)  # 1 anno

# Password del gamemaster (da cambiare!)
GAMEMASTER_PASSWORD = 'festa2025'

# Configurazione upload foto
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

# Crea cartella upload se non esiste
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Configurazione database MySQL
DB_CONFIG = {
    'host': 'localhost',
    'user': 'claudio',
    'password': 'Superrapa22',
    'database': 'birthday_game'
}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)


# Route principale - Selezione personaggio
@app.route('/')
def index():
    if 'player_id' in session:
        return redirect(url_for('dashboard'))

    # Carica personaggi disponibili
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, nome, descrizione FROM personaggi WHERE disponibile = TRUE ORDER BY nome")
    personaggi = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('index.html', personaggi=personaggi)


@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    nome = data.get('nome')
    squadra = data.get('squadra')
    personaggio_id = data.get('personaggio_id')

    if not all([nome, squadra, personaggio_id]):
        return jsonify({'success': False, 'error': 'Tutti i campi sono obbligatori'})

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Controlla se il nome è già in uso
        cursor.execute("SELECT id FROM giocatori WHERE nome = %s", (nome,))
        if cursor.fetchone():
            return jsonify({'success': False, 'error': 'Nome già in uso'})

        # Controlla se il personaggio è disponibile
        cursor.execute("SELECT nome FROM personaggi WHERE id = %s AND disponibile = TRUE", (personaggio_id,))
        personaggio = cursor.fetchone()
        if not personaggio:
            return jsonify({'success': False, 'error': 'Personaggio non disponibile'})

        # Registra il giocatore
        cursor.execute("""
            INSERT INTO giocatori (nome, squadra, personaggio_id, punti_totali)
            VALUES (%s, %s, %s, 0)
        """, (nome, squadra, personaggio_id))

        # Ottieni l'ID del giocatore appena creato
        player_id = cursor.lastrowid

        # Marca il personaggio come non disponibile
        cursor.execute("UPDATE personaggi SET disponibile = FALSE WHERE id = %s", (personaggio_id,))

        conn.commit()

        # Imposta la sessione come permanente
        session.permanent = True
        session['player_id'] = player_id
        session['player_name'] = nome
        session['team'] = squadra
        session['personaggio'] = personaggio[0]

        return jsonify({'success': True})

    except mysql.connector.Error as err:
        return jsonify({'success': False, 'error': str(err)})
    finally:
        cursor.close()
        conn.close()


@app.route('/dashboard')
def dashboard():
    if 'player_id' not in session:
        return redirect(url_for('index'))

    # Controlla lo stato del gioco corrente
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT gioco_attivo, messaggio FROM stato_gioco WHERE id = 1")
    stato = cursor.fetchone()

    # Ottieni info giocatore
    cursor.execute("""
        SELECT g.nome, g.squadra, g.punti_totali, g.foto_profilo, p.nome as personaggio
        FROM giocatori g 
        JOIN personaggi p ON g.personaggio_id = p.id 
        WHERE g.id = %s
    """, (session['player_id'],))
    player_info = cursor.fetchone()

    cursor.close()
    conn.close()

    gioco_attivo = stato[0] if stato else None
    messaggio = stato[1] if stato else "In attesa del gamemaster..."

    return render_template('dashboard.html',
                           gioco_attivo=gioco_attivo,
                           messaggio=messaggio,
                           player_info=player_info)


# API per controllo sessione
@app.route('/api/check-session')
def check_session():
    if 'player_id' in session:
        return jsonify({
            'logged_in': True,
            'player_name': session.get('player_name'),
            'team': session.get('team'),
            'personaggio': session.get('personaggio')
        })
    return jsonify({'logged_in': False})


# API per personaggi disponibili
@app.route('/api/personaggi-disponibili')
def get_personaggi_disponibili():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, nome, descrizione FROM personaggi WHERE disponibile = TRUE ORDER BY nome")
    personaggi = cursor.fetchall()
    cursor.close()
    conn.close()

    return jsonify([{
        'id': p[0],
        'nome': p[1],
        'descrizione': p[2]
    } for p in personaggi])


# API per info giocatore
@app.route('/api/player-info')
def get_player_info():
    if 'player_id' not in session:
        return jsonify({'error': 'Non autorizzato', 'redirect': True})

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT g.nome, g.squadra, g.punti_totali, g.foto_profilo, p.nome as personaggio
            FROM giocatori g 
            JOIN personaggi p ON g.personaggio_id = p.id 
            WHERE g.id = %s
        """, (session['player_id'],))
        player_info = cursor.fetchone()

        if player_info:
            return jsonify({
                'nome': player_info[0],
                'squadra': player_info[1],
                'punti_totali': player_info[2],
                'foto_profilo': player_info[3],
                'personaggio': player_info[4]
            })
        else:
            # Giocatore non trovato nel database, sessione non valida
            session.clear()
            return jsonify({'error': 'Giocatore non trovato', 'redirect': True})

    except mysql.connector.Error as err:
        return jsonify({'error': 'Errore database', 'redirect': False})
    finally:
        cursor.close()
        conn.close()


# API per classifica squadre
@app.route('/api/classifica-squadre')
def api_classifica_squadre():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT squadra, SUM(punti_totali) as punti_squadra, COUNT(*) as membri
        FROM giocatori 
        GROUP BY squadra 
        ORDER BY punti_squadra DESC
    """)
    squadre = cursor.fetchall()

    cursor.close()
    conn.close()

    return jsonify([{
        'squadra': squadra[0],
        'punti_squadra': squadra[1],
        'membri': squadra[2]
    } for squadra in squadre])


# API per classifica individuale
@app.route('/api/classifica-individuale')
def api_classifica_individuale():
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT g.nome, g.squadra, g.punti_totali, g.foto_profilo, p.nome as personaggio,
                   (SELECT COUNT(*) FROM quiz_risposte qr WHERE qr.giocatore_id = g.id AND qr.corretta = TRUE) as corrette,
                   (SELECT COUNT(*) FROM quiz_risposte qr WHERE qr.giocatore_id = g.id) as totali
            FROM giocatori g
            JOIN personaggi p ON g.personaggio_id = p.id
            ORDER BY g.punti_totali DESC, corrette DESC
        """)

        giocatori = cursor.fetchall()
        leaderboard = []

        for giocatore in giocatori:
            nome, squadra, punti, foto, personaggio, corrette, totali = giocatore
            leaderboard.append({
                'nome': nome,
                'squadra': squadra,
                'personaggio': personaggio,
                'foto_profilo': foto,
                'punti': punti,
                'risposte_corrette': corrette,
                'risposte_totali': totali,
                'percentuale': round((corrette / totali * 100) if totali > 0 else 0, 1)
            })

        return jsonify(leaderboard)

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


# Upload foto profilo
@app.route('/upload-foto', methods=['POST'])
def upload_foto():
    if 'player_id' not in session:
        return jsonify({'error': 'Non autorizzato'})

    if 'foto' not in request.files:
        return jsonify({'error': 'Nessun file selezionato'})

    file = request.files['foto']
    if file.filename == '':
        return jsonify({'error': 'Nessun file selezionato'})

    if file and allowed_file(file.filename):
        # Genera nome unico per il file
        filename = str(uuid.uuid4()) + '.' + file.filename.rsplit('.', 1)[1].lower()
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        # Salva nel database
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE giocatori SET foto_profilo = %s WHERE id = %s
        """, (filename, session['player_id']))

        cursor.execute("""
            INSERT INTO foto_profili (nome_file, nome_originale, giocatore_id)
            VALUES (%s, %s, %s)
        """, (filename, file.filename, session['player_id']))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({'success': True, 'filename': filename})

    return jsonify({'error': 'Formato file non supportato'})


# API per stato gioco (polling)
@app.route('/api/game-status')
def game_status():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT gioco_attivo, messaggio, ultimo_aggiornamento FROM stato_gioco WHERE id = 1")
    stato = cursor.fetchone()
    cursor.close()
    conn.close()

    if stato:
        return jsonify({
            'gioco_attivo': stato[0],
            'messaggio': stato[1],
            'ultimo_aggiornamento': stato[2].isoformat() if stato[2] else None
        })
    return jsonify({'gioco_attivo': None, 'messaggio': 'In attesa...'})


# API per controllo autenticazione gamemaster
@app.route('/api/gamemaster/check-auth')
def check_gamemaster_auth():
    return jsonify({'authenticated': session.get('is_gamemaster', False)})


# ROUTES GAMEMASTER
@app.route('/gamemaster')
def gamemaster():
    return render_template('gamemaster_login.html')


@app.route('/gamemaster/login', methods=['POST'])
def gamemaster_login():
    data = request.get_json()
    password = data.get('password')

    if password == GAMEMASTER_PASSWORD:
        session.permanent = True
        session['is_gamemaster'] = True
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'error': 'Password errata'})


@app.route('/gamemaster/panel')
def gamemaster_panel():
    if not session.get('is_gamemaster'):
        return redirect(url_for('gamemaster'))

    return render_template('gamemaster_panel.html')


# API Gamemaster - Ottieni tutti i giocatori
@app.route('/api/gamemaster/players')
def get_all_players():
    if not session.get('is_gamemaster'):
        return jsonify({'error': 'Non autorizzato'}), 403

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT g.id, g.nome, g.squadra, g.punti_totali, g.foto_profilo, 
                   p.nome as personaggio, g.escluso_da_gioco, g.ultima_attivita
            FROM giocatori g
            JOIN personaggi p ON g.personaggio_id = p.id
            ORDER BY g.punti_totali DESC
        """)
        players = cursor.fetchall()

        players_list = []
        for player in players:
            players_list.append({
                'id': player[0],
                'nome': player[1],
                'squadra': player[2],
                'punti_totali': player[3],
                'foto_profilo': player[4],
                'personaggio': player[5],
                'escluso_da_gioco': bool(player[6]),
                'ultima_attivita': player[7].isoformat() if player[7] else None
            })

        return jsonify(players_list)

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


# API Gamemaster - Gestione stato gioco
@app.route('/api/gamemaster/game-state', methods=['POST'])
def update_game_state():
    if not session.get('is_gamemaster'):
        return jsonify({'error': 'Non autorizzato'}), 403

    data = request.get_json()
    gioco_attivo = data.get('gioco_attivo')
    messaggio = data.get('messaggio', '')

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO stato_gioco (id, gioco_attivo, messaggio, ultimo_aggiornamento) 
            VALUES (1, %s, %s, NOW()) 
            ON DUPLICATE KEY UPDATE 
            gioco_attivo = %s, messaggio = %s, ultimo_aggiornamento = NOW()
        """, (gioco_attivo, messaggio, gioco_attivo, messaggio))

        conn.commit()
        return jsonify({'success': True})

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


# API Gamemaster - Gestione giocatori avanzata
@app.route('/api/gamemaster/players/<int:player_id>/toggle-status', methods=['POST'])
def toggle_player_status(player_id):
    if not session.get('is_gamemaster'):
        return jsonify({'error': 'Non autorizzato'}), 403

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Ottieni stato attuale
        cursor.execute("SELECT escluso_da_gioco FROM giocatori WHERE id = %s", (player_id,))
        result = cursor.fetchone()

        if not result:
            return jsonify({'error': 'Giocatore non trovato'}), 404

        # Inverti lo stato
        nuovo_stato = not bool(result[0])

        cursor.execute("""
            UPDATE giocatori 
            SET escluso_da_gioco = %s 
            WHERE id = %s
        """, (nuovo_stato, player_id))

        conn.commit()
        return jsonify({'success': True, 'nuovo_stato': nuovo_stato})

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/api/gamemaster/reset-scores', methods=['POST'])
def reset_all_scores():
    if not session.get('is_gamemaster'):
        return jsonify({'error': 'Non autorizzato'}), 403

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Reset punteggi
        cursor.execute("UPDATE giocatori SET punti_totali = 0")

        # Opzionalmente, cancella anche le risposte del quiz e partite
        cursor.execute("DELETE FROM quiz_risposte")
        cursor.execute("DELETE FROM indovina_partite")
        cursor.execute("DELETE FROM indovina_risposte")
        cursor.execute("DELETE FROM votazione_costumi")
        cursor.execute("DELETE FROM partecipazioni")

        conn.commit()
        return jsonify({'success': True})

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


# API Gamemaster - Gestione domande quiz
@app.route('/api/gamemaster/quiz-questions')
def get_quiz_questions():
    if not session.get('is_gamemaster'):
        return jsonify({'error': 'Non autorizzato'}), 403

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT id, domanda, opzione_a, opzione_b, opzione_c, opzione_d, 
                   risposta_corretta, categoria, created_at
            FROM quiz_domande 
            ORDER BY created_at DESC
        """)
        questions = cursor.fetchall()

        questions_list = []
        for q in questions:
            questions_list.append({
                'id': q[0],
                'domanda': q[1],
                'opzione_a': q[2],
                'opzione_b': q[3],
                'opzione_c': q[4],
                'opzione_d': q[5],
                'risposta_corretta': q[6],
                'categoria': q[7],
                'created_at': q[8].isoformat() if q[8] else None
            })

        return jsonify(questions_list)

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/api/gamemaster/quiz-questions', methods=['POST'])
def add_quiz_question():
    if not session.get('is_gamemaster'):
        return jsonify({'error': 'Non autorizzato'}), 403

    data = request.get_json()
    domanda = data.get('domanda', '').strip()
    opzione_a = data.get('opzione_a', '').strip()
    opzione_b = data.get('opzione_b', '').strip()
    opzione_c = data.get('opzione_c', '').strip()
    opzione_d = data.get('opzione_d', '').strip()
    risposta_corretta = data.get('risposta_corretta', '').lower()
    categoria = data.get('categoria', 'generale').strip()

    # Validazione
    if not all([domanda, opzione_a, opzione_b, opzione_c, opzione_d, risposta_corretta]):
        return jsonify({'error': 'Tutti i campi sono obbligatori'})

    if risposta_corretta not in ['a', 'b', 'c', 'd']:
        return jsonify({'error': 'Risposta corretta deve essere a, b, c o d'})

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO quiz_domande (domanda, opzione_a, opzione_b, opzione_c, opzione_d, risposta_corretta, categoria)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (domanda, opzione_a, opzione_b, opzione_c, opzione_d, risposta_corretta, categoria))

        conn.commit()
        return jsonify({'success': True})

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/api/gamemaster/quiz-questions/<int:question_id>', methods=['PUT'])
def update_quiz_question(question_id):
    if not session.get('is_gamemaster'):
        return jsonify({'error': 'Non autorizzato'}), 403

    data = request.get_json()
    domanda = data.get('domanda', '').strip()
    opzione_a = data.get('opzione_a', '').strip()
    opzione_b = data.get('opzione_b', '').strip()
    opzione_c = data.get('opzione_c', '').strip()
    opzione_d = data.get('opzione_d', '').strip()
    risposta_corretta = data.get('risposta_corretta', '').lower()
    categoria = data.get('categoria', 'generale').strip()

    # Validazione
    if not all([domanda, opzione_a, opzione_b, opzione_c, opzione_d, risposta_corretta]):
        return jsonify({'error': 'Tutti i campi sono obbligatori'})

    if risposta_corretta not in ['a', 'b', 'c', 'd']:
        return jsonify({'error': 'Risposta corretta deve essere a, b, c o d'})

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            UPDATE quiz_domande 
            SET domanda = %s, opzione_a = %s, opzione_b = %s, opzione_c = %s, 
                opzione_d = %s, risposta_corretta = %s, categoria = %s
            WHERE id = %s
        """, (domanda, opzione_a, opzione_b, opzione_c, opzione_d, risposta_corretta, categoria, question_id))

        conn.commit()
        return jsonify({'success': True})

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/api/gamemaster/quiz-questions/<int:question_id>', methods=['DELETE'])
def delete_quiz_question(question_id):
    if not session.get('is_gamemaster'):
        return jsonify({'error': 'Non autorizzato'}), 403

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("DELETE FROM quiz_domande WHERE id = %s", (question_id,))
        conn.commit()
        return jsonify({'success': True})

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


# API Gamemaster - Gestione Indovina Chi
@app.route('/api/gamemaster/indovina-people')
def get_indovina_people():
    if not session.get('is_gamemaster'):
        return jsonify({'error': 'Non autorizzato'}), 403

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT id, nome, descrizione, foto_filename, attivo, created_at
            FROM indovina_persone 
            ORDER BY nome ASC
        """)
        people = cursor.fetchall()

        people_list = []
        for p in people:
            people_list.append({
                'id': p[0],
                'nome': p[1],
                'descrizione': p[2],
                'foto_filename': p[3],
                'attivo': bool(p[4]),
                'created_at': p[5].isoformat() if p[5] else None
            })

        return jsonify(people_list)

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/api/gamemaster/indovina-people', methods=['POST'])
def add_indovina_person():
    if not session.get('is_gamemaster'):
        return jsonify({'error': 'Non autorizzato'}), 403

    data = request.get_json()
    nome = data.get('nome', '').strip()
    descrizione = data.get('descrizione', '').strip()

    if not nome:
        return jsonify({'error': 'Nome obbligatorio'})

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO indovina_persone (nome, descrizione, attivo)
            VALUES (%s, %s, TRUE)
        """, (nome, descrizione))

        conn.commit()
        return jsonify({'success': True, 'id': cursor.lastrowid})

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/api/gamemaster/indovina-indizi/<int:persona_id>')
def get_indizi_by_person(persona_id):
    if not session.get('is_gamemaster'):
        return jsonify({'error': 'Non autorizzato'}), 403

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT id, indizio, ordine, punti
            FROM indovina_indizi 
            WHERE persona_id = %s
            ORDER BY ordine ASC
        """, (persona_id,))
        indizi = cursor.fetchall()

        indizi_list = []
        for i in indizi:
            indizi_list.append({
                'id': i[0],
                'indizio': i[1],
                'ordine': i[2],
                'punti': i[3]
            })

        return jsonify(indizi_list)

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/api/gamemaster/indovina-indizi', methods=['POST'])
def add_indizio():
    if not session.get('is_gamemaster'):
        return jsonify({'error': 'Non autorizzato'}), 403

    data = request.get_json()
    persona_id = data.get('persona_id')
    indizio = data.get('indizio', '').strip()
    ordine = data.get('ordine', 1)
    punti = data.get('punti', 50)

    if not all([persona_id, indizio]):
        return jsonify({'error': 'Persona e indizio obbligatori'})

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO indovina_indizi (persona_id, indizio, ordine, punti)
            VALUES (%s, %s, %s, %s)
        """, (persona_id, indizio, ordine, punti))

        conn.commit()
        return jsonify({'success': True})

    except mysql.connector.IntegrityError:
        return jsonify({'error': 'Ordine già esistente per questa persona'})
    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/api/gamemaster/indovina-indizi/<int:indizio_id>', methods=['PUT'])
def update_indizio(indizio_id):
    if not session.get('is_gamemaster'):
        return jsonify({'error': 'Non autorizzato'}), 403

    data = request.get_json()
    indizio = data.get('indizio', '').strip()
    ordine = data.get('ordine', 1)
    punti = data.get('punti', 0)

    if not indizio:
        return jsonify({'error': 'Indizio obbligatorio'})

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            UPDATE indovina_indizi 
            SET indizio = %s, ordine = %s, punti = %s
            WHERE id = %s
        """, (indizio, ordine, punti, indizio_id))

        conn.commit()
        return jsonify({'success': True})

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/api/gamemaster/indovina-indizi/<int:indizio_id>', methods=['DELETE'])
def delete_indizio(indizio_id):
    if not session.get('is_gamemaster'):
        return jsonify({'error': 'Non autorizzato'}), 403

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("DELETE FROM indovina_indizi WHERE id = %s", (indizio_id,))
        conn.commit()
        return jsonify({'success': True})

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/upload-foto-indovina', methods=['POST'])
def upload_foto_indovina():
    """Upload foto per una persona di Indovina Chi"""
    if not session.get('is_gamemaster'):
        return jsonify({'error': 'Non autorizzato'})

    if 'foto' not in request.files:
        return jsonify({'error': 'Nessun file selezionato'})

    file = request.files['foto']
    persona_id = request.form.get('persona_id')

    if file.filename == '' or not persona_id:
        return jsonify({'error': 'File e persona_id obbligatori'})

    if file and allowed_file(file.filename):
        # Genera nome unico per il file
        filename = f"indovina_{persona_id}_{str(uuid.uuid4())}.{file.filename.rsplit('.', 1)[1].lower()}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        # Aggiorna il database
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE indovina_persone SET foto_filename = %s WHERE id = %s
        """, (filename, persona_id))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({'success': True, 'filename': filename})

    return jsonify({'error': 'Formato file non supportato'})


# Quiz Personalizzato
@app.route('/quiz-personalizzato')
def quiz_personalizzato():
    if 'player_id' not in session:
        return redirect(url_for('index'))
    return render_template('quiz_personalizzato.html')


# Indovina Chi
@app.route('/indovina-chi')
def indovina_chi():
    if 'player_id' not in session:
        return redirect(url_for('index'))
    return render_template('indovina_chi.html')


# Votazione Costumi
@app.route('/votazione-costumi')
def votazione_costumi():
    if 'player_id' not in session:
        return redirect(url_for('index'))
    return render_template('votazione_costumi.html')


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)