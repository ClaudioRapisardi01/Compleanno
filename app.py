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


# Aggiungi queste route al tuo app.py (inserisci prima della riga "if __name__ == '__main__':")

# API per reset quiz (solo gamemaster)
@app.route('/api/gamemaster/reset-quiz-responses', methods=['POST'])
def reset_quiz_responses():
    if not session.get('is_gamemaster'):
        return jsonify({'error': 'Non autorizzato'}), 403

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("DELETE FROM quiz_risposte")
        conn.commit()
        return jsonify({'success': True, 'message': 'Tutte le risposte quiz sono state resettate'})

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


# API per ottenere domande quiz (per i giocatori)
@app.route('/api/quiz-questions')
def get_quiz_questions_for_players():
    if 'player_id' not in session:
        return jsonify({'error': 'Non autorizzato'}), 403

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Prendi tutte le domande in ordine casuale
        cursor.execute("""
            SELECT id, domanda, opzione_a, opzione_b, opzione_c, opzione_d, categoria
            FROM quiz_domande 
            ORDER BY RAND()
        """)
        questions = cursor.fetchall()

        questions_list = []
        for q in questions:
            questions_list.append({
                'id': q[0],
                'domanda': q[1],
                'opzioni': [q[2], q[3], q[4], q[5]],  # Array delle opzioni
                'categoria': q[6]
            })

        return jsonify(questions_list)

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


# API per inviare risposte quiz
# Sostituisci la funzione submit_quiz in app.py con questa versione corretta:

@app.route('/api/submit-quiz', methods=['POST'])
def submit_quiz():
    if 'player_id' not in session:
        return jsonify({'error': 'Non autorizzato'}), 403

    data = request.get_json()
    risposte = data.get('risposte', {})  # Dict: {domanda_id: risposta_data}
    tempo_totale = data.get('tempo_totale', 0)

    if not risposte:
        return jsonify({'error': 'Nessuna risposta fornita'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        punteggio_totale = 0
        risposte_corrette = 0
        dettagli_risposte = []

        # Processa ogni risposta
        for domanda_id, risposta_data in risposte.items():
            # Skip se è un campo tempo
            if str(domanda_id).startswith('tempo_'):
                continue

            # Ottieni la risposta corretta
            cursor.execute("""
                SELECT risposta_corretta, categoria, domanda
                FROM quiz_domande 
                WHERE id = %s
            """, (domanda_id,))

            question = cursor.fetchone()
            if not question:
                continue

            risposta_corretta_db, categoria, domanda_text = question
            is_correct = risposta_data.lower() == risposta_corretta_db.lower()

            # Ottieni il tempo di risposta per questa domanda
            tempo_key = f'tempo_{domanda_id}'
            tempo_risposta = data.get(tempo_key, 30)  # Default 30 secondi se non specificato

            if is_correct:
                risposte_corrette += 1
                punti_domanda = 10  # Punti base per risposta corretta

                # Bonus per velocità
                if tempo_risposta <= 10:
                    punti_domanda += 5  # Bonus velocità
                elif tempo_risposta <= 20:
                    punti_domanda += 2

                punteggio_totale += punti_domanda
            else:
                punti_domanda = 0

            # Salva la risposta nel database
            cursor.execute("""
                INSERT INTO quiz_risposte (giocatore_id, domanda_id, risposta_data, corretta, tempo_risposta)
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE 
                risposta_data = %s, corretta = %s, tempo_risposta = %s
            """, (
                session['player_id'], domanda_id, risposta_data, is_correct, tempo_risposta,
                risposta_data, is_correct, tempo_risposta
            ))

            dettagli_risposte.append({
                'domanda': domanda_text,
                'categoria': categoria,
                'risposta_data': risposta_data,
                'risposta_corretta': risposta_corretta_db,
                'corretta': is_correct,
                'punti': punti_domanda,
                'tempo': tempo_risposta
            })

        # Aggiorna punteggio totale giocatore
        cursor.execute("""
            UPDATE giocatori 
            SET punti_totali = punti_totali + %s 
            WHERE id = %s
        """, (punteggio_totale, session['player_id']))

        # Registra partecipazione
        cursor.execute("""
            INSERT INTO partecipazioni (giocatore_id, gioco, punti)
            VALUES (%s, 'quiz_personalizzato', %s)
        """, (session['player_id'], punteggio_totale))

        conn.commit()

        return jsonify({
            'success': True,
            'punteggio_totale': punteggio_totale,
            'risposte_corrette': risposte_corrette,
            'totale_domande': len(dettagli_risposte),
            'tempo_totale': tempo_totale,
            'dettagli': dettagli_risposte
        })

    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({'error': str(err)}), 500
    except Exception as e:
        conn.rollback()
        return jsonify({'error': f'Errore generico: {str(e)}'}), 500
    finally:
        cursor.close()
        conn.close()


# API per verificare se il giocatore ha già fatto il quiz
@app.route('/api/quiz-status')
def quiz_status():
    if 'player_id' not in session:
        return jsonify({'error': 'Non autorizzato'}), 403

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Controlla se ha già fatto il quiz
        cursor.execute("""
            SELECT COUNT(*) as risposte_date, 
                   SUM(CASE WHEN corretta = TRUE THEN 1 ELSE 0 END) as corrette,
                   MAX(timestamp) as ultimo_tentativo
            FROM quiz_risposte 
            WHERE giocatore_id = %s
        """, (session['player_id'],))

        result = cursor.fetchone()
        risposte_date = result[0] if result else 0
        risposte_corrette = result[1] if result else 0
        ultimo_tentativo = result[2] if result else None

        # Conta domande totali disponibili
        cursor.execute("SELECT COUNT(*) FROM quiz_domande")
        totale_domande = cursor.fetchone()[0]

        return jsonify({
            'ha_completato': risposte_date >= totale_domande,
            'risposte_date': risposte_date,
            'risposte_corrette': risposte_corrette,
            'totale_domande': totale_domande,
            'ultimo_tentativo': ultimo_tentativo.isoformat() if ultimo_tentativo else None,
            'puo_rifare': True  # Permettiamo sempre di rifare il quiz
        })

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


# Indovina Chi
@app.route('/indovina-chi')
def indovina_chi():
    if 'player_id' not in session:
        return redirect(url_for('index'))
    return render_template('indovina_chi.html')


# Aggiungi queste route al tuo app.py, prima della riga "if __name__ == '__main__':"

# ==================== API INDOVINA CHI ====================

# API per ottenere una persona casuale da indovinare (evitando quelle già giocate)
@app.route('/api/indovina-chi/start-game', methods=['POST'])
def start_indovina_chi_game():
    if 'player_id' not in session:
        return jsonify({'error': 'Non autorizzato'}), 403

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Controlla se il giocatore ha già una partita attiva
        cursor.execute("""
            SELECT id, persona_id FROM indovina_partite 
            WHERE giocatore_id = %s AND completata = FALSE
            ORDER BY timestamp DESC LIMIT 1
        """, (session['player_id'],))

        partita_attiva = cursor.fetchone()

        if partita_attiva:
            # Ritorna la partita esistente
            partita_id, persona_id = partita_attiva

            # Ottieni info persona
            cursor.execute("""
                SELECT nome, descrizione FROM indovina_persone WHERE id = %s
            """, (persona_id,))
            persona = cursor.fetchone()

            return jsonify({
                'success': True,
                'partita_id': partita_id,
                'persona_id': persona_id,
                'persona_nome': persona[0] if persona else 'Sconosciuta',
                'persona_descrizione': persona[1] if persona else '',
                'nuova_partita': False
            })

        # Ottieni persone che il giocatore NON ha mai giocato
        cursor.execute("""
            SELECT ip.id, ip.nome, ip.descrizione FROM indovina_persone ip
            WHERE ip.attivo = TRUE 
            AND ip.id NOT IN (
                SELECT DISTINCT persona_id 
                FROM indovina_partite 
                WHERE giocatore_id = %s AND completata = TRUE
            )
            ORDER BY RAND() LIMIT 1
        """, (session['player_id'],))

        persona = cursor.fetchone()

        if not persona:
            # Il giocatore ha completato tutte le persone disponibili
            return jsonify({
                'game_completed': True,
                'error': 'Complimenti! Hai completato tutte le persone disponibili!'
            })

        persona_id, nome, descrizione = persona

        # Conta persone totali e quelle già completate
        cursor.execute("""
            SELECT COUNT(*) FROM indovina_persone WHERE attivo = TRUE
        """)
        persone_totali = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(DISTINCT persona_id) 
            FROM indovina_partite 
            WHERE giocatore_id = %s AND completata = TRUE
        """, (session['player_id'],))
        persone_completate = cursor.fetchone()[0]

        # Crea nuova partita
        cursor.execute("""
            INSERT INTO indovina_partite (giocatore_id, persona_id, indizi_richiesti, punti_guadagnati, completata)
            VALUES (%s, %s, 0, 0, FALSE)
        """, (session['player_id'], persona_id))

        partita_id = cursor.lastrowid
        conn.commit()

        return jsonify({
            'success': True,
            'partita_id': partita_id,
            'persona_id': persona_id,
            'persona_nome': nome,
            'persona_descrizione': descrizione,
            'nuova_partita': True,
            'progresso': {
                'completate': persone_completate,
                'totali': persone_totali,
                'rimanenti': persone_totali - persone_completate
            }
        })

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


# API per richiedere un indizio
@app.route('/api/indovina-chi/get-clue', methods=['POST'])
def get_indovina_chi_clue():
    if 'player_id' not in session:
        return jsonify({'error': 'Non autorizzato'}), 403

    data = request.get_json()
    partita_id = data.get('partita_id')

    if not partita_id:
        return jsonify({'error': 'ID partita mancante'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Verifica che la partita appartenga al giocatore
        cursor.execute("""
            SELECT persona_id, indizi_richiesti, completata 
            FROM indovina_partite 
            WHERE id = %s AND giocatore_id = %s
        """, (partita_id, session['player_id']))

        partita = cursor.fetchone()
        if not partita:
            return jsonify({'error': 'Partita non trovata'}), 404

        persona_id, indizi_richiesti, completata = partita

        if completata:
            return jsonify({'error': 'Partita già completata'}), 400

        # Calcola il prossimo indizio
        prossimo_indizio_numero = indizi_richiesti + 1

        # Ottieni l'indizio
        cursor.execute("""
            SELECT indizio, punti FROM indovina_indizi 
            WHERE persona_id = %s AND ordine = %s
        """, (persona_id, prossimo_indizio_numero))

        indizio_data = cursor.fetchone()
        if not indizio_data:
            return jsonify({'error': 'Nessun indizio disponibile per questo numero'})

        indizio_testo, punti = indizio_data

        # Registra la richiesta dell'indizio
        cursor.execute("""
            INSERT INTO indovina_risposte (partita_id, giocatore_id, indizio_numero)
            VALUES (%s, %s, %s)
        """, (partita_id, session['player_id'], prossimo_indizio_numero))

        # Aggiorna il numero di indizi richiesti
        cursor.execute("""
            UPDATE indovina_partite 
            SET indizi_richiesti = %s 
            WHERE id = %s
        """, (prossimo_indizio_numero, partita_id))

        # Conta il totale degli indizi disponibili
        cursor.execute("""
            SELECT COUNT(*) FROM indovina_indizi WHERE persona_id = %s
        """, (persona_id,))
        totale_indizi = cursor.fetchone()[0]

        conn.commit()

        return jsonify({
            'success': True,
            'indizio': indizio_testo,
            'indizio_numero': prossimo_indizio_numero,
            'punti_possibili': punti,
            'indizi_richiesti': prossimo_indizio_numero,
            'totale_indizi': totale_indizi,
            'tutti_indizi_usati': prossimo_indizio_numero >= totale_indizi
        })

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


# API per inviare una risposta
@app.route('/api/indovina-chi/submit-answer', methods=['POST'])
def submit_indovina_chi_answer():
    if 'player_id' not in session:
        return jsonify({'error': 'Non autorizzato'}), 403

    data = request.get_json()
    partita_id = data.get('partita_id')
    risposta = data.get('risposta', '').strip()
    tempo_impiegato = data.get('tempo_impiegato', 0)

    if not all([partita_id, risposta]):
        return jsonify({'error': 'Dati mancanti'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Ottieni info partita
        cursor.execute("""
            SELECT ip.persona_id, ip.indizi_richiesti, ip.completata, p.nome
            FROM indovina_partite ip
            JOIN indovina_persone p ON ip.persona_id = p.id
            WHERE ip.id = %s AND ip.giocatore_id = %s
        """, (partita_id, session['player_id']))

        partita_info = cursor.fetchone()
        if not partita_info:
            return jsonify({'error': 'Partita non trovata'}), 404

        persona_id, indizi_richiesti, completata, nome_corretto = partita_info

        if completata:
            return jsonify({'error': 'Partita già completata'}), 400

        # Verifica se la risposta è corretta (case-insensitive)
        risposta_corretta = risposta.lower().strip() == nome_corretto.lower().strip()

        # Calcola punteggio
        punti_guadagnati = 0
        if risposta_corretta:
            # Punteggio basato sugli indizi usati
            if indizi_richiesti == 1:
                punti_guadagnati = 100  # Indovinato al primo indizio
            elif indizi_richiesti == 2:
                punti_guadagnati = 80  # Secondo indizio
            elif indizi_richiesti == 3:
                punti_guadagnati = 60  # Terzo indizio
            elif indizi_richiesti == 4:
                punti_guadagnati = 40  # Quarto indizio
            else:
                punti_guadagnati = 20  # Più di 4 indizi

            # Bonus per velocità (se completato in meno di 2 minuti)
            if tempo_impiegato > 0 and tempo_impiegato < 120:
                punti_guadagnati += 10

        # Aggiorna la partita
        cursor.execute("""
            UPDATE indovina_partite 
            SET risposta_corretta = %s, punti_guadagnati = %s, 
                tempo_impiegato = %s, completata = TRUE
            WHERE id = %s
        """, (risposta_corretta, punti_guadagnati, tempo_impiegato, partita_id))

        # Se la risposta è corretta, aggiorna i punti del giocatore
        if risposta_corretta:
            cursor.execute("""
                UPDATE giocatori 
                SET punti_totali = punti_totali + %s 
                WHERE id = %s
            """, (punti_guadagnati, session['player_id']))

            # Registra partecipazione
            cursor.execute("""
                INSERT INTO partecipazioni (giocatore_id, gioco, punti)
                VALUES (%s, 'indovina_chi', %s)
            """, (session['player_id'], punti_guadagnati))

        conn.commit()

        return jsonify({
            'success': True,
            'corretta': risposta_corretta,
            'nome_corretto': nome_corretto,
            'punti_guadagnati': punti_guadagnati,
            'indizi_usati': indizi_richiesti,
            'tempo_impiegato': tempo_impiegato,
            'messaggio': 'Corretto! Ottimo lavoro!' if risposta_corretta else f'Sbagliato! La risposta corretta era: {nome_corretto}'
        })

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


# API per ottenere lo stato di una partita
@app.route('/api/indovina-chi/game-status')
def get_indovina_chi_game_status():
    if 'player_id' not in session:
        return jsonify({'error': 'Non autorizzato'}), 403

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Controlla se ha completato tutte le persone
        cursor.execute("""
            SELECT COUNT(*) FROM indovina_persone WHERE attivo = TRUE
        """)
        persone_totali = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(DISTINCT persona_id) 
            FROM indovina_partite 
            WHERE giocatore_id = %s AND completata = TRUE
        """, (session['player_id'],))
        persone_completate = cursor.fetchone()[0]

        # Se ha completato tutto
        if persone_completate >= persone_totali and persone_totali > 0:
            return jsonify({
                'game_fully_completed': True,
                'has_active_game': False,
                'can_start_new': False,
                'progresso': {
                    'completate': persone_completate,
                    'totali': persone_totali,
                    'rimanenti': 0
                },
                'messaggio_finale': f'🎉 Complimenti! Hai completato tutte le {persone_totali} persone disponibili!'
            })

        # Ottieni l'ultima partita del giocatore
        cursor.execute("""
            SELECT ip.id, ip.persona_id, ip.indizi_richiesti, ip.punti_guadagnati, 
                   ip.risposta_corretta, ip.completata, ip.tempo_impiegato,
                   p.nome, p.descrizione
            FROM indovina_partite ip
            JOIN indovina_persone p ON ip.persona_id = p.id
            WHERE ip.giocatore_id = %s
            ORDER BY ip.timestamp DESC LIMIT 1
        """, (session['player_id'],))

        partita = cursor.fetchone()

        if not partita:
            return jsonify({
                'has_active_game': False,
                'can_start_new': True,
                'progresso': {
                    'completate': persone_completate,
                    'totali': persone_totali,
                    'rimanenti': persone_totali - persone_completate
                }
            })

        partita_id, persona_id, indizi_richiesti, punti_guadagnati, risposta_corretta, completata, tempo_impiegato, nome, descrizione = partita

        # Se la partita è completata, può iniziarne una nuova (se ce ne sono ancora)
        if completata:
            persone_rimanenti = persone_totali - persone_completate
            return jsonify({
                'has_active_game': False,
                'can_start_new': persone_rimanenti > 0,
                'progresso': {
                    'completate': persone_completate,
                    'totali': persone_totali,
                    'rimanenti': persone_rimanenti
                },
                'last_game': {
                    'persona_nome': nome,
                    'corretta': bool(risposta_corretta),
                    'punti': punti_guadagnati,
                    'indizi_usati': indizi_richiesti
                }
            })

        # Ottieni gli indizi già richiesti
        cursor.execute("""
            SELECT ii.indizio, ii.ordine, ii.punti
            FROM indovina_indizi ii
            JOIN indovina_risposte ir ON ir.indizio_numero = ii.ordine
            WHERE ir.partita_id = %s AND ii.persona_id = %s
            ORDER BY ii.ordine ASC
        """, (partita_id, persona_id))

        indizi_ottenuti = []
        for indizio_data in cursor.fetchall():
            indizi_ottenuti.append({
                'testo': indizio_data[0],
                'numero': indizio_data[1],
                'punti': indizio_data[2]
            })

        # Conta totale indizi disponibili
        cursor.execute("""
            SELECT COUNT(*) FROM indovina_indizi WHERE persona_id = %s
        """, (persona_id,))
        totale_indizi = cursor.fetchone()[0]

        return jsonify({
            'has_active_game': True,
            'can_start_new': False,
            'partita_id': partita_id,
            'persona_id': persona_id,
            'persona_nome': nome,
            'persona_descrizione': descrizione,
            'indizi_richiesti': indizi_richiesti,
            'indizi_ottenuti': indizi_ottenuti,
            'totale_indizi': totale_indizi,
            'tutti_indizi_usati': indizi_richiesti >= totale_indizi,
            'progresso': {
                'completate': persone_completate,
                'totali': persone_totali,
                'rimanenti': persone_totali - persone_completate
            }
        })

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


# API per ottenere le statistiche del giocatore
@app.route('/api/indovina-chi/stats')
def get_indovina_chi_stats():
    if 'player_id' not in session:
        return jsonify({'error': 'Non autorizzato'}), 403

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Statistiche generali
        cursor.execute("""
            SELECT 
                COUNT(*) as partite_totali,
                SUM(CASE WHEN risposta_corretta = TRUE THEN 1 ELSE 0 END) as partite_vinte,
                SUM(punti_guadagnati) as punti_totali,
                AVG(CASE WHEN completata = TRUE THEN indizi_richiesti END) as media_indizi,
                AVG(CASE WHEN completata = TRUE THEN tempo_impiegato END) as tempo_medio
            FROM indovina_partite 
            WHERE giocatore_id = %s AND completata = TRUE
        """, (session['player_id'],))

        stats = cursor.fetchone()

        # Conta persone totali e completate
        cursor.execute("""
            SELECT COUNT(*) FROM indovina_persone WHERE attivo = TRUE
        """)
        persone_totali = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(DISTINCT persona_id) 
            FROM indovina_partite 
            WHERE giocatore_id = %s AND completata = TRUE
        """, (session['player_id'],))
        persone_completate = cursor.fetchone()[0]

        if not stats or stats[0] == 0:
            return jsonify({
                'partite_totali': 0,
                'partite_vinte': 0,
                'punti_totali': 0,
                'percentuale_vittoria': 0,
                'media_indizi': 0,
                'tempo_medio': 0,
                'miglior_partita': None,
                'progresso': {
                    'persone_completate': persone_completate,
                    'persone_totali': persone_totali,
                    'percentuale_completamento': round(
                        (persone_completate / persone_totali * 100) if persone_totali > 0 else 0, 1),
                    'gioco_completato': persone_completate >= persone_totali and persone_totali > 0
                }
            })

        partite_totali, partite_vinte, punti_totali, media_indizi, tempo_medio = stats
        percentuale_vittoria = (partite_vinte / partite_totali * 100) if partite_totali > 0 else 0

        # Miglior partita
        cursor.execute("""
            SELECT ip.punti_guadagnati, ip.indizi_richiesti, ip.tempo_impiegato, p.nome
            FROM indovina_partite ip
            JOIN indovina_persone p ON ip.persona_id = p.id
            WHERE ip.giocatore_id = %s AND ip.risposta_corretta = TRUE
            ORDER BY ip.punti_guadagnati DESC, ip.indizi_richiesti ASC
            LIMIT 1
        """, (session['player_id'],))

        miglior_partita = cursor.fetchone()

        # Lista persone ancora da completare
        cursor.execute("""
            SELECT p.nome FROM indovina_persone p
            WHERE p.attivo = TRUE 
            AND p.id NOT IN (
                SELECT DISTINCT persona_id 
                FROM indovina_partite 
                WHERE giocatore_id = %s AND completata = TRUE
            )
            ORDER BY p.nome
        """, (session['player_id'],))

        persone_rimanenti = [row[0] for row in cursor.fetchall()]

        return jsonify({
            'partite_totali': partite_totali,
            'partite_vinte': partite_vinte,
            'punti_totali': punti_totali or 0,
            'percentuale_vittoria': round(percentuale_vittoria, 1),
            'media_indizi': round(media_indizi or 0, 1),
            'tempo_medio': round(tempo_medio or 0, 1),
            'miglior_partita': {
                'punti': miglior_partita[0],
                'indizi': miglior_partita[1],
                'tempo': miglior_partita[2],
                'persona': miglior_partita[3]
            } if miglior_partita else None,
            'progresso': {
                'persone_completate': persone_completate,
                'persone_totali': persone_totali,
                'percentuale_completamento': round(
                    (persone_completate / persone_totali * 100) if persone_totali > 0 else 0, 1),
                'gioco_completato': persone_completate >= persone_totali and persone_totali > 0,
                'persone_rimanenti': persone_rimanenti
            }
        })

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


# API per rinunciare a una partita
@app.route('/api/indovina-chi/give-up', methods=['POST'])
def give_up_indovina_chi():
    if 'player_id' not in session:
        return jsonify({'error': 'Non autorizzato'}), 403

    data = request.get_json()
    partita_id = data.get('partita_id')

    if not partita_id:
        return jsonify({'error': 'ID partita mancante'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Verifica che la partita appartenga al giocatore e non sia completata
        cursor.execute("""
            SELECT ip.persona_id, p.nome
            FROM indovina_partite ip
            JOIN indovina_persone p ON ip.persona_id = p.id
            WHERE ip.id = %s AND ip.giocatore_id = %s AND ip.completata = FALSE
        """, (partita_id, session['player_id']))

        partita_info = cursor.fetchone()
        if not partita_info:
            return jsonify({'error': 'Partita non trovata o già completata'}), 404

        persona_id, nome_corretto = partita_info

        # Segna la partita come completata senza punti
        cursor.execute("""
            UPDATE indovina_partite 
            SET risposta_corretta = FALSE, punti_guadagnati = 0, completata = TRUE
            WHERE id = %s
        """, (partita_id,))

        conn.commit()

        return jsonify({
            'success': True,
            'nome_corretto': nome_corretto,
            'messaggio': f'Hai rinunciato. La risposta corretta era: {nome_corretto}'
        })

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


# API per ottenere la classifica Indovina Chi
@app.route('/api/indovina-chi/leaderboard')
def get_indovina_chi_leaderboard():
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT 
                g.nome, g.squadra, g.foto_profilo,
                COUNT(ip.id) as partite_giocate,
                SUM(CASE WHEN ip.risposta_corretta = TRUE THEN 1 ELSE 0 END) as partite_vinte,
                SUM(ip.punti_guadagnati) as punti_totali,
                AVG(CASE WHEN ip.completata = TRUE AND ip.risposta_corretta = TRUE THEN ip.indizi_richiesti END) as media_indizi_vincenti
            FROM giocatori g
            LEFT JOIN indovina_partite ip ON g.id = ip.giocatore_id AND ip.completata = TRUE
            GROUP BY g.id, g.nome, g.squadra, g.foto_profilo
            HAVING partite_giocate > 0
            ORDER BY punti_totali DESC, partite_vinte DESC, media_indizi_vincenti ASC
        """, )

        leaderboard = []
        for row in cursor.fetchall():
            nome, squadra, foto, partite_giocate, partite_vinte, punti_totali, media_indizi = row

            percentuale_vittoria = (partite_vinte / partite_giocate * 100) if partite_giocate > 0 else 0

            leaderboard.append({
                'nome': nome,
                'squadra': squadra,
                'foto_profilo': foto,
                'partite_giocate': partite_giocate,
                'partite_vinte': partite_vinte,
                'punti_totali': punti_totali or 0,
                'percentuale_vittoria': round(percentuale_vittoria, 1),
                'media_indizi_vincenti': round(media_indizi or 0, 1)
            })

        return jsonify(leaderboard)

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()




# Votazione Costumi
@app.route('/votazione-costumi')
def votazione_costumi():
    if 'player_id' not in session:
        return redirect(url_for('index'))
    return render_template('votazione_costumi.html')


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)