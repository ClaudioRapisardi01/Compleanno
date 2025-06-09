from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import json
from datetime import datetime
import secrets
import os
import uuid

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Cambia con una chiave sicura

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


# API per info giocatore
@app.route('/api/player-info')
def get_player_info():
    if 'player_id' not in session:
        return jsonify({'error': 'Non autorizzato'})

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT g.nome, g.squadra, g.punti_totali, g.foto_profilo, p.nome as personaggio
        FROM giocatori g 
        JOIN personaggi p ON g.personaggio_id = p.id 
        WHERE g.id = %s
    """, (session['player_id'],))
    player_info = cursor.fetchone()
    cursor.close()
    conn.close()

    if player_info:
        return jsonify({
            'nome': player_info[0],
            'squadra': player_info[1],
            'punti_totali': player_info[2],
            'foto_profilo': player_info[3],
            'personaggio': player_info[4]
        })
    return jsonify({'error': 'Giocatore non trovato'})


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
        # Verifica che il personaggio non sia già preso
        cursor.execute("SELECT nome FROM personaggi WHERE id = %s AND disponibile = TRUE", (personaggio_id,))
        personaggio = cursor.fetchone()

        if not personaggio:
            return jsonify({'success': False, 'error': 'Personaggio non disponibile'})

        # Verifica che il nome non sia già usato
        cursor.execute("SELECT id FROM giocatori WHERE nome = %s", (nome,))
        if cursor.fetchone():
            return jsonify({'success': False, 'error': 'Nome già utilizzato'})

        # Registra il giocatore
        cursor.execute("""
            INSERT INTO giocatori (nome, squadra, personaggio_id, punti_totali) 
            VALUES (%s, %s, %s, 0)
        """, (nome, squadra, personaggio_id))

        player_id = cursor.lastrowid

        # Marca il personaggio come non disponibile
        cursor.execute("UPDATE personaggi SET disponibile = FALSE WHERE id = %s", (personaggio_id,))

        conn.commit()

        # Salva in sessione
        session['player_id'] = player_id
        session['player_name'] = nome
        session['team'] = squadra
        session['personaggio'] = personaggio[0]
        session['personaggio_id'] = personaggio_id

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



# API Gamemaster - Gestione domande quiz
@app.route('/api/gamemaster/quiz-questions')
def get_quiz_questions():
    if not session.get('is_gamemaster'):
        return jsonify({'error': 'Non autorizzato'}), 403

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT * FROM quiz_domande ORDER BY categoria, id")
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
                'categoria': q[7] if len(q) > 7 else 'generale'
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
        return jsonify({'error': 'Non autorizzato'})

    data = request.get_json()
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO quiz_domande (domanda, opzione_a, opzione_b, opzione_c, opzione_d, risposta_corretta, categoria)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (data['domanda'], data['opzione_a'], data['opzione_b'],
          data['opzione_c'], data['opzione_d'], data['risposta_corretta'], data['categoria']))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({'success': True})


@app.route('/api/gamemaster/quiz-questions/<int:question_id>', methods=['PUT'])
def update_quiz_question(question_id):
    if not session.get('is_gamemaster'):
        return jsonify({'error': 'Non autorizzato'})

    data = request.get_json()
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE quiz_domande 
        SET domanda = %s, opzione_a = %s, opzione_b = %s, opzione_c = %s, 
            opzione_d = %s, risposta_corretta = %s, categoria = %s
        WHERE id = %s
    """, (data['domanda'], data['opzione_a'], data['opzione_b'],
          data['opzione_c'], data['opzione_d'], data['risposta_corretta'],
          data['categoria'], question_id))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({'success': True})


@app.route('/api/gamemaster/quiz-questions/<int:question_id>', methods=['DELETE'])
def delete_quiz_question(question_id):
    if not session.get('is_gamemaster'):
        return jsonify({'error': 'Non autorizzato'})

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM quiz_domande WHERE id = %s", (question_id,))
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({'success': True})


@app.route('/gamemaster/set-game', methods=['POST'])
def set_active_game():
    if not session.get('is_gamemaster'):
        return jsonify({'error': 'Non autorizzato'})

    data = request.get_json()
    gioco = data.get('gioco')
    messaggio = data.get('messaggio', '')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO stato_gioco (id, gioco_attivo, messaggio, ultimo_aggiornamento) 
        VALUES (1, %s, %s, NOW()) 
        ON DUPLICATE KEY UPDATE 
        gioco_attivo = %s, messaggio = %s, ultimo_aggiornamento = NOW()
    """, (gioco, messaggio, gioco, messaggio))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({'success': True})


@app.route('/gamemaster/stop-game', methods=['POST'])
def stop_game():
    if not session.get('is_gamemaster'):
        return jsonify({'error': 'Non autorizzato'})

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE stato_gioco 
        SET gioco_attivo = NULL, messaggio = 'In attesa del prossimo gioco...', ultimo_aggiornamento = NOW() 
        WHERE id = 1
    """)

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({'success': True})


# QUIZ PERSONALIZZATO
@app.route('/quiz-personalizzato')
def quiz_personalizzato():
    if 'player_id' not in session:
        return redirect(url_for('index'))

    # Verifica che il gioco sia attivo
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT gioco_attivo FROM stato_gioco WHERE id = 1")
    stato = cursor.fetchone()

    if not stato or stato[0] != 'quiz_personalizzato':
        cursor.close()
        conn.close()
        return redirect(url_for('dashboard'))

    cursor.execute("SELECT * FROM quiz_domande ORDER BY RAND() LIMIT 10")
    domande = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('quiz_personalizzato.html', domande=domande)


@app.route('/submit-quiz', methods=['POST'])
def submit_quiz():
    if 'player_id' not in session:
        return jsonify({'error': 'Non autorizzato'})

    data = request.get_json()
    risposte = data.get('risposte', {})
    punteggio = data.get('punteggio', 0)
    tempo_totale = data.get('tempo_totale', 0)

    conn = get_db_connection()
    cursor = conn.cursor()

    # Aggiorna punteggio giocatore
    cursor.execute("""
        UPDATE giocatori 
        SET punti_totali = punti_totali + %s 
        WHERE id = %s
    """, (punteggio, session['player_id']))

    # Registra partecipazione
    cursor.execute("""
        INSERT INTO partecipazioni (giocatore_id, gioco, punti, timestamp) 
        VALUES (%s, 'quiz_personalizzato', %s, NOW())
    """, (session['player_id'], punteggio))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({'success': True, 'punti': punteggio})


# CLASSIFICA
@app.route('/classifica')
def classifica():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Classifica individuale
    cursor.execute("""
        SELECT g.nome, g.squadra, p.nome as personaggio, g.punti_totali, g.foto_profilo
        FROM giocatori g
        JOIN personaggi p ON g.personaggio_id = p.id
        ORDER BY g.punti_totali DESC
    """)
    classifica_individuale = cursor.fetchall()

    # Classifica squadre
    cursor.execute("""
        SELECT squadra, SUM(punti_totali) as punti_squadra, COUNT(*) as membri
        FROM giocatori 
        GROUP BY squadra 
        ORDER BY punti_squadra DESC
    """)
    classifica_squadre = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('classifica.html',
                           individuale=classifica_individuale,
                           squadre=classifica_squadre)


@app.route('/api/classifica')
def api_classifica():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT g.nome, g.squadra, g.punti_totali, g.foto_profilo
        FROM giocatori g
        ORDER BY g.punti_totali DESC 
        LIMIT 10
    """)
    top_players = cursor.fetchall()

    cursor.close()
    conn.close()

    return jsonify([{
        'nome': player[0],
        'squadra': player[1],
        'punti': player[2],
        'foto_profilo': player[3]
    } for player in top_players])


# Aggiungi queste nuove route al tuo file app.py

# API Gamemaster - Gestione personaggi
@app.route('/api/gamemaster/personaggi')
def get_all_personaggi():
    if not session.get('is_gamemaster'):
        return jsonify({'error': 'Non autorizzato'}), 403

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT p.id, p.nome, p.descrizione, p.disponibile,
                   g.nome as giocatore_nome, g.id as giocatore_id
            FROM personaggi p
            LEFT JOIN giocatori g ON p.id = g.personaggio_id
            ORDER BY p.nome
        """)
        personaggi = cursor.fetchall()

        personaggi_list = []
        for p in personaggi:
            personaggi_list.append({
                'id': p[0],
                'nome': p[1],
                'descrizione': p[2],
                'disponibile': bool(p[3]),
                'giocatore_nome': p[4],
                'giocatore_id': p[5]
            })

        return jsonify(personaggi_list)

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/api/gamemaster/personaggi/<int:personaggio_id>/toggle', methods=['POST'])
def toggle_personaggio_availability(personaggio_id):
    if not session.get('is_gamemaster'):
        return jsonify({'error': 'Non autorizzato'}), 403

    data = request.get_json()
    make_available = data.get('disponibile', True)

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Se stiamo rendendo non disponibile un personaggio già assegnato
        if not make_available:
            cursor.execute("""
                SELECT g.id, g.nome FROM giocatori g 
                WHERE g.personaggio_id = %s
            """, (personaggio_id,))
            giocatore = cursor.fetchone()

            if giocatore:
                return jsonify({
                    'success': False,
                    'error': f'Personaggio assegnato a {giocatore[1]}. Disconnetti prima il giocatore.'
                })

        # Aggiorna disponibilità
        cursor.execute("""
            UPDATE personaggi SET disponibile = %s WHERE id = %s
        """, (make_available, personaggio_id))

        conn.commit()
        return jsonify({'success': True})

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/api/gamemaster/personaggi', methods=['POST'])
def add_personaggio():
    if not session.get('is_gamemaster'):
        return jsonify({'error': 'Non autorizzato'}), 403

    data = request.get_json()
    nome = data.get('nome', '').strip()
    descrizione = data.get('descrizione', '').strip()

    if not nome:
        return jsonify({'error': 'Nome personaggio obbligatorio'})

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO personaggi (nome, descrizione, disponibile)
            VALUES (%s, %s, TRUE)
        """, (nome, descrizione))

        conn.commit()
        return jsonify({'success': True})

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/api/gamemaster/personaggi/<int:personaggio_id>', methods=['PUT'])
def update_personaggio(personaggio_id):
    if not session.get('is_gamemaster'):
        return jsonify({'error': 'Non autorizzato'}), 403

    data = request.get_json()
    nome = data.get('nome', '').strip()
    descrizione = data.get('descrizione', '').strip()

    if not nome:
        return jsonify({'error': 'Nome personaggio obbligatorio'})

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            UPDATE personaggi 
            SET nome = %s, descrizione = %s
            WHERE id = %s
        """, (nome, descrizione, personaggio_id))

        conn.commit()
        return jsonify({'success': True})

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/api/gamemaster/personaggi/<int:personaggio_id>', methods=['DELETE'])
def delete_personaggio(personaggio_id):
    if not session.get('is_gamemaster'):
        return jsonify({'error': 'Non autorizzato'}), 403

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Controlla se il personaggio è assegnato
        cursor.execute("""
            SELECT g.nome FROM giocatori g WHERE g.personaggio_id = %s
        """, (personaggio_id,))
        giocatore = cursor.fetchone()

        if giocatore:
            return jsonify({
                'success': False,
                'error': f'Impossibile eliminare: personaggio assegnato a {giocatore[0]}'
            })

        cursor.execute("DELETE FROM personaggi WHERE id = %s", (personaggio_id,))
        conn.commit()
        return jsonify({'success': True})

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


# API Gamemaster - Gestione giocatori e disconnessioni
@app.route('/api/gamemaster/players/<int:player_id>/disconnect', methods=['POST'])
def disconnect_player(player_id):
    if not session.get('is_gamemaster'):
        return jsonify({'error': 'Non autorizzato'}), 403

    data = request.get_json()
    reason = data.get('reason', 'Disconnesso dal gamemaster')

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Ottieni info giocatore
        cursor.execute("""
            SELECT nome, personaggio_id FROM giocatori WHERE id = %s
        """, (player_id,))
        giocatore = cursor.fetchone()

        if not giocatore:
            return jsonify({'error': 'Giocatore non trovato'})

        nome_giocatore = giocatore[0]
        personaggio_id = giocatore[1]

        # Registra la disconnessione per audit
        cursor.execute("""
            INSERT INTO disconnessioni (giocatore_id, motivo, timestamp, gamemaster_action)
            VALUES (%s, %s, NOW(), TRUE)
        """, (player_id, reason))

        # Libera il personaggio
        cursor.execute("""
            UPDATE personaggi SET disponibile = TRUE WHERE id = %s
        """, (personaggio_id,))

        # Rimuovi il giocatore
        cursor.execute("DELETE FROM giocatori WHERE id = %s", (player_id,))

        conn.commit()

        return jsonify({
            'success': True,
            'message': f'Giocatore {nome_giocatore} disconnesso'
        })

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/api/gamemaster/players/<int:player_id>/kick-from-game', methods=['POST'])
def kick_from_game(player_id):
    """Interrompe la partita di un giocatore senza disconnetterlo completamente"""
    if not session.get('is_gamemaster'):
        return jsonify({'error': 'Non autorizzato'}), 403

    data = request.get_json()
    reason = data.get('reason', 'Escluso dal gioco corrente')

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Registra l'esclusione dal gioco
        cursor.execute("""
            INSERT INTO esclusioni_gioco (giocatore_id, gioco_corrente, motivo, timestamp)
            VALUES (%s, (SELECT gioco_attivo FROM stato_gioco WHERE id = 1), %s, NOW())
        """, (player_id, reason))

        # Aggiorna il flag di esclusione del giocatore
        cursor.execute("""
            UPDATE giocatori SET escluso_da_gioco = TRUE WHERE id = %s
        """, (player_id,))

        conn.commit()

        return jsonify({
            'success': True,
            'message': 'Giocatore escluso dal gioco corrente'
        })

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/api/gamemaster/players/<int:player_id>/restore', methods=['POST'])
def restore_player(player_id):
    """Ripristina un giocatore escluso dal gioco"""
    if not session.get('is_gamemaster'):
        return jsonify({'error': 'Non autorizzato'}), 403

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            UPDATE giocatori SET escluso_da_gioco = FALSE WHERE id = %s
        """, (player_id,))

        conn.commit()

        return jsonify({
            'success': True,
            'message': 'Giocatore ripristinato'
        })

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


# API per controllo esclusione dal gioco (chiamata dai giocatori)
@app.route('/api/check-game-exclusion')
def check_game_exclusion():
    if 'player_id' not in session:
        return jsonify({'excluded': False})

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT escluso_da_gioco FROM giocatori WHERE id = %s
        """, (session['player_id'],))
        result = cursor.fetchone()

        excluded = result[0] if result else False

        return jsonify({'excluded': bool(excluded)})

    except mysql.connector.Error as err:
        return jsonify({'excluded': False})
    finally:
        cursor.close()
        conn.close()


# Aggiorna la query per i giocatori per includere lo stato di esclusione
@app.route('/api/gamemaster/players')
def get_players():
    if not session.get('is_gamemaster'):
        return jsonify({'error': 'Non autorizzato'}), 403

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT g.id, g.nome, g.squadra, g.punti_totali, g.foto_profilo, 
                   p.nome as personaggio, g.escluso_da_gioco,
                   DATE_FORMAT(g.ultima_attivita, '%H:%i') as ultima_attivita
            FROM giocatori g
            JOIN personaggi p ON g.personaggio_id = p.id
            ORDER BY g.punti_totali DESC
        """)
        players = cursor.fetchall()

        players_list = []
        for p in players:
            players_list.append({
                'id': p[0],
                'nome': p[1],
                'squadra': p[2],
                'punti': p[3],
                'foto_profilo': p[4],
                'personaggio': p[5],
                'escluso_da_gioco': bool(p[6]) if p[6] is not None else False,
                'ultima_attivita': p[7]
            })

        return jsonify(players_list)

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


# Aggiungi queste route al tuo file app.py per il gioco "Indovina Chi"

import random
from werkzeug.utils import secure_filename
import uuid
import os


# ========================
# ROUTE GAMEMASTER - GESTIONE PERSONE E INDIZI
# ========================

@app.route('/api/gamemaster/indovina-persone')
def get_indovina_persone():
    """Ottieni tutte le persone per Indovina Chi"""
    if not session.get('is_gamemaster'):
        return jsonify({'error': 'Non autorizzato'}), 403

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT ip.id, ip.nome, ip.foto_filename, ip.descrizione, ip.attivo,
                   COUNT(ii.id) as num_indizi
            FROM indovina_persone ip
            LEFT JOIN indovina_indizi ii ON ip.id = ii.persona_id
            GROUP BY ip.id
            ORDER BY ip.nome
        """)
        persone = cursor.fetchall()

        persone_list = []
        for p in persone:
            persone_list.append({
                'id': p[0],
                'nome': p[1],
                'foto_filename': p[2],
                'descrizione': p[3],
                'attivo': bool(p[4]),
                'num_indizi': p[5]
            })

        return jsonify(persone_list)

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/api/gamemaster/indovina-persone', methods=['POST'])
def add_indovina_persona():
    """Aggiungi una nuova persona per Indovina Chi"""
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

        persona_id = cursor.lastrowid
        conn.commit()

        return jsonify({'success': True, 'persona_id': persona_id})

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/api/gamemaster/indovina-persone/<int:persona_id>', methods=['PUT'])
def update_indovina_persona(persona_id):
    """Aggiorna una persona"""
    if not session.get('is_gamemaster'):
        return jsonify({'error': 'Non autorizzato'}), 403

    data = request.get_json()
    nome = data.get('nome', '').strip()
    descrizione = data.get('descrizione', '').strip()
    attivo = data.get('attivo', True)

    if not nome:
        return jsonify({'error': 'Nome obbligatorio'})

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            UPDATE indovina_persone 
            SET nome = %s, descrizione = %s, attivo = %s
            WHERE id = %s
        """, (nome, descrizione, attivo, persona_id))

        conn.commit()
        return jsonify({'success': True})

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/api/gamemaster/indovina-persone/<int:persona_id>', methods=['DELETE'])
def delete_indovina_persona(persona_id):
    """Elimina una persona (cascade elimina anche gli indizi)"""
    if not session.get('is_gamemaster'):
        return jsonify({'error': 'Non autorizzato'}), 403

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Controlla se ci sono partite attive per questa persona
        cursor.execute("""
            SELECT COUNT(*) FROM indovina_partite 
            WHERE persona_id = %s AND stato = 'attiva'
        """, (persona_id,))

        if cursor.fetchone()[0] > 0:
            return jsonify({'error': 'Impossibile eliminare: partita attiva in corso'})

        cursor.execute("DELETE FROM indovina_persone WHERE id = %s", (persona_id,))
        conn.commit()
        return jsonify({'success': True})

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/api/gamemaster/indovina-indizi/<int:persona_id>')
def get_indizi_persona(persona_id):
    """Ottieni tutti gli indizi di una persona"""
    if not session.get('is_gamemaster'):
        return jsonify({'error': 'Non autorizzato'}), 403

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT id, indizio, ordine, punti
            FROM indovina_indizi
            WHERE persona_id = %s
            ORDER BY ordine
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
    """Aggiungi un indizio a una persona"""
    if not session.get('is_gamemaster'):
        return jsonify({'error': 'Non autorizzato'}), 403

    data = request.get_json()
    persona_id = data.get('persona_id')
    indizio = data.get('indizio', '').strip()
    ordine = data.get('ordine', 1)
    punti = data.get('punti', 0)

    if not all([persona_id, indizio]):
        return jsonify({'error': 'Tutti i campi sono obbligatori'})

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
    """Aggiorna un indizio"""
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
    """Elimina un indizio"""
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


# ========================
# ROUTE GAMEMASTER - GESTIONE PARTITE
# ========================

@app.route('/api/gamemaster/indovina-start', methods=['POST'])
def start_indovina_partita():
    """Avvia una nuova partita di Indovina Chi"""
    if not session.get('is_gamemaster'):
        return jsonify({'error': 'Non autorizzato'}), 403

    data = request.get_json()
    persona_id = data.get('persona_id')

    if not persona_id:
        # Scegli persona casuale tra quelle attive
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id FROM indovina_persone 
            WHERE attivo = TRUE 
            AND id IN (SELECT persona_id FROM indovina_indizi GROUP BY persona_id HAVING COUNT(*) >= 3)
            ORDER BY RAND() 
            LIMIT 1
        """)

        result = cursor.fetchone()
        if not result:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Nessuna persona disponibile con abbastanza indizi'})

        persona_id = result[0]
        cursor.close()
        conn.close()

    # Termina eventuali partite attive
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Chiudi partite precedenti
        cursor.execute("""
            UPDATE indovina_partite 
            SET stato = 'completata', tempo_fine = NOW() 
            WHERE stato = 'attiva'
        """)

        # Crea nuova partita
        cursor.execute("""
            INSERT INTO indovina_partite (persona_id, indizio_corrente, stato)
            VALUES (%s, 1, 'attiva')
        """, (persona_id,))

        partita_id = cursor.lastrowid
        conn.commit()

        return jsonify({'success': True, 'partita_id': partita_id, 'persona_id': persona_id})

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/api/gamemaster/indovina-next-clue', methods=['POST'])
def next_indovina_clue():
    """Passa al prossimo indizio"""
    if not session.get('is_gamemaster'):
        return jsonify({'error': 'Non autorizzato'}), 403

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Trova partita attiva
        cursor.execute("""
            SELECT id, persona_id, indizio_corrente 
            FROM indovina_partite 
            WHERE stato = 'attiva' 
            LIMIT 1
        """)

        partita = cursor.fetchone()
        if not partita:
            return jsonify({'error': 'Nessuna partita attiva'})

        partita_id, persona_id, indizio_corrente = partita

        # Controlla se ci sono altri indizi
        cursor.execute("""
            SELECT COUNT(*) FROM indovina_indizi 
            WHERE persona_id = %s AND ordine > %s
        """, (persona_id, indizio_corrente))

        if cursor.fetchone()[0] == 0:
            # Nessun indizio successivo, termina partita
            cursor.execute("""
                UPDATE indovina_partite 
                SET stato = 'completata', tempo_fine = NOW() 
                WHERE id = %s
            """, (partita_id,))
            conn.commit()
            return jsonify({'success': True, 'game_ended': True})

        # Passa al prossimo indizio
        cursor.execute("""
            UPDATE indovina_partite 
            SET indizio_corrente = indizio_corrente + 1 
            WHERE id = %s
        """, (partita_id,))

        conn.commit()
        return jsonify({'success': True, 'next_clue': indizio_corrente + 1})

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/api/gamemaster/indovina-end', methods=['POST'])
def end_indovina_partita():
    """Termina la partita corrente"""
    if not session.get('is_gamemaster'):
        return jsonify({'error': 'Non autorizzato'}), 403

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            UPDATE indovina_partite 
            SET stato = 'completata', tempo_fine = NOW() 
            WHERE stato = 'attiva'
        """)

        conn.commit()
        return jsonify({'success': True})

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


# ========================
# ROUTE GIOCATORI - GAMEPLAY
# ========================

@app.route('/indovina-chi')
def indovina_chi_game():
    """Pagina del gioco Indovina Chi"""
    if 'player_id' not in session:
        return redirect(url_for('index'))

    # Verifica che il gioco sia attivo
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT gioco_attivo FROM stato_gioco WHERE id = 1")
    stato = cursor.fetchone()

    if not stato or stato[0] != 'indovina_chi':
        cursor.close()
        conn.close()
        return redirect(url_for('dashboard'))

    cursor.close()
    conn.close()
    return render_template('indovina_chi.html')


@app.route('/api/indovina-status')
def indovina_game_status():
    """Ottieni lo stato attuale del gioco per i giocatori"""
    if 'player_id' not in session:
        return jsonify({'error': 'Non autorizzato'})

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Trova partita attiva
        cursor.execute("""
            SELECT ip.id, ip.persona_id, ip.indizio_corrente, ip.stato,
                   ipe.nome, ipe.foto_filename
            FROM indovina_partite ip
            JOIN indovina_persone ipe ON ip.persona_id = ipe.id
            WHERE ip.stato = 'attiva'
            LIMIT 1
        """)

        partita = cursor.fetchone()
        if not partita:
            return jsonify({'game_active': False, 'message': 'Nessuna partita attiva'})

        partita_id, persona_id, indizio_corrente, stato, nome_persona, foto = partita

        # Ottieni l'indizio corrente
        cursor.execute("""
            SELECT indizio, punti FROM indovina_indizi
            WHERE persona_id = %s AND ordine = %s
        """, (persona_id, indizio_corrente))

        indizio_data = cursor.fetchone()
        if not indizio_data:
            return jsonify({'game_active': False, 'message': 'Errore nel caricamento indizio'})

        indizio, punti = indizio_data

        # Controlla se il giocatore ha già risposto a questo indizio
        cursor.execute("""
            SELECT id, corretta, punti_ottenuti FROM indovina_risposte
            WHERE partita_id = %s AND giocatore_id = %s AND indizio_numero = %s
        """, (partita_id, session['player_id'], indizio_corrente))

        risposta_esistente = cursor.fetchone()

        return jsonify({
            'game_active': True,
            'partita_id': partita_id,
            'persona_nome': nome_persona,
            'persona_foto': foto,
            'indizio_corrente': indizio_corrente,
            'indizio_testo': indizio,
            'punti_disponibili': punti,
            'ha_risposto': risposta_esistente is not None,
            'risposta_corretta': risposta_esistente[1] if risposta_esistente else None,
            'punti_ottenuti': risposta_esistente[2] if risposta_esistente else 0
        })

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/api/indovina-answer', methods=['POST'])
def submit_indovina_answer():
    """Invia una risposta per Indovina Chi"""
    if 'player_id' not in session:
        return jsonify({'error': 'Non autorizzato'})

    data = request.get_json()
    risposta = data.get('risposta', '').strip()

    if not risposta:
        return jsonify({'error': 'Risposta obbligatoria'})

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Trova partita attiva
        cursor.execute("""
            SELECT ip.id, ip.persona_id, ip.indizio_corrente,
                   ipe.nome
            FROM indovina_partite ip
            JOIN indovina_persone ipe ON ip.persona_id = ipe.id
            WHERE ip.stato = 'attiva'
            LIMIT 1
        """)

        partita = cursor.fetchone()
        if not partita:
            return jsonify({'error': 'Nessuna partita attiva'})

        partita_id, persona_id, indizio_corrente, nome_corretto = partita

        # Controlla se ha già risposto a questo indizio
        cursor.execute("""
            SELECT id FROM indovina_risposte
            WHERE partita_id = %s AND giocatore_id = %s AND indizio_numero = %s
        """, (partita_id, session['player_id'], indizio_corrente))

        if cursor.fetchone():
            return jsonify({'error': 'Hai già risposto a questo indizio'})

        # Ottieni i punti per questo indizio
        cursor.execute("""
            SELECT punti FROM indovina_indizi
            WHERE persona_id = %s AND ordine = %s
        """, (persona_id, indizio_corrente))

        punti_indizio = cursor.fetchone()
        if not punti_indizio:
            return jsonify({'error': 'Errore nel caricamento indizio'})

        punti_disponibili = punti_indizio[0]

        # Controlla se la risposta è corretta (case-insensitive, ignora spazi)
        risposta_pulita = risposta.lower().strip()
        nome_pulito = nome_corretto.lower().strip()

        corretta = risposta_pulita == nome_pulito
        punti_ottenuti = punti_disponibili if corretta else 0

        # Salva la risposta
        cursor.execute("""
            INSERT INTO indovina_risposte 
            (partita_id, giocatore_id, risposta, indizio_numero, corretta, punti_ottenuti)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (partita_id, session['player_id'], risposta, indizio_corrente, corretta, punti_ottenuti))

        # Aggiorna punti giocatore se corretta
        if corretta:
            cursor.execute("""
                UPDATE giocatori 
                SET punti_totali = punti_totali + %s 
                WHERE id = %s
            """, (punti_ottenuti, session['player_id']))

            # Registra partecipazione
            cursor.execute("""
                INSERT INTO partecipazioni (giocatore_id, gioco, punti, timestamp)
                VALUES (%s, 'indovina_chi', %s, NOW())
            """, (session['player_id'], punti_ottenuti))

        conn.commit()

        return jsonify({
            'success': True,
            'corretta': corretta,
            'punti_ottenuti': punti_ottenuti,
            'nome_corretto': nome_corretto if corretta else None
        })

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/api/indovina-leaderboard')
def indovina_leaderboard():
    """Classifica specifica per Indovina Chi"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT g.nome, g.squadra, g.foto_profilo,
                   COALESCE(SUM(ir.punti_ottenuti), 0) as punti_indovina,
                   COUNT(CASE WHEN ir.corretta = TRUE THEN 1 END) as risposte_corrette,
                   COUNT(ir.id) as risposte_totali
            FROM giocatori g
            LEFT JOIN indovina_risposte ir ON g.id = ir.giocatore_id
            GROUP BY g.id
            ORDER BY punti_indovina DESC, risposte_corrette DESC
            LIMIT 10
        """)

        classifica = cursor.fetchall()

        leaderboard = []
        for i, (nome, squadra, foto, punti, corrette, totali) in enumerate(classifica):
            leaderboard.append({
                'posizione': i + 1,
                'nome': nome,
                'squadra': squadra,
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


# Aggiungi queste route al tuo app.py

import json
import random
from datetime import datetime, timedelta


# ========================
# LUPUS IN FABULA - ROUTES GAMEMASTER
# ========================

@app.route('/api/gamemaster/lupus-configs')
def get_lupus_configs():
    """Ottieni configurazioni predefinite per Lupus"""
    if not session.get('is_gamemaster'):
        return jsonify({'error': 'Non autorizzato'}), 403

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT id, nome_config, descrizione, min_giocatori, max_giocatori,
                   durata_notte_secondi, durata_giorno_secondi, durata_votazione_secondi,
                   ruoli_configurazione, attiva
            FROM lupus_configurazioni
            WHERE attiva = TRUE
            ORDER BY min_giocatori ASC
        """)
        configs = cursor.fetchall()

        configs_list = []
        for config in configs:
            configs_list.append({
                'id': config[0],
                'nome': config[1],
                'descrizione': config[2],
                'min_giocatori': config[3],
                'max_giocatori': config[4],
                'durata_notte': config[5],
                'durata_giorno': config[6],
                'durata_votazione': config[7],
                'ruoli': json.loads(config[8]) if config[8] else {},
                'attiva': bool(config[9])
            })

        return jsonify(configs_list)

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/api/gamemaster/lupus-start', methods=['POST'])
def start_lupus_game():
    """Avvia una nuova partita di Lupus"""
    if not session.get('is_gamemaster'):
        return jsonify({'error': 'Non autorizzato'}), 403

    data = request.get_json()
    config_id = data.get('config_id')
    custom_config = data.get('custom_config')

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Ottieni giocatori disponibili
        cursor.execute("""
            SELECT id, nome FROM giocatori 
            WHERE escluso_da_gioco != TRUE OR escluso_da_gioco IS NULL
            ORDER BY punti_totali DESC
        """)
        available_players = cursor.fetchall()

        if len(available_players) < 6:
            return jsonify({'error': 'Servono almeno 6 giocatori per Lupus'})

        # Ottieni configurazione
        if config_id:
            cursor.execute("""
                SELECT ruoli_configurazione, durata_notte_secondi, 
                       durata_giorno_secondi, durata_votazione_secondi
                FROM lupus_configurazioni WHERE id = %s
            """, (config_id,))
            config_data = cursor.fetchone()
            if not config_data:
                return jsonify({'error': 'Configurazione non trovata'})

            ruoli_config = json.loads(config_data[0])
            durata_notte = config_data[1]
            durata_giorno = config_data[2]
            durata_votazione = config_data[3]
        else:
            # Usa configurazione personalizzata
            ruoli_config = custom_config['ruoli']
            durata_notte = custom_config.get('durata_notte', 120)
            durata_giorno = custom_config.get('durata_giorno', 180)
            durata_votazione = custom_config.get('durata_votazione', 90)

        # Calcola numero totale giocatori necessari
        total_players_needed = sum(ruoli_config.values())
        if len(available_players) < total_players_needed:
            return jsonify({
                'error': f'Servono {total_players_needed} giocatori, disponibili: {len(available_players)}'
            })

        # Termina eventuali partite attive
        cursor.execute("UPDATE lupus_partite SET stato = 'ended' WHERE stato != 'ended'")

        # Crea nuova partita
        cursor.execute("""
            INSERT INTO lupus_partite (stato, fase_corrente, durata_fase_secondi)
            VALUES ('waiting', 'setup', %s)
        """, (durata_notte,))

        partita_id = cursor.lastrowid

        # Assegna ruoli
        assigned_roles = assign_lupus_roles(cursor, partita_id, available_players, ruoli_config)

        # Aggiorna stato gioco globale
        cursor.execute("""
            INSERT INTO stato_gioco (id, gioco_attivo, messaggio, ultimo_aggiornamento) 
            VALUES (1, 'lupus_in_fabula', 'Lupus in Fabula sta per iniziare! 🐺', NOW()) 
            ON DUPLICATE KEY UPDATE 
            gioco_attivo = 'lupus_in_fabula', 
            messaggio = 'Lupus in Fabula sta per iniziare! 🐺', 
            ultimo_aggiornamento = NOW()
        """)

        conn.commit()

        return jsonify({
            'success': True,
            'partita_id': partita_id,
            'giocatori_assegnati': len(assigned_roles),
            'ruoli_assegnati': assigned_roles
        })

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


def assign_lupus_roles(cursor, partita_id, players, ruoli_config):
    """Assegna ruoli casuali ai giocatori"""

    # Ottieni tutti i ruoli disponibili
    cursor.execute("SELECT id, nome FROM lupus_ruoli WHERE attivo = TRUE")
    all_roles = {nome: role_id for role_id, nome in cursor.fetchall()}

    # Crea lista di ruoli da assegnare
    roles_to_assign = []
    for role_name, count in ruoli_config.items():
        if role_name in all_roles:
            roles_to_assign.extend([all_roles[role_name]] * count)

    # Mescola giocatori e ruoli
    players_list = list(players)
    random.shuffle(players_list)
    random.shuffle(roles_to_assign)

    # Assegna ruoli
    assigned = []
    for i, (player_id, player_name) in enumerate(players_list[:len(roles_to_assign)]):
        role_id = roles_to_assign[i]

        cursor.execute("""
            INSERT INTO lupus_partecipazioni (partita_id, giocatore_id, ruolo_id)
            VALUES (%s, %s, %s)
        """, (partita_id, player_id, role_id))

        # Ottieni nome ruolo per risposta
        cursor.execute("SELECT nome FROM lupus_ruoli WHERE id = %s", (role_id,))
        role_name = cursor.fetchone()[0]

        assigned.append({
            'player_id': player_id,
            'player_name': player_name,
            'role_name': role_name
        })

    return assigned


@app.route('/api/gamemaster/lupus-phase', methods=['POST'])
def change_lupus_phase():
    """Cambia fase della partita Lupus"""
    if not session.get('is_gamemaster'):
        return jsonify({'error': 'Non autorizzato'}), 403

    data = request.get_json()
    new_phase = data.get('phase')  # 'night', 'day', 'voting', 'ended'

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Trova partita attiva
        cursor.execute("""
            SELECT id, fase_corrente, turno_numero 
            FROM lupus_partite 
            WHERE stato != 'ended' 
            ORDER BY id DESC LIMIT 1
        """)

        partita = cursor.fetchone()
        if not partita:
            return jsonify({'error': 'Nessuna partita attiva'})

        partita_id, current_phase, turno = partita

        # Esegui azioni di fine fase se necessario
        if current_phase == 'night':
            process_night_actions(cursor, partita_id, turno)
        elif current_phase == 'voting':
            process_voting_results(cursor, partita_id, turno)

        # Determina durata nuova fase
        phase_durations = {
            'night': 120,
            'day': 180,
            'voting': 90
        }
        duration = phase_durations.get(new_phase, 60)

        # Incrementa turno se si passa da voting a night
        if current_phase == 'voting' and new_phase == 'night':
            turno += 1

        # Aggiorna partita
        cursor.execute("""
            UPDATE lupus_partite 
            SET fase_corrente = %s, tempo_fase_inizio = NOW(), 
                durata_fase_secondi = %s, turno_numero = %s
            WHERE id = %s
        """, (new_phase, duration, turno, partita_id))

        # Log evento
        cursor.execute("""
            INSERT INTO lupus_eventi (partita_id, turno, fase, tipo_evento, descrizione)
            VALUES (%s, %s, %s, 'cambio_fase', %s)
        """, (partita_id, turno, new_phase, f'Cambiata fase da {current_phase} a {new_phase}'))

        conn.commit()

        return jsonify({'success': True, 'new_phase': new_phase, 'turno': turno})

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


def process_night_actions(cursor, partita_id, turno):
    """Processa tutte le azioni notturne"""

    # Ottieni tutte le azioni della notte in ordine di priorità
    cursor.execute("""
        SELECT la.giocatore_id, la.tipo_azione, la.target_giocatore_id, lr.priorita_azione
        FROM lupus_azioni la
        JOIN lupus_partecipazioni lp ON la.giocatore_id = lp.giocatore_id
        JOIN lupus_ruoli lr ON lp.ruolo_id = lr.id
        WHERE la.partita_id = %s AND la.turno = %s AND la.fase = 'notte'
        ORDER BY lr.priorita_azione DESC
    """, (partita_id, turno))

    actions = cursor.fetchall()

    protected_players = set()
    killed_players = []
    investigation_results = []

    for giocatore_id, tipo_azione, target_id, priorita in actions:
        if tipo_azione == 'protect':
            protected_players.add(target_id)
        elif tipo_azione == 'kill' and target_id not in protected_players:
            killed_players.append(target_id)
        elif tipo_azione == 'investigate':
            # Ottieni ruolo del target
            cursor.execute("""
                SELECT lr.team FROM lupus_partecipazioni lp
                JOIN lupus_ruoli lr ON lp.ruolo_id = lr.id
                WHERE lp.partita_id = %s AND lp.giocatore_id = %s
            """, (partita_id, target_id))
            target_team = cursor.fetchone()[0]
            investigation_results.append((giocatore_id, target_id, target_team))

    # Applica morti
    for player_id in set(killed_players):  # Remove duplicates
        cursor.execute("""
            UPDATE lupus_partecipazioni 
            SET stato = 'morto', morte_turno = %s, morte_fase = 'notte'
            WHERE partita_id = %s AND giocatore_id = %s
        """, (turno, partita_id, player_id))

        # Log morte
        cursor.execute("""
            INSERT INTO lupus_eventi (partita_id, turno, fase, tipo_evento, descrizione, giocatori_coinvolti)
            VALUES (%s, %s, 'notte', 'morte', 'Giocatore eliminato durante la notte', %s)
        """, (partita_id, turno, json.dumps([player_id])))

    # Salva risultati investigazioni
    for investigator_id, target_id, result in investigation_results:
        cursor.execute("""
            UPDATE lupus_azioni 
            SET risultato = %s, successo = TRUE
            WHERE partita_id = %s AND turno = %s AND giocatore_id = %s AND tipo_azione = 'investigate'
        """, (result, partita_id, turno, investigator_id))


def process_voting_results(cursor, partita_id, turno):
    """Processa risultati della votazione diurna"""

    # Conta voti con peso
    cursor.execute("""
        SELECT lv.votato_giocatore_id, SUM(lv.peso_voto) as voti_totali
        FROM lupus_votazioni lv
        WHERE lv.partita_id = %s AND lv.turno = %s
        GROUP BY lv.votato_giocatore_id
        ORDER BY voti_totali DESC
        LIMIT 1
    """, (partita_id, turno))

    result = cursor.fetchone()
    if result:
        eliminated_player_id, voti = result

        # Elimina giocatore
        cursor.execute("""
            UPDATE lupus_partecipazioni 
            SET stato = 'eliminato', morte_turno = %s, morte_fase = 'votazione'
            WHERE partita_id = %s AND giocatore_id = %s
        """, (turno, partita_id, eliminated_player_id))

        # Log eliminazione
        cursor.execute("""
            INSERT INTO lupus_eventi (partita_id, turno, fase, tipo_evento, descrizione, giocatori_coinvolti)
            VALUES (%s, %s, 'votazione', 'eliminazione', %s, %s)
        """, (partita_id, turno, f'Giocatore eliminato con {voti} voti', json.dumps([eliminated_player_id])))


@app.route('/api/gamemaster/lupus-status')
def get_lupus_game_status():
    """Ottieni stato attuale partita Lupus per gamemaster"""
    if not session.get('is_gamemaster'):
        return jsonify({'error': 'Non autorizzato'}), 403

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Trova partita attiva
        cursor.execute("""
            SELECT id, stato, fase_corrente, tempo_fase_inizio, durata_fase_secondi, 
                   turno_numero, vincitore
            FROM lupus_partite 
            WHERE stato != 'ended' 
            ORDER BY id DESC LIMIT 1
        """)

        partita = cursor.fetchone()
        if not partita:
            return jsonify({'game_active': False})

        partita_id, stato, fase, tempo_inizio, durata, turno, vincitore = partita

        # Calcola tempo rimanente
        time_elapsed = (datetime.now() - tempo_inizio).total_seconds()
        time_remaining = max(0, durata - time_elapsed)

        # Ottieni partecipanti
        cursor.execute("""
            SELECT g.id, g.nome, g.foto_profilo, lr.nome as ruolo, lr.emoji, 
                   lr.team, lp.stato, lp.morte_turno
            FROM lupus_partecipazioni lp
            JOIN giocatori g ON lp.giocatore_id = g.id
            JOIN lupus_ruoli lr ON lp.ruolo_id = lr.id
            WHERE lp.partita_id = %s
            ORDER BY lp.stato, g.nome
        """, (partita_id,))

        participants = []
        for p in cursor.fetchall():
            participants.append({
                'id': p[0],
                'nome': p[1],
                'foto_profilo': p[2],
                'ruolo': p[3],
                'emoji': p[4],
                'team': p[5],
                'stato': p[6],
                'morte_turno': p[7]
            })

        # Conta vivi per team
        vivi_lupi = len([p for p in participants if p['team'] == 'lupi' and p['stato'] == 'vivo'])
        vivi_cittadini = len([p for p in participants if p['team'] == 'cittadini' and p['stato'] == 'vivo'])

        return jsonify({
            'game_active': True,
            'partita_id': partita_id,
            'fase_corrente': fase,
            'turno': turno,
            'tempo_rimanente': int(time_remaining),
            'partecipanti': participants,
            'vivi_lupi': vivi_lupi,
            'vivi_cittadini': vivi_cittadini,
            'vincitore': vincitore
        })

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


# ========================
# LUPUS IN FABULA - ROUTES GIOCATORI
# ========================

@app.route('/lupus-in-fabula')
def lupus_game_page():
    """Pagina del gioco Lupus in Fabula"""
    if 'player_id' not in session:
        return redirect(url_for('index'))

    # Verifica che il gioco sia attivo
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT gioco_attivo FROM stato_gioco WHERE id = 1")
    stato = cursor.fetchone()

    if not stato or stato[0] != 'lupus_in_fabula':
        cursor.close()
        conn.close()
        return redirect(url_for('dashboard'))

    cursor.close()
    conn.close()
    return render_template('lupus_in_fabula.html')


@app.route('/api/lupus-player-status')
def get_lupus_player_status():
    """Ottieni stato del giocatore nella partita Lupus"""
    if 'player_id' not in session:
        return jsonify({'error': 'Non autorizzato'})

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Trova partita attiva e partecipazione del giocatore
        cursor.execute("""
            SELECT lpt.id, lpt.fase_corrente, lpt.tempo_fase_inizio, lpt.durata_fase_secondi,
                   lpt.turno_numero, lp.ruolo_id, lp.stato, lr.nome as ruolo_nome, 
                   lr.emoji, lr.team, lr.descrizione, lr.azione_notturna, lr.azione_diurna
            FROM lupus_partite lpt
            JOIN lupus_partecipazioni lp ON lpt.id = lp.partita_id
            JOIN lupus_ruoli lr ON lp.ruolo_id = lr.id
            WHERE lpt.stato != 'ended' AND lp.giocatore_id = %s
            ORDER BY lpt.id DESC LIMIT 1
        """, (session['player_id'],))

        result = cursor.fetchone()
        if not result:
            return jsonify({'in_game': False, 'message': 'Non sei in una partita attiva'})

        (partita_id, fase, tempo_inizio, durata, turno, ruolo_id, stato_player,
         ruolo_nome, emoji, team, descrizione, azione_notturna, azione_diurna) = result

        # Calcola tempo rimanente
        time_elapsed = (datetime.now() - tempo_inizio).total_seconds()
        time_remaining = max(0, durata - time_elapsed)

        # Ottieni lista altri giocatori (info base)
        cursor.execute("""
            SELECT g.id, g.nome, g.foto_profilo, lp.stato
            FROM lupus_partecipazioni lp
            JOIN giocatori g ON lp.giocatore_id = g.id
            WHERE lp.partita_id = %s AND lp.giocatore_id != %s
            ORDER BY lp.stato, g.nome
        """, (partita_id, session['player_id']))

        altri_giocatori = []
        for p in cursor.fetchall():
            altri_giocatori.append({
                'id': p[0],
                'nome': p[1],
                'foto_profilo': p[2],
                'stato': p[3]
            })

        # Se è un lupo, ottieni lista altri lupi
        altri_lupi = []
        if team == 'lupi':
            cursor.execute("""
                SELECT g.id, g.nome, g.foto_profilo
                FROM lupus_partecipazioni lp
                JOIN giocatori g ON lp.giocatore_id = g.id
                JOIN lupus_ruoli lr ON lp.ruolo_id = lr.id
                WHERE lp.partita_id = %s AND lr.team = 'lupi' AND lp.giocatore_id != %s
                AND lp.stato = 'vivo'
            """, (partita_id, session['player_id']))

            for lupo in cursor.fetchall():
                altri_lupi.append({
                    'id': lupo[0],
                    'nome': lupo[1],
                    'foto_profilo': lupo[2]
                })

        # Controlla se ha già fatto azione in questo turno
        ha_fatto_azione = False
        if (fase == 'night' and azione_notturna) or (fase == 'day' and azione_diurna):
            cursor.execute("""
                SELECT id FROM lupus_azioni
                WHERE partita_id = %s AND turno = %s AND giocatore_id = %s
                AND fase = %s
            """, (partita_id, turno, session['player_id'], fase))
            ha_fatto_azione = cursor.fetchone() is not None

        # Controlla se ha già votato
        ha_votato = False
        if fase == 'voting':
            cursor.execute("""
                SELECT id FROM lupus_votazioni
                WHERE partita_id = %s AND turno = %s AND votante_giocatore_id = %s
            """, (partita_id, turno, session['player_id']))
            ha_votato = cursor.fetchone() is not None

        return jsonify({
            'in_game': True,
            'partita_id': partita_id,
            'fase_corrente': fase,
            'turno': turno,
            'tempo_rimanente': int(time_remaining),
            'ruolo': {
                'id': ruolo_id,
                'nome': ruolo_nome,
                'emoji': emoji,
                'team': team,
                'descrizione': descrizione,
                'azione_notturna': bool(azione_notturna),
                'azione_diurna': bool(azione_diurna)
            },
            'stato_player': stato_player,
            'altri_giocatori': altri_giocatori,
            'altri_lupi': altri_lupi,
            'ha_fatto_azione': ha_fatto_azione,
            'ha_votato': ha_votato
        })

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/api/lupus-action', methods=['POST'])
def submit_lupus_action():
    """Invia azione notturna/diurna"""
    if 'player_id' not in session:
        return jsonify({'error': 'Non autorizzato'})

    data = request.get_json()
    action_type = data.get('action_type')  # 'kill', 'protect', 'investigate'
    target_id = data.get('target_id')

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Trova partita e verifica partecipazione
        cursor.execute("""
            SELECT lpt.id, lpt.fase_corrente, lpt.turno_numero, lr.nome, lr.team
            FROM lupus_partite lpt
            JOIN lupus_partecipazioni lp ON lpt.id = lp.partita_id
            JOIN lupus_ruoli lr ON lp.ruolo_id = lr.id
            WHERE lpt.stato != 'ended' AND lp.giocatore_id = %s AND lp.stato = 'vivo'
            ORDER BY lpt.id DESC LIMIT 1
        """, (session['player_id'],))

        result = cursor.fetchone()
        if not result:
            return jsonify({'error': 'Non sei in una partita attiva o sei morto'})

        partita_id, fase, turno, ruolo_nome, team = result

        # Verifica che l'azione sia appropriata per la fase
        if fase not in ['night', 'day']:
            return jsonify({'error': 'Non puoi fare azioni in questa fase'})

        # Verifica autorizzazioni per tipo azione
        action_permissions = {
            'kill': lambda: team == 'lupi' and fase == 'night',
            'protect': lambda: ruolo_nome == 'Guardia' and fase == 'night',
            'investigate': lambda: ruolo_nome == 'Veggente' and fase == 'night'
        }

        if action_type not in action_permissions or not action_permissions[action_type]():
            return jsonify({'error': 'Non puoi fare questa azione'})

        # Verifica che non abbia già fatto un'azione questo turno
        cursor.execute("""
            SELECT id FROM lupus_azioni
            WHERE partita_id = %s AND turno = %s AND giocatore_id = %s AND fase = %s
        """, (partita_id, turno, session['player_id'], fase))

        if cursor.fetchone():
            return jsonify({'error': 'Hai già fatto un\'azione questo turno'})

        # Verifica che il target sia valido
        cursor.execute("""
            SELECT stato FROM lupus_partecipazioni
            WHERE partita_id = %s AND giocatore_id = %s
        """, (partita_id, target_id))

        target_status = cursor.fetchone()
        if not target_status or target_status[0] != 'vivo':
            return jsonify({'error': 'Target non valido'})

        # Salva azione
        cursor.execute("""
            INSERT INTO lupus_azioni (partita_id, turno, fase, giocatore_id, tipo_azione, target_giocatore_id)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (partita_id, turno, fase, session['player_id'], action_type, target_id))

        conn.commit()

        return jsonify({'success': True, 'message': 'Azione registrata'})

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/api/lupus-vote', methods=['POST'])
def submit_lupus_vote():
    """Invia voto per eliminazione diurna"""
    if 'player_id' not in session:
        return jsonify({'error': 'Non autorizzato'})

    data = request.get_json()
    target_id = data.get('target_id')

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Trova partita e verifica stato
        cursor.execute("""
            SELECT lpt.id, lpt.fase_corrente, lpt.turno_numero, lr.nome
            FROM lupus_partite lpt
            JOIN lupus_partecipazioni lp ON lpt.id = lp.partita_id
            JOIN lupus_ruoli lr ON lp.ruolo_id = lr.id
            WHERE lpt.stato != 'ended' AND lp.giocatore_id = %s AND lp.stato = 'vivo'
            ORDER BY lpt.id DESC LIMIT 1
        """, (session['player_id'],))

        result = cursor.fetchone()
        if not result:
            return jsonify({'error': 'Non puoi votare'})

        partita_id, fase, turno, ruolo_nome = result

        if fase != 'voting':
            return jsonify({'error': 'Non è il momento di votare'})

        # Verifica che non abbia già votato
        cursor.execute("""
            SELECT id FROM lupus_votazioni
            WHERE partita_id = %s AND turno = %s AND votante_giocatore_id = %s
        """, (partita_id, turno, session['player_id']))

        if cursor.fetchone():
            return jsonify({'error': 'Hai già votato'})

        # Determina peso del voto
        peso_voto = 2 if ruolo_nome in ['Sindaco', 'Festeggiato'] else 1

        # Salva voto
        cursor.execute("""
            INSERT INTO lupus_votazioni (partita_id, turno, votante_giocatore_id, votato_giocatore_id, peso_voto)
            VALUES (%s, %s, %s, %s, %s)
        """, (partita_id, turno, session['player_id'], target_id, peso_voto))

        conn.commit()

        return jsonify({'success': True, 'peso_voto': peso_voto})

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()





if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')