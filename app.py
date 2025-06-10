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

        if len(available_players) < 1:
            return jsonify({'error': 'Servono almeno 1 giocatori per Lupus'})

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
        total_players_needed = 1
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


# Aggiungi queste funzioni al tuo app.py per il sistema Lupus migliorato

import random
import json
from datetime import datetime, timedelta


def get_optimal_lupus_config(num_real_players):
    """Determina la configurazione ottimale in base al numero di giocatori reali"""

    # Se ci sono abbastanza giocatori reali, usa solo quelli
    if num_real_players >= 6:
        # Trova la configurazione più adatta
        configs = {
            (6, 7): {"Lupo": 1, "Veggente": 1, "Guardia": 1, "Cittadino": 4},
            (8, 10): {"Lupo": 2, "Veggente": 1, "Guardia": 1, "Sindaco": 1, "Cittadino": 5},
            (11, 16): {"Lupo": 3, "Lupo Alpha": 1, "Veggente": 1, "Guardia": 1, "Medico": 1, "Sindaco": 1,
                       "Cacciatore": 1, "Cittadino": 6},
            (17, 25): {"Lupo": 4, "Lupo Alpha": 1, "Veggente": 1, "Guardia": 1, "Medico": 1, "Sindaco": 1,
                       "Cacciatore": 1, "Strega": 1, "Cittadino": 14},
            (26, 40): {"Lupo": 6, "Lupo Alpha": 1, "Veggente": 2, "Guardia": 2, "Medico": 1, "Sindaco": 1,
                       "Cacciatore": 1, "Strega": 1, "Cupido": 1, "Cittadino": 24}
        }

        for (min_p, max_p), config in configs.items():
            if min_p <= num_real_players <= max_p:
                # Aggiusta la configurazione per il numero esatto
                total_roles = sum(config.values())
                if total_roles > num_real_players:
                    # Riduci cittadini
                    config["Cittadino"] = max(1, config["Cittadino"] - (total_roles - num_real_players))
                elif total_roles < num_real_players:
                    # Aggiungi cittadini
                    config["Cittadino"] += (num_real_players - total_roles)

                return config, 0  # 0 bot necessari

    # Se ci sono pochi giocatori reali, aggiungi bot per arrivare a 6-8
    else:
        target_players = max(6, num_real_players + 2)  # Almeno 6, o +2 rispetto ai reali
        bots_needed = target_players - num_real_players

        config = {"Lupo": 1, "Veggente": 1, "Guardia": 1, "Cittadino": target_players - 3}
        if target_players >= 8:
            config["Lupo"] = 2
            config["Cittadino"] = target_players - 4

        return config, bots_needed


def create_bot_players(num_bots_needed):
    """Crea giocatori bot temporanei per la partita"""

    bot_names = [
        "🤖 Bot Marco", "🤖 Bot Laura", "🤖 Bot Giuseppe", "🤖 Bot Anna",
        "🤖 Bot Francesco", "🤖 Bot Maria", "🤖 Bot Luigi", "🤖 Bot Sara",
        "🤖 Bot Antonio", "🤖 Bot Elena", "🤖 Bot Roberto", "🤖 Bot Giulia",
        "🤖 Bot Alessandro", "🤖 Bot Chiara", "🤖 Bot Matteo", "🤖 Bot Federica"
    ]

    bot_players = []
    for i in range(min(num_bots_needed, len(bot_names))):
        bot_players.append({
            'id': f'bot_{i}',  # ID temporaneo per bot
            'nome': bot_names[i],
            'is_bot': True,
            'personalita': random.choice(['aggressivo', 'difensivo', 'casuale', 'intelligente'])
        })

    return bot_players


def simulate_bot_action(bot_player, game_state, action_type):
    """Simula l'azione di un bot in base alla sua personalità"""

    personalita = bot_player.get('personalita', 'casuale')
    alive_players = [p for p in game_state['players'] if p['stato'] == 'vivo' and p['id'] != bot_player['id']]

    if not alive_players:
        return None

    if action_type == 'vote':
        # Logica di voto del bot
        if personalita == 'intelligente':
            # Vota il giocatore più sospetto (casualità pesata)
            return random.choices(alive_players, weights=[0.3 if p.get('is_bot') else 0.7 for p in alive_players])[0][
                'id']
        elif personalita == 'aggressivo':
            # Vota sempre giocatori umani se possibile
            human_players = [p for p in alive_players if not p.get('is_bot')]
            return random.choice(human_players if human_players else alive_players)['id']
        elif personalita == 'difensivo':
            # Vota più cautamente, spesso si astiene o vota bot
            bot_players = [p for p in alive_players if p.get('is_bot')]
            return random.choice(bot_players if bot_players else alive_players)['id']
        else:  # casuale
            return random.choice(alive_players)['id']

    elif action_type == 'kill':  # Per lupi bot
        if personalita == 'intelligente':
            # Preferisce giocatori umani con ruoli speciali
            human_players = [p for p in alive_players if not p.get('is_bot')]
            return random.choice(human_players if human_players else alive_players)['id']
        else:
            return random.choice(alive_players)['id']

    elif action_type == 'protect':  # Per guardia bot
        if personalita == 'intelligente':
            # Protegge giocatori importanti (preferibilmente umani)
            human_players = [p for p in alive_players if not p.get('is_bot')]
            return random.choice(human_players if human_players else alive_players)['id']
        else:
            return random.choice(alive_players)['id']

    elif action_type == 'investigate':  # Per veggente bot
        # Investiga giocatori sospetti
        return random.choice(alive_players)['id']

    return None


# Aggiorna la funzione assign_lupus_roles per gestire i bot
def assign_lupus_roles_with_bots(cursor, partita_id, real_players, bot_players, ruoli_config):
    """Assegna ruoli a giocatori reali e bot"""

    # Ottieni tutti i ruoli disponibili
    cursor.execute("SELECT id, nome FROM lupus_ruoli WHERE attivo = TRUE")
    all_roles = {nome: role_id for role_id, nome in cursor.fetchall()}

    # Crea lista di ruoli da assegnare
    roles_to_assign = []
    for role_name, count in ruoli_config.items():
        if role_name in all_roles:
            roles_to_assign.extend([all_roles[role_name]] * count)

    # Combina giocatori reali e bot
    all_players = list(real_players) + bot_players

    # Mescola giocatori e ruoli
    random.shuffle(all_players)
    random.shuffle(roles_to_assign)

    # Assegna ruoli
    assigned = []
    for i, player in enumerate(all_players[:len(roles_to_assign)]):
        role_id = roles_to_assign[i]

        if isinstance(player, dict) and player.get('is_bot'):
            # Per bot, crea un giocatore temporaneo
            cursor.execute("""
                INSERT INTO giocatori (nome, squadra, personaggio_id, punti_totali, escluso_da_gioco)
                VALUES (%s, 'Rossi', 1, 0, FALSE)
            """, (player['nome'],))

            bot_player_id = cursor.lastrowid

            cursor.execute("""
                INSERT INTO lupus_partecipazioni (partita_id, giocatore_id, ruolo_id, simulato)
                VALUES (%s, %s, %s, TRUE)
            """, (partita_id, bot_player_id, role_id))

            # Salva info bot per simulazioni
            cursor.execute("""
                INSERT INTO lupus_bots (nome, personalita, attivo) 
                VALUES (%s, %s, TRUE)
                ON DUPLICATE KEY UPDATE personalita = %s
            """, (player['nome'], player['personalita'], player['personalita']))

        else:
            # Giocatore reale
            player_id = player[0] if isinstance(player, tuple) else player
            cursor.execute("""
                INSERT INTO lupus_partecipazioni (partita_id, giocatore_id, ruolo_id, simulato)
                VALUES (%s, %s, %s, FALSE)
            """, (partita_id, player_id, role_id))

        # Ottieni nome ruolo per risposta
        cursor.execute("SELECT nome FROM lupus_ruoli WHERE id = %s", (role_id,))
        role_name = cursor.fetchone()[0]

        player_name = player['nome'] if isinstance(player, dict) else player[1]
        assigned.append({
            'player_name': player_name,
            'role_name': role_name,
            'is_bot': isinstance(player, dict) and player.get('is_bot', False)
        })

    return assigned


# Funzione per processare azioni bot automaticamente
def process_bot_actions_for_phase(cursor, partita_id, turno, fase):
    """Processa automaticamente le azioni dei bot per una fase"""

    # Ottieni bot attivi nella partita
    cursor.execute("""
        SELECT lp.giocatore_id, g.nome, lr.nome as ruolo, lr.team, lr.azione_notturna, lr.azione_diurna
        FROM lupus_partecipazioni lp
        JOIN giocatori g ON lp.giocatore_id = g.id
        JOIN lupus_ruoli lr ON lp.ruolo_id = lr.id
        WHERE lp.partita_id = %s AND lp.simulato = TRUE AND lp.stato = 'vivo'
    """, (partita_id,))

    bots = cursor.fetchall()

    # Ottieni stato del gioco per le decisioni bot
    cursor.execute("""
        SELECT lp.giocatore_id, g.nome, lp.stato
        FROM lupus_partecipazioni lp
        JOIN giocatori g ON lp.giocatore_id = g.id
        WHERE lp.partita_id = %s
    """, (partita_id,))

    all_players = [{'id': p[0], 'nome': p[1], 'stato': p[2], 'is_bot': False} for p in cursor.fetchall()]

    # Aggiorna info sui bot
    for player in all_players:
        for bot in bots:
            if player['id'] == bot[0]:
                player['is_bot'] = True
                break

    game_state = {'players': all_players}

    for bot_id, bot_name, ruolo, team, azione_notturna, azione_diurna in bots:

        # Determina che azione fare
        action_to_take = None

        if fase == 'night' and azione_notturna:
            if team == 'lupi':
                action_to_take = 'kill'
            elif ruolo == 'Veggente':
                action_to_take = 'investigate'
            elif ruolo == 'Guardia':
                action_to_take = 'protect'

        elif fase == 'voting':
            action_to_take = 'vote'

        if action_to_take:
            # Simula l'azione
            bot_player = {'id': bot_id, 'nome': bot_name, 'personalita': 'casuale'}  # Default personalità

            # Ottieni personalità del bot se disponibile
            cursor.execute("SELECT personalita FROM lupus_bots WHERE nome = %s", (bot_name,))
            personalita_result = cursor.fetchone()
            if personalita_result:
                bot_player['personalita'] = personalita_result[0]

            target_id = simulate_bot_action(bot_player, game_state, action_to_take)

            if target_id and action_to_take == 'vote':
                # Salva voto bot
                cursor.execute("""
                    INSERT IGNORE INTO lupus_votazioni (partita_id, turno, votante_giocatore_id, votato_giocatore_id, peso_voto)
                    VALUES (%s, %s, %s, %s, 1)
                """, (partita_id, turno, bot_id, target_id))

            elif target_id and action_to_take in ['kill', 'investigate', 'protect']:
                # Salva azione notturna bot
                cursor.execute("""
                    INSERT IGNORE INTO lupus_azioni (partita_id, turno, fase, giocatore_id, tipo_azione, target_giocatore_id)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (partita_id, turno, fase, bot_id, action_to_take, target_id))


# Aggiorna la route per start lupus game
@app.route('/api/gamemaster/lupus-start-flexible', methods=['POST'])
def start_flexible_lupus_game():
    """Avvia Lupus con supporto per bot e gruppi di qualsiasi dimensione"""
    if not session.get('is_gamemaster'):
        return jsonify({'error': 'Non autorizzato'}), 403

    data = request.get_json()
    use_bots = data.get('use_bots', True)  # Default: usa bot se necessario
    force_config = data.get('force_config')  # Configurazione forzata

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Ottieni giocatori reali disponibili
        cursor.execute("""
            SELECT id, nome FROM giocatori 
            WHERE (escluso_da_gioco != TRUE OR escluso_da_gioco IS NULL)
            ORDER BY punti_totali DESC
        """)
        real_players = cursor.fetchall()
        num_real_players = len(real_players)

        if num_real_players < 3:
            return jsonify({'error': 'Servono almeno 3 giocatori per Lupus (anche con bot)'})

        # Determina configurazione
        if force_config:
            ruoli_config = force_config
            bots_needed = 0
        else:
            ruoli_config, bots_needed = get_optimal_lupus_config(num_real_players)
            if not use_bots:
                bots_needed = 0

        # Crea bot se necessario
        bot_players = []
        if bots_needed > 0:
            bot_players = create_bot_players(bots_needed)

        total_players = num_real_players + len(bot_players)

        # Termina eventuali partite attive
        cursor.execute("UPDATE lupus_partite SET stato = 'ended' WHERE stato != 'ended'")

        # Crea nuova partita
        cursor.execute("""
            INSERT INTO lupus_partite (stato, fase_corrente, durata_fase_secondi)
            VALUES ('waiting', 'setup', 120)
        """)
        partita_id = cursor.lastrowid

        # Assegna ruoli
        assigned_roles = assign_lupus_roles_with_bots(cursor, partita_id, real_players, bot_players, ruoli_config)

        # Aggiorna stato gioco globale
        cursor.execute("""
            INSERT INTO stato_gioco (id, gioco_attivo, messaggio, ultimo_aggiornamento) 
            VALUES (1, 'lupus_in_fabula', 'Lupus in Fabula sta per iniziare! 🐺', NOW()) 
            ON DUPLICATE KEY UPDATE 
            gioco_attivo = 'lupus_in_fabula', 
            messaggio = 'Lupus in Fabula sta per iniziare! 🐺', 
            ultimo_aggiornamento = NOW()
        """)

        # Log partita iniziata
        cursor.execute("""
            INSERT INTO lupus_eventi (partita_id, turno, fase, tipo_evento, descrizione)
            VALUES (%s, 1, 'setup', 'partita_iniziata', %s)
        """, (partita_id, f'Partita iniziata con {num_real_players} giocatori reali e {len(bot_players)} bot'))

        conn.commit()

        return jsonify({
            'success': True,
            'partita_id': partita_id,
            'giocatori_reali': num_real_players,
            'bot_aggiunti': len(bot_players),
            'giocatori_totali': total_players,
            'ruoli_assegnati': assigned_roles,
            'configurazione': ruoli_config
        })

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


# Funzione per cleanup bot alla fine della partita
def cleanup_bot_players(cursor, partita_id):
    """Rimuove i giocatori bot temporanei alla fine della partita"""

    # Trova giocatori bot di questa partita
    cursor.execute("""
        SELECT g.id FROM giocatori g
        JOIN lupus_partecipazioni lp ON g.id = lp.giocatore_id
        WHERE lp.partita_id = %s AND lp.simulato = TRUE AND g.nome LIKE '🤖 Bot%'
    """, (partita_id,))

    bot_ids = [row[0] for row in cursor.fetchall()]

    # Rimuovi bot giocatori (le partecipazioni verranno eliminate per CASCADE)
    for bot_id in bot_ids:
        cursor.execute("DELETE FROM giocatori WHERE id = %s", (bot_id,))


# Aggiungi route per gestione automatica fasi con bot
@app.route('/api/gamemaster/lupus-auto-phase', methods=['POST'])
def auto_manage_lupus_phase():
    """Gestione automatica delle fasi con azioni bot"""
    if not session.get('is_gamemaster'):
        return jsonify({'error': 'Non autorizzato'}), 403

    data = request.get_json()
    new_phase = data.get('phase')

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

        # Processa azioni bot per la fase corrente prima di cambiarla
        if current_phase in ['night', 'voting']:
            process_bot_actions_for_phase(cursor, partita_id, turno, current_phase)

        # Processa risultati fase corrente
        if current_phase == 'night':
            process_night_actions(cursor, partita_id, turno)
        elif current_phase == 'voting':
            process_voting_results(cursor, partita_id, turno)

        # Cambia fase (usa la logica esistente)
        phase_durations = {'night': 120, 'day': 180, 'voting': 90}
        duration = phase_durations.get(new_phase, 60)

        if current_phase == 'voting' and new_phase == 'night':
            turno += 1

        cursor.execute("""
            UPDATE lupus_partite 
            SET fase_corrente = %s, tempo_fase_inizio = NOW(), 
                durata_fase_secondi = %s, turno_numero = %s
            WHERE id = %s
        """, (new_phase, duration, turno, partita_id))

        # Se la partita finisce, cleanup bot
        if new_phase == 'ended':
            cleanup_bot_players(cursor, partita_id)

        conn.commit()

        return jsonify({
            'success': True,
            'new_phase': new_phase,
            'turno': turno,
            'bot_actions_processed': True
        })

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


# Aggiungi queste route al file app.py esistente

# Route per la pagina dedicata del gamemaster Lupus
@app.route('/gamemaster/lupus')
def lupus_gamemaster_page():
    """Pagina dedicata gestione Lupus in Fabula"""
    if not session.get('is_gamemaster'):
        return redirect(url_for('gamemaster'))

    return render_template('lupus_gamemaster.html')


# API per azioni di un turno specifico
@app.route('/api/gamemaster/lupus-actions/<int:partita_id>/<int:turno>')
def get_lupus_actions(partita_id, turno):
    """Ottieni tutte le azioni di un turno specifico"""
    if not session.get('is_gamemaster'):
        return jsonify({'error': 'Non autorizzato'}), 403

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT la.tipo_azione, la.risultato, la.successo, la.timestamp,
                   g1.nome as giocatore_nome, lr1.nome as ruolo,
                   g2.nome as target_nome
            FROM lupus_azioni la
            JOIN lupus_partecipazioni lp1 ON la.giocatore_id = lp1.giocatore_id
            JOIN giocatori g1 ON la.giocatore_id = g1.id
            JOIN lupus_ruoli lr1 ON lp1.ruolo_id = lr1.id
            LEFT JOIN giocatori g2 ON la.target_giocatore_id = g2.id
            WHERE la.partita_id = %s AND la.turno = %s
            ORDER BY la.timestamp
        """, (partita_id, turno))

        actions = cursor.fetchall()

        actions_list = []
        for action in actions:
            actions_list.append({
                'tipo_azione': action[0],
                'risultato': action[1],
                'successo': bool(action[2]),
                'timestamp': action[3].isoformat() if action[3] else None,
                'giocatore_nome': action[4],
                'ruolo': action[5],
                'target_nome': action[6]
            })

        return jsonify(actions_list)

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


# API per voti di un turno specifico
@app.route('/api/gamemaster/lupus-votes/<int:partita_id>/<int:turno>')
def get_lupus_votes(partita_id, turno):
    """Ottieni tutti i voti di un turno specifico"""
    if not session.get('is_gamemaster'):
        return jsonify({'error': 'Non autorizzato'}), 403

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT lv.peso_voto, lv.timestamp,
                   g1.nome as votante_nome,
                   g2.nome as votato_nome
            FROM lupus_votazioni lv
            JOIN giocatori g1 ON lv.votante_giocatore_id = g1.id
            JOIN giocatori g2 ON lv.votato_giocatore_id = g2.id
            WHERE lv.partita_id = %s AND lv.turno = %s
            ORDER BY lv.timestamp
        """, (partita_id, turno))

        votes = cursor.fetchall()

        votes_list = []
        for vote in votes:
            votes_list.append({
                'peso_voto': vote[0],
                'timestamp': vote[1].isoformat() if vote[1] else None,
                'votante_nome': vote[2],
                'votato_nome': vote[3]
            })

        return jsonify(votes_list)

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


# API per eventi di una partita
@app.route('/api/gamemaster/lupus-events/<int:partita_id>')
def get_lupus_events(partita_id):
    """Ottieni eventi di una partita"""
    if not session.get('is_gamemaster'):
        return jsonify({'error': 'Non autorizzato'}), 403

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT le.turno, le.fase, le.tipo_evento, le.descrizione, 
                   le.giocatori_coinvolti, le.timestamp
            FROM lupus_eventi le
            WHERE le.partita_id = %s
            ORDER BY le.timestamp DESC
            LIMIT 50
        """, (partita_id,))

        events = cursor.fetchall()

        events_list = []
        for event in events:
            events_list.append({
                'turno': event[0],
                'fase': event[1],
                'tipo_evento': event[2],
                'descrizione': event[3],
                'giocatori_coinvolti': json.loads(event[4]) if event[4] else [],
                'timestamp': event[5].isoformat() if event[5] else None
            })

        return jsonify(events_list)

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


# API per azioni manuali sui giocatori
@app.route('/api/gamemaster/lupus-player-action', methods=['POST'])
def lupus_player_action():
    """Esegui azione manuale su un giocatore"""
    if not session.get('is_gamemaster'):
        return jsonify({'error': 'Non autorizzato'}), 403

    data = request.get_json()
    player_id = data.get('player_id')
    action = data.get('action')  # 'kill', 'revive'

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Trova partita attiva e partecipazione del giocatore
        cursor.execute("""
            SELECT lpt.id, lpt.turno_numero, lp.stato, g.nome
            FROM lupus_partite lpt
            JOIN lupus_partecipazioni lp ON lpt.id = lp.partita_id
            JOIN giocatori g ON lp.giocatore_id = g.id
            WHERE lpt.stato != 'ended' AND lp.giocatore_id = %s
            ORDER BY lpt.id DESC LIMIT 1
        """, (player_id,))

        result = cursor.fetchone()
        if not result:
            return jsonify({'error': 'Giocatore non trovato nella partita'})

        partita_id, turno, stato_attuale, nome_giocatore = result

        if action == 'kill' and stato_attuale == 'vivo':
            # Elimina giocatore
            cursor.execute("""
                UPDATE lupus_partecipazioni 
                SET stato = 'morto', morte_turno = %s, morte_fase = 'gamemaster'
                WHERE partita_id = %s AND giocatore_id = %s
            """, (turno, partita_id, player_id))

            # Log evento
            cursor.execute("""
                INSERT INTO lupus_eventi (partita_id, turno, fase, tipo_evento, descrizione, giocatori_coinvolti)
                VALUES (%s, %s, 'gamemaster', 'eliminazione_manuale', %s, %s)
            """, (partita_id, turno, f'Giocatore {nome_giocatore} eliminato manualmente dal gamemaster',
                  json.dumps([player_id])))

            message = f'Giocatore {nome_giocatore} eliminato'

        elif action == 'revive' and stato_attuale != 'vivo':
            # Riporta in vita giocatore
            cursor.execute("""
                UPDATE lupus_partecipazioni 
                SET stato = 'vivo', morte_turno = NULL, morte_fase = NULL
                WHERE partita_id = %s AND giocatore_id = %s
            """, (partita_id, player_id))

            # Log evento
            cursor.execute("""
                INSERT INTO lupus_eventi (partita_id, turno, fase, tipo_evento, descrizione, giocatori_coinvolti)
                VALUES (%s, %s, 'gamemaster', 'resurrezione_manuale', %s, %s)
            """, (
            partita_id, turno, f'Giocatore {nome_giocatore} riportato in vita dal gamemaster', json.dumps([player_id])))

            message = f'Giocatore {nome_giocatore} riportato in vita'

        else:
            return jsonify({'error': f'Azione non valida: {action} per stato {stato_attuale}'})

        conn.commit()
        return jsonify({'success': True, 'message': message})

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


# Funzioni utility per la gestione di Lupus in Fabula
def log_lupus_event(partita_id, turno, fase, tipo_evento, descrizione, giocatori_coinvolti=None):
    """Log di un evento nella partita"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO lupus_eventi (partita_id, turno, fase, tipo_evento, descrizione, giocatori_coinvolti)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (partita_id, turno, fase, tipo_evento, descrizione,
              json.dumps(giocatori_coinvolti) if giocatori_coinvolti else None))
        conn.commit()
    except Exception as e:
        print(f"Errore log evento: {e}")
    finally:
        cursor.close()
        conn.close()


def check_lupus_win_conditions(partita_id):
    """Controlla le condizioni di vittoria"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Conta giocatori vivi per team
        cursor.execute("""
            SELECT lr.team, COUNT(*) as count
            FROM lupus_partecipazioni lp
            JOIN lupus_ruoli lr ON lp.ruolo_id = lr.id
            WHERE lp.partita_id = %s AND lp.stato = 'vivo'
            GROUP BY lr.team
        """, (partita_id,))

        team_counts = dict(cursor.fetchall())
        lupi_vivi = team_counts.get('lupi', 0)
        cittadini_vivi = team_counts.get('cittadini', 0)

        # Vittoria lupi: lupi >= cittadini
        if lupi_vivi > 0 and lupi_vivi >= cittadini_vivi:
            return 'lupi'

        # Vittoria cittadini: nessun lupo vivo
        if lupi_vivi == 0:
            return 'cittadini'

        return None

    except Exception as e:
        print(f"Errore controllo vittoria: {e}")
        return None
    finally:
        cursor.close()
        conn.close()


def update_lupus_phase_timer(partita_id, fase, durata_minuti=None):
    """Aggiorna il timer della fase corrente con durate più veloci"""

    # Durate ottimizzate per velocità
    durate_veloci = {
        'night': 1.5,  # 90 secondi per azioni notturne
        'day': 2.0,  # 2 minuti per discussione
        'voting': 1.0,  # 60 secondi per votare
        'setup': 0.5  # 30 secondi per preparazione
    }

    if durata_minuti is None:
        durata_minuti = durate_veloci.get(fase, 2.0)

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        fine_fase = datetime.now() + timedelta(minutes=durata_minuti)
        cursor.execute("""
            UPDATE lupus_partite 
            SET fase_corrente = %s, fine_fase = %s, ultimo_aggiornamento = NOW()
            WHERE id = %s
        """, (fase, fine_fase, partita_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Errore aggiornamento timer: {e}")
        return False
    finally:
        cursor.close()
        conn.close()


# Aggiungi queste tabelle al database (script SQL da eseguire)
def create_lupus_tables():
    """Crea le tabelle necessarie per Lupus in Fabula"""

    lupus_tables_sql = """
    -- Tabella configurazioni di gioco
    CREATE TABLE IF NOT EXISTS lupus_configurazioni (
        id INT AUTO_INCREMENT PRIMARY KEY,
        nome VARCHAR(100) NOT NULL,
        descrizione TEXT,
        min_giocatori INT DEFAULT 5,
        max_giocatori INT DEFAULT 15,
        durata_notte INT DEFAULT 120, -- secondi
        durata_giorno INT DEFAULT 300,
        durata_votazione INT DEFAULT 180,
        ruoli_disponibili JSON, -- lista ruoli con quantità
        regole_speciali JSON,
        attiva BOOLEAN DEFAULT TRUE,
        creata_il TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Tabella ruoli disponibili
    CREATE TABLE IF NOT EXISTS lupus_ruoli (
        id INT AUTO_INCREMENT PRIMARY KEY,
        nome VARCHAR(50) NOT NULL UNIQUE,
        descrizione TEXT,
        team ENUM('lupi', 'cittadini', 'neutral') NOT NULL,
        abilita_speciali JSON,
        priorita_azione INT DEFAULT 0,
        attivo BOOLEAN DEFAULT TRUE
    );

    -- Tabella partite Lupus
    CREATE TABLE IF NOT EXISTS lupus_partite (
        id INT AUTO_INCREMENT PRIMARY KEY,
        configurazione_id INT,
        stato ENUM('setup', 'active', 'paused', 'ended') DEFAULT 'setup',
        fase_corrente ENUM('setup', 'night', 'day', 'voting', 'ended') DEFAULT 'setup',
        turno_numero INT DEFAULT 1,
        inizio_partita TIMESTAMP NULL,
        fine_partita TIMESTAMP NULL,
        fine_fase TIMESTAMP NULL,
        squadra_vincente VARCHAR(50) NULL,
        ultimo_aggiornamento TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        FOREIGN KEY (configurazione_id) REFERENCES lupus_configurazioni(id)
    );

    -- Tabella partecipazioni
    CREATE TABLE IF NOT EXISTS lupus_partecipazioni (
        id INT AUTO_INCREMENT PRIMARY KEY,
        partita_id INT NOT NULL,
        giocatore_id INT NOT NULL,
        ruolo_id INT NOT NULL,
        stato ENUM('vivo', 'morto', 'eliminato') DEFAULT 'vivo',
        morte_turno INT NULL,
        morte_fase VARCHAR(20) NULL,
        note_private TEXT,
        FOREIGN KEY (partita_id) REFERENCES lupus_partite(id) ON DELETE CASCADE,
        FOREIGN KEY (giocatore_id) REFERENCES giocatori(id),
        FOREIGN KEY (ruolo_id) REFERENCES lupus_ruoli(id),
        UNIQUE KEY unique_participation (partita_id, giocatore_id)
    );

    -- Tabella azioni dei giocatori
    CREATE TABLE IF NOT EXISTS lupus_azioni (
        id INT AUTO_INCREMENT PRIMARY KEY,
        partita_id INT NOT NULL,
        giocatore_id INT NOT NULL,
        turno INT NOT NULL,
        fase ENUM('night', 'day', 'voting') NOT NULL,
        tipo_azione VARCHAR(50) NOT NULL,
        target_giocatore_id INT NULL,
        parametri_extra JSON,
        risultato TEXT,
        successo BOOLEAN DEFAULT FALSE,
        processata BOOLEAN DEFAULT FALSE,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (partita_id) REFERENCES lupus_partite(id) ON DELETE CASCADE,
        FOREIGN KEY (giocatore_id) REFERENCES giocatori(id),
        FOREIGN KEY (target_giocatore_id) REFERENCES giocatori(id)
    );

    -- Tabella votazioni
    CREATE TABLE IF NOT EXISTS lupus_votazioni (
        id INT AUTO_INCREMENT PRIMARY KEY,
        partita_id INT NOT NULL,
        turno INT NOT NULL,
        votante_giocatore_id INT NOT NULL,
        votato_giocatore_id INT NOT NULL,
        peso_voto INT DEFAULT 1,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (partita_id) REFERENCES lupus_partite(id) ON DELETE CASCADE,
        FOREIGN KEY (votante_giocatore_id) REFERENCES giocatori(id),
        FOREIGN KEY (votato_giocatore_id) REFERENCES giocatori(id),
        UNIQUE KEY unique_vote (partita_id, turno, votante_giocatore_id)
    );

    -- Tabella eventi/log
    CREATE TABLE IF NOT EXISTS lupus_eventi (
        id INT AUTO_INCREMENT PRIMARY KEY,
        partita_id INT NOT NULL,
        turno INT NOT NULL,
        fase VARCHAR(20) NOT NULL,
        tipo_evento VARCHAR(50) NOT NULL,
        descrizione TEXT NOT NULL,
        giocatori_coinvolti JSON,
        metadati JSON,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (partita_id) REFERENCES lupus_partite(id) ON DELETE CASCADE
    );

    -- Inserimento ruoli base
    INSERT IGNORE INTO lupus_ruoli (nome, descrizione, team, abilita_speciali, priorita_azione) VALUES
    ('Lupo', 'Elimina un cittadino ogni notte', 'lupi', '{"azione_notte": "kill", "gruppo": true}', 1),
    ('Lupo Alpha', 'Lupo con poteri speciali', 'lupi', '{"azione_notte": "kill", "gruppo": true, "immunita_prima_notte": true}', 1),
    ('Cittadino', 'Ruolo base senza poteri speciali', 'cittadini', '{}', 0),
    ('Veggente', 'Può scoprire il ruolo di un giocatore ogni notte', 'cittadini', '{"azione_notte": "investigate"}', 2),
    ('Dottore', 'Può proteggere un giocatore ogni notte', 'cittadini', '{"azione_notte": "protect"}', 3),
    ('Guardia del Corpo', 'Protegge permanentemente un giocatore', 'cittadini', '{"azione_setup": "protect_permanent"}', 0),
    ('Detective', 'Ottiene informazioni sui morti', 'cittadini', '{"azione_giorno": "investigate_dead"}', 0),
    ('Cacciatore', 'Può eliminare qualcuno quando viene eliminato', 'cittadini', '{"azione_morte": "revenge_kill"}', 0),
    ('Sindaco', 'Il suo voto vale doppio', 'cittadini', '{"peso_voto": 2}', 0),
    ('Innamorati', 'Muoiono insieme', 'cittadini', '{"legame": "lovers"}', 0),
    ('Assassino', 'Può uccidere una volta per partita', 'neutral', '{"azione_speciale": "kill_once"}', 4),
    ('Jolly', 'Vince se sopravvive fino alla fine', 'neutral', '{"condizione_vittoria": "survivor"}', 0);

    -- Configurazioni predefinite
    INSERT IGNORE INTO lupus_configurazioni (nome, descrizione, min_giocatori, max_giocatori, ruoli_disponibili) VALUES
    ('Classica 5-8 giocatori', 'Configurazione base per piccoli gruppi', 5, 8, 
     '{"Lupo": 1, "Cittadino": 3, "Veggente": 1, "Dottore": 1}'),
    ('Standard 8-12 giocatori', 'Configurazione standard con più ruoli', 8, 12,
     '{"Lupo": 2, "Cittadino": 4, "Veggente": 1, "Dottore": 1, "Detective": 1, "Guardia del Corpo": 1}'),
    ('Avanzata 10-15 giocatori', 'Con ruoli speciali e neutral', 10, 15,
     '{"Lupo": 2, "Lupo Alpha": 1, "Cittadino": 5, "Veggente": 1, "Dottore": 1, "Detective": 1, "Cacciatore": 1, "Sindaco": 1, "Assassino": 1}'),
    ('Chaos Mode 12+ giocatori', 'Modalità con innamorati e molti ruoli', 12, 20,
     '{"Lupo": 3, "Lupo Alpha": 1, "Cittadino": 6, "Veggente": 1, "Dottore": 1, "Detective": 1, "Cacciatore": 1, "Sindaco": 1, "Innamorati": 2, "Assassino": 1, "Jolly": 1}');
    """

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Esegui ogni comando separatamente
        for statement in lupus_tables_sql.split(';'):
            statement = statement.strip()
            if statement:
                cursor.execute(statement)

        conn.commit()
        print("Tabelle Lupus in Fabula create con successo!")
        return True

    except mysql.connector.Error as err:
        print(f"Errore creazione tabelle: {err}")
        return False
    finally:
        cursor.close()
        conn.close()


# Route aggiuntive per gestione avanzata

@app.route('/api/gamemaster/lupus-advanced-action', methods=['POST'])
def lupus_advanced_action():
    """Azioni avanzate del gamemaster"""
    if not session.get('is_gamemaster'):
        return jsonify({'error': 'Non autorizzato'}), 403

    data = request.get_json()
    action_type = data.get('type')
    partita_id = data.get('partita_id')

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        if action_type == 'force_phase_end':
            # Forza fine fase corrente
            cursor.execute("""
                UPDATE lupus_partite 
                SET fine_fase = NOW()
                WHERE id = %s
            """, (partita_id,))

            message = 'Fase terminata forzatamente'

        elif action_type == 'extend_time':
            # Estendi tempo fase corrente
            cursor.execute("""
                UPDATE lupus_partite 
                SET fine_fase = DATE_ADD(fine_fase, INTERVAL 30 SECOND)
                WHERE id = %s
            """, (partita_id,))

            message = 'Tempo esteso di 30 secondi'

        elif action_type == 'reset_votes':
            # Reset voti turno corrente
            cursor.execute("""
                SELECT turno_numero FROM lupus_partite WHERE id = %s
            """, (partita_id,))
            turno = cursor.fetchone()[0]

            cursor.execute("""
                DELETE FROM lupus_votazioni 
                WHERE partita_id = %s AND turno = %s
            """, (partita_id, turno))

            message = 'Voti del turno corrente cancellati'

        elif action_type == 'pause_game':
            # Pausa partita
            cursor.execute("""
                UPDATE lupus_partite 
                SET stato = 'paused', fine_fase = NULL
                WHERE id = %s
            """, (partita_id,))

            message = 'Partita messa in pausa'

        elif action_type == 'resume_game':
            # Riprendi partita
            cursor.execute("""
                UPDATE lupus_partite 
                SET stato = 'active', fine_fase = DATE_ADD(NOW(), INTERVAL 5 MINUTE)
                WHERE id = %s
            """, (partita_id,))

            message = 'Partita ripresa'

        else:
            return jsonify({'error': 'Azione non riconosciuta'})

        conn.commit()
        return jsonify({'success': True, 'message': message})

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/api/gamemaster/lupus-stats/<int:partita_id>')
def get_lupus_stats(partita_id):
    """Statistiche dettagliate della partita"""
    if not session.get('is_gamemaster'):
        return jsonify({'error': 'Non autorizzato'}), 403

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Statistiche generali
        cursor.execute("""
            SELECT 
                COUNT(*) as totale_giocatori,
                SUM(CASE WHEN lp.stato = 'vivo' THEN 1 ELSE 0 END) as vivi,
                SUM(CASE WHEN lp.stato = 'morto' THEN 1 ELSE 0 END) as morti,
                SUM(CASE WHEN lr.team = 'lupi' AND lp.stato = 'vivo' THEN 1 ELSE 0 END) as lupi_vivi,
                SUM(CASE WHEN lr.team = 'cittadini' AND lp.stato = 'vivo' THEN 1 ELSE 0 END) as cittadini_vivi,
                SUM(CASE WHEN lr.team = 'neutral' AND lp.stato = 'vivo' THEN 1 ELSE 0 END) as neutral_vivi
            FROM lupus_partecipazioni lp
            JOIN lupus_ruoli lr ON lp.ruolo_id = lr.id
            WHERE lp.partita_id = %s
        """, (partita_id,))

        stats = cursor.fetchone()

        # Azioni per turno
        cursor.execute("""
            SELECT turno, COUNT(*) as azioni_count
            FROM lupus_azioni
            WHERE partita_id = %s
            GROUP BY turno
            ORDER BY turno
        """, (partita_id,))

        azioni_per_turno = dict(cursor.fetchall())

        # Morti per turno
        cursor.execute("""
            SELECT morte_turno, COUNT(*) as morti_count
            FROM lupus_partecipazioni
            WHERE partita_id = %s AND morte_turno IS NOT NULL
            GROUP BY morte_turno
            ORDER BY morte_turno
        """, (partita_id,))

        morti_per_turno = dict(cursor.fetchall())

        return jsonify({
            'totale_giocatori': stats[0],
            'giocatori_vivi': stats[1],
            'giocatori_morti': stats[2],
            'lupi_vivi': stats[3],
            'cittadini_vivi': stats[4],
            'neutral_vivi': stats[5],
            'azioni_per_turno': azioni_per_turno,
            'morti_per_turno': morti_per_turno
        })

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


# Aggiungi questa route al tuo app.py
# Aggiungi queste funzioni al tuo app.py per il sistema di punteggi Lupus

def calculate_lupus_points(partita_id, team_vincitore):
    """Calcola e assegna punti ai vincitori della partita Lupus"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Ottieni informazioni sulla partita
        cursor.execute("""
            SELECT turno_numero, created_at
            FROM lupus_partite 
            WHERE id = %s
        """, (partita_id,))

        partita_info = cursor.fetchone()
        if not partita_info:
            return False

        turno_finale, data_inizio = partita_info

        # Calcola durata partita in minuti
        durata_partita = (datetime.now() - data_inizio).total_seconds() / 60

        # Ottieni tutti i partecipanti con i loro ruoli
        cursor.execute("""
            SELECT lp.giocatore_id, g.nome, lr.nome as ruolo, lr.team, 
                   lp.stato, lp.morte_turno, lp.simulato
            FROM lupus_partecipazioni lp
            JOIN giocatori g ON lp.giocatore_id = g.id
            JOIN lupus_ruoli lr ON lp.ruolo_id = lr.id
            WHERE lp.partita_id = %s
        """, (partita_id,))

        partecipanti = cursor.fetchall()

        # Sistema di punteggi base
        punti_base = {
            'vittoria_base': 50,  # Punti base per la vittoria
            'sopravvivenza': 25,  # Punti per essere sopravvissuto
            'performance_lupo': 30,  # Bonus per lupi che eliminano molti
            'performance_cittadino': 20,  # Bonus per cittadini che scoprono lupi
            'partecipazione': 10,  # Punti base per aver partecipato
            'durata_bonus': 5  # Bonus per partite lunghe (per turno oltre il 3°)
        }

        # Calcola punti per ogni giocatore
        punteggi = []

        for giocatore_id, nome, ruolo, team, stato, morte_turno, is_bot in partecipanti:
            # Salta i bot per l'assegnazione punti
            if is_bot:
                continue

            punti_giocatore = 0
            dettaglio = []

            # Punti partecipazione base
            punti_giocatore += punti_base['partecipazione']
            dettaglio.append(f"Partecipazione: +{punti_base['partecipazione']}")

            # Punti vittoria team
            if team == team_vincitore:
                punti_giocatore += punti_base['vittoria_base']
                dettaglio.append(f"Vittoria {team}: +{punti_base['vittoria_base']}")

                # Bonus sopravvivenza per vincitori
                if stato == 'vivo':
                    punti_giocatore += punti_base['sopravvivenza']
                    dettaglio.append(f"Sopravvissuto: +{punti_base['sopravvivenza']}")

            # Bonus durata partita (per partite lunghe)
            if turno_finale > 3:
                bonus_durata = (turno_finale - 3) * punti_base['durata_bonus']
                punti_giocatore += bonus_durata
                dettaglio.append(f"Partita lunga ({turno_finale} turni): +{bonus_durata}")

            # Bonus specifici per ruolo
            punti_ruolo, dettaglio_ruolo = calculate_role_bonus(
                cursor, partita_id, giocatore_id, ruolo, team, team_vincitore
            )
            punti_giocatore += punti_ruolo
            dettaglio.extend(dettaglio_ruolo)

            # Salva il punteggio
            punteggi.append({
                'giocatore_id': giocatore_id,
                'nome': nome,
                'ruolo': ruolo,
                'team': team,
                'punti': punti_giocatore,
                'dettaglio': dettaglio
            })

            # Aggiorna i punti totali del giocatore
            cursor.execute("""
                UPDATE giocatori 
                SET punti_totali = punti_totali + %s 
                WHERE id = %s
            """, (punti_giocatore, giocatore_id))

            # Registra la partecipazione con punti
            cursor.execute("""
                INSERT INTO partecipazioni (giocatore_id, gioco, punti, timestamp, dettagli)
                VALUES (%s, 'lupus_in_fabula', %s, NOW(), %s)
            """, (giocatore_id, punti_giocatore, json.dumps({
                'ruolo': ruolo,
                'team': team,
                'vincitore': team == team_vincitore,
                'stato_finale': stato,
                'turni_giocati': turno_finale,
                'dettaglio_punti': dettaglio
            })))

        # Salva evento vittoria
        cursor.execute("""
            INSERT INTO lupus_eventi (partita_id, turno, fase, tipo_evento, descrizione, giocatori_coinvolti)
            VALUES (%s, %s, 'ended', 'victory', %s, %s)
        """, (partita_id, turno_finale,
              f'Vittoria del team {team_vincitore}! Punti assegnati ai giocatori.',
              json.dumps([p['giocatore_id'] for p in punteggi])))

        conn.commit()
        return punteggi

    except Exception as e:
        print(f"Errore calcolo punteggi: {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()


def calculate_role_bonus(cursor, partita_id, giocatore_id, ruolo, team, team_vincitore):
    """Calcola bonus specifici per ruolo"""
    punti_bonus = 0
    dettaglio = []

    try:
        if ruolo in ['Lupo', 'Lupo Alpha']:
            # Bonus per lupi: punti per ogni uccisione
            cursor.execute("""
                SELECT COUNT(*) FROM lupus_azioni 
                WHERE partita_id = %s AND giocatore_id = %s 
                AND tipo_azione = 'kill' AND successo = TRUE
            """, (partita_id, giocatore_id))

            uccisioni = cursor.fetchone()[0]
            if uccisioni > 0:
                bonus_kill = uccisioni * 15
                punti_bonus += bonus_kill
                dettaglio.append(f"Eliminazioni ({uccisioni}): +{bonus_kill}")

        elif ruolo == 'Veggente':
            # Bonus per veggente: punti per investigazioni su lupi
            cursor.execute("""
                SELECT COUNT(*) FROM lupus_azioni la
                JOIN lupus_partecipazioni lp ON la.target_giocatore_id = lp.giocatore_id 
                JOIN lupus_ruoli lr ON lp.ruolo_id = lr.id
                WHERE la.partita_id = %s AND la.giocatore_id = %s 
                AND la.tipo_azione = 'investigate' AND lr.team = 'lupi'
            """, (partita_id, giocatore_id))

            lupi_scoperti = cursor.fetchone()[0]
            if lupi_scoperti > 0:
                bonus_investigate = lupi_scoperti * 20
                punti_bonus += bonus_investigate
                dettaglio.append(f"Lupi investigati ({lupi_scoperti}): +{bonus_investigate}")

        elif ruolo == 'Dottore':
            # Bonus per dottore: punti per protezioni riuscite
            cursor.execute("""
                SELECT COUNT(*) FROM lupus_azioni 
                WHERE partita_id = %s AND giocatore_id = %s 
                AND tipo_azione = 'protect' AND successo = TRUE
            """, (partita_id, giocatore_id))

            protezioni = cursor.fetchone()[0]
            if protezioni > 0:
                bonus_protect = protezioni * 25
                punti_bonus += bonus_protect
                dettaglio.append(f"Protezioni riuscite ({protezioni}): +{bonus_protect}")

        elif ruolo == 'Sindaco':
            # Bonus per sindaco: punti per voti decisivi
            cursor.execute("""
                SELECT COUNT(DISTINCT turno) FROM lupus_votazioni 
                WHERE partita_id = %s AND votante_giocatore_id = %s AND peso_voto > 1
            """, (partita_id, giocatore_id))

            voti_doppi = cursor.fetchone()[0]
            if voti_doppi > 0:
                bonus_vote = voti_doppi * 10
                punti_bonus += bonus_vote
                dettaglio.append(f"Voti influenti ({voti_doppi}): +{bonus_vote}")

        # Bonus generale per ruoli speciali se il team ha vinto
        if team == team_vincitore and ruolo != 'Cittadino':
            punti_bonus += 15
            dettaglio.append(f"Ruolo speciale vincente: +15")

    except Exception as e:
        print(f"Errore calcolo bonus ruolo: {e}")

    return punti_bonus, dettaglio


@app.route('/api/gamemaster/lupus-end-game', methods=['POST'])
def end_lupus_game():
    """Termina la partita Lupus e assegna punti"""
    if not session.get('is_gamemaster'):
        return jsonify({'error': 'Non autorizzato'}), 403

    data = request.get_json()
    force_end = data.get('force_end', False)
    winner_team = data.get('winner_team')  # Opzionale: forza un vincitore

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Trova partita attiva
        cursor.execute("""
            SELECT id FROM lupus_partite 
            WHERE stato IN ('waiting', 'in_progress') 
            ORDER BY id DESC LIMIT 1
        """)

        partita = cursor.fetchone()
        if not partita:
            return jsonify({'error': 'Nessuna partita attiva da terminare'})

        partita_id = partita[0]

        # Determina il vincitore se non forzato
        if not winner_team:
            winner_team = check_lupus_win_conditions(partita_id)

            # Se non c'è un vincitore naturale e non è forzata la fine
            if not winner_team and not force_end:
                return jsonify({'error': 'La partita non ha ancora un vincitore naturale'})

            # Se forziamo la fine senza vincitore, consideriamo pareggio
            if not winner_team and force_end:
                winner_team = 'pareggio'

        # Aggiorna stato partita
        cursor.execute("""
            UPDATE lupus_partite 
            SET stato = 'ended', vincitore = %s, fase_corrente = 'ended'
            WHERE id = %s
        """, (winner_team if winner_team != 'pareggio' else None, partita_id))

        # Calcola e assegna punti solo se c'è un vincitore
        punteggi = []
        if winner_team != 'pareggio':
            punteggi = calculate_lupus_points(partita_id, winner_team)

        # Aggiorna stato gioco globale
        cursor.execute("""
            UPDATE stato_gioco 
            SET gioco_attivo = NULL, messaggio = 'Gioco terminato. In attesa del gamemaster...'
            WHERE id = 1
        """)

        conn.commit()

        return jsonify({
            'success': True,
            'winner_team': winner_team,
            'punteggi': punteggi if punteggi else [],
            'message': f'Partita terminata! {"Vittoria del team " + winner_team if winner_team != "pareggio" else "Partita terminata in pareggio"}'
        })

    except Exception as e:
        conn.rollback()
        return jsonify({'error': f'Errore terminazione partita: {str(e)}'}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/api/gamemaster/lupus-restart', methods=['POST'])
def restart_lupus_game():
    """Riavvia una nuova partita Lupus con la stessa configurazione"""
    if not session.get('is_gamemaster'):
        return jsonify({'error': 'Non autorizzato'}), 403

    data = request.get_json()
    same_players = data.get('same_players', True)
    same_config = data.get('same_config', True)

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Ottieni info dell'ultima partita
        cursor.execute("""
            SELECT config_utilizzata FROM lupus_partite 
            WHERE stato = 'ended' 
            ORDER BY id DESC LIMIT 1
        """)

        last_game = cursor.fetchone()
        config_id = last_game[0] if last_game and same_config else None

        # Se manteniamo gli stessi giocatori, usa quelli dell'ultima partita
        if same_players and last_game:
            cursor.execute("""
                SELECT lp.giocatore_id FROM lupus_partecipazioni lp
                JOIN lupus_partite lpart ON lp.partita_id = lpart.id
                WHERE lpart.stato = 'ended' AND lp.simulato = FALSE
                ORDER BY lpart.id DESC
            """)
            player_ids = [row[0] for row in cursor.fetchall()]

            if len(player_ids) < 3:
                return jsonify({'error': 'Serve almeno 3 giocatori per riavviare'})

        # Termina eventuali partite ancora attive
        cursor.execute("UPDATE lupus_partite SET stato = 'ended' WHERE stato != 'ended'")

        # Avvia nuova partita con la configurazione precedente
        if config_id:
            # Riusa la configurazione precedente
            return start_lupus_game()  # Chiama la funzione esistente
        else:
            # Avvia con configurazione di default
            return start_flexible_lupus_game()  # Chiama la funzione flessibile

    except Exception as e:
        return jsonify({'error': f'Errore riavvio partita: {str(e)}'}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/api/gamemaster/lupus-game-summary/<int:partita_id>')
def get_lupus_game_summary(partita_id):
    """Ottieni riassunto dettagliato della partita terminata"""
    if not session.get('is_gamemaster'):
        return jsonify({'error': 'Non autorizzato'}), 403

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Info partita
        cursor.execute("""
            SELECT lp.vincitore, lp.turno_numero, lp.created_at,
                   TIMESTAMPDIFF(MINUTE, lp.created_at, NOW()) as durata_minuti
            FROM lupus_partite lp
            WHERE lp.id = %s
        """, (partita_id,))

        partita_info = cursor.fetchone()
        if not partita_info:
            return jsonify({'error': 'Partita non trovata'})

        vincitore, turni, inizio, durata = partita_info

        # Statistiche giocatori
        cursor.execute("""
            SELECT g.nome, lr.nome as ruolo, lr.team, lp.stato, 
                   lp.morte_turno, lp.simulato,
                   COALESCE(part.punti, 0) as punti_ottenuti
            FROM lupus_partecipazioni lp
            JOIN giocatori g ON lp.giocatore_id = g.id
            JOIN lupus_ruoli lr ON lp.ruolo_id = lr.id
            LEFT JOIN partecipazioni part ON part.giocatore_id = g.id 
                AND part.gioco = 'lupus_in_fabula' 
                AND DATE(part.timestamp) = DATE(NOW())
            WHERE lp.partita_id = %s
            ORDER BY lr.team, lp.simulato, g.nome
        """, (partita_id,))

        giocatori = cursor.fetchall()

        # Eventi principali
        cursor.execute("""
            SELECT turno, fase, tipo_evento, descrizione, timestamp
            FROM lupus_eventi
            WHERE partita_id = %s
            ORDER BY turno, timestamp
        """, (partita_id,))

        eventi = cursor.fetchall()

        return jsonify({
            'partita': {
                'id': partita_id,
                'vincitore': vincitore,
                'turni_totali': turni,
                'durata_minuti': durata,
                'data_inizio': inizio.isoformat()
            },
            'giocatori': [{
                'nome': g[0],
                'ruolo': g[1],
                'team': g[2],
                'stato_finale': g[3],
                'morte_turno': g[4],
                'era_bot': g[5],
                'punti_ottenuti': g[6]
            } for g in giocatori],
            'eventi': [{
                'turno': e[0],
                'fase': e[1],
                'tipo': e[2],
                'descrizione': e[3],
                'timestamp': e[4].isoformat()
            } for e in eventi]
        })

    except Exception as e:
        return jsonify({'error': f'Errore recupero riassunto: {str(e)}'}), 500
    finally:
        cursor.close()
        conn.close()


def check_auto_advance_phase(partita_id):
    """Controlla se tutti hanno completato le azioni e avanza automaticamente"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Ottieni info partita
        cursor.execute("""
            SELECT fase_corrente, turno_numero FROM lupus_partite 
            WHERE id = %s AND stato != 'ended'
        """, (partita_id,))

        result = cursor.fetchone()
        if not result:
            return False

        fase_corrente, turno = result

        if fase_corrente == 'night':
            # Controlla se tutti i lupi e ruoli speciali hanno agito
            cursor.execute("""
                SELECT COUNT(*) as total_with_actions,
                       COUNT(la.id) as completed_actions
                FROM lupus_partecipazioni lp
                JOIN lupus_ruoli lr ON lp.ruolo_id = lr.id
                LEFT JOIN lupus_azioni la ON (lp.giocatore_id = la.giocatore_id 
                          AND la.partita_id = %s AND la.turno = %s AND la.fase = 'night')
                WHERE lp.partita_id = %s AND lp.stato = 'vivo' 
                AND (lr.team = 'lupi' OR lr.azione_notturna IS NOT NULL)
            """, (partita_id, turno, partita_id))

            result = cursor.fetchone()
            if result and result[0] > 0 and result[0] == result[1]:
                # Tutti hanno agito, avanza al giorno
                advance_to_next_phase(partita_id, 'day')
                return True

        elif fase_corrente == 'voting':
            # Controlla se tutti i vivi hanno votato
            cursor.execute("""
                SELECT COUNT(*) as total_alive,
                       COUNT(lv.id) as total_votes
                FROM lupus_partecipazioni lp
                LEFT JOIN lupus_votazioni lv ON (lp.giocatore_id = lv.votante_giocatore_id 
                          AND lv.partita_id = %s AND lv.turno = %s)
                WHERE lp.partita_id = %s AND lp.stato = 'vivo'
            """, (partita_id, turno, partita_id))

            result = cursor.fetchone()
            if result and result[0] > 0 and result[0] == result[1]:
                # Tutti hanno votato, processa votazione
                process_voting_results(partita_id, turno)
                return True

        return False

    except Exception as e:
        print(f"Errore controllo avanzamento automatico: {e}")
        return False
    finally:
        cursor.close()
        conn.close()


# 3. PROCESSAMENTO AUTOMATICO DELLE VOTAZIONI
def process_voting_results(partita_id, turno):
    """Processa i risultati della votazione ed elimina il giocatore"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Conta i voti per ogni giocatore
        cursor.execute("""
            SELECT lv.votato_giocatore_id, g.nome, SUM(lv.peso_voto) as voti_totali
            FROM lupus_votazioni lv
            JOIN giocatori g ON lv.votato_giocatore_id = g.id
            WHERE lv.partita_id = %s AND lv.turno = %s
            GROUP BY lv.votato_giocatore_id, g.nome
            ORDER BY voti_totali DESC, RAND()  -- RAND() per pareggi casuali
            LIMIT 1
        """, (partita_id, turno))

        result = cursor.fetchone()
        if result:
            eliminato_id, eliminato_nome, voti_totali = result

            # Elimina il giocatore
            cursor.execute("""
                UPDATE lupus_partecipazioni 
                SET stato = 'eliminato', morte_turno = %s 
                WHERE partita_id = %s AND giocatore_id = %s
            """, (turno, partita_id, eliminato_id))

            # Log evento eliminazione
            cursor.execute("""
                INSERT INTO lupus_eventi (partita_id, turno, fase, tipo_evento, descrizione)
                VALUES (%s, %s, 'voting', 'eliminazione', %s)
            """, (partita_id, turno, f'{eliminato_nome} eliminato con {voti_totali} voti'))

            conn.commit()

            # Controlla condizioni vittoria
            vincitore = check_lupus_win_conditions(partita_id)
            if vincitore:
                end_lupus_game(partita_id, vincitore)
            else:
                # Avanza al turno successivo
                advance_to_next_phase(partita_id, 'night', new_turn=True)

        return True

    except Exception as e:
        print(f"Errore processamento votazioni: {e}")
        return False
    finally:
        cursor.close()
        conn.close()


# 4. AVANZAMENTO FLUIDO TRA FASI
def advance_to_next_phase(partita_id, next_phase, new_turn=False):
    """Avanza alla fase successiva con timer appropriato"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        if new_turn:
            # Nuovo turno
            cursor.execute("""
                UPDATE lupus_partite 
                SET turno_numero = turno_numero + 1, fase_corrente = %s,
                    tempo_fase_inizio = NOW(), ultimo_aggiornamento = NOW()
                WHERE id = %s
            """, (next_phase, partita_id))

            # Ottieni nuovo numero turno
            cursor.execute("SELECT turno_numero FROM lupus_partite WHERE id = %s", (partita_id,))
            nuovo_turno = cursor.fetchone()[0]

        else:
            # Stessa fase, solo cambio fase
            cursor.execute("""
                UPDATE lupus_partite 
                SET fase_corrente = %s, tempo_fase_inizio = NOW(), ultimo_aggiornamento = NOW()
                WHERE id = %s
            """, (next_phase, partita_id))
            nuovo_turno = None

        # Aggiorna durata fase
        update_lupus_phase_timer(partita_id, next_phase)

        conn.commit()

        # Log cambio fase
        if nuovo_turno:
            cursor.execute("""
                INSERT INTO lupus_eventi (partita_id, turno, fase, tipo_evento, descrizione)
                VALUES (%s, %s, %s, 'cambio_fase', %s)
            """, (partita_id, nuovo_turno, next_phase, f'Inizio turno {nuovo_turno} - Fase: {next_phase}'))
        else:
            cursor.execute("""
                SELECT turno_numero FROM lupus_partite WHERE id = %s
            """, (partita_id,))
            turno_corrente = cursor.fetchone()[0]

            cursor.execute("""
                INSERT INTO lupus_eventi (partita_id, turno, fase, tipo_evento, descrizione)
                VALUES (%s, %s, %s, 'cambio_fase', %s)
            """, (partita_id, turno_corrente, next_phase, f'Cambio fase: {next_phase}'))

        conn.commit()
        return True

    except Exception as e:
        print(f"Errore avanzamento fase: {e}")
        return False
    finally:
        cursor.close()
        conn.close()


# 5. ROUTE PER CONTROLLO AUTOMATICO PERIODICO
@app.route('/api/lupus-auto-check', methods=['POST'])
def lupus_auto_check():
    """Controllo automatico per avanzamento fasi - da chiamare ogni 5 secondi"""

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Trova partita attiva
        cursor.execute("""
            SELECT id, fase_corrente, fine_fase, turno_numero 
            FROM lupus_partite 
            WHERE stato != 'ended' 
            ORDER BY id DESC LIMIT 1
        """)

        partita = cursor.fetchone()
        if not partita:
            return jsonify({'status': 'no_game'})

        partita_id, fase, fine_fase, turno = partita

        # Controlla se il tempo è scaduto
        if datetime.now() > fine_fase:
            if fase == 'night':
                # Processamento azioni notturne e avanza al giorno
                process_night_actions(partita_id, turno)
                advance_to_next_phase(partita_id, 'day')

            elif fase == 'day':
                # Avanza alla votazione
                advance_to_next_phase(partita_id, 'voting')

            elif fase == 'voting':
                # Processa votazioni
                process_voting_results(partita_id, turno)

            return jsonify({'status': 'phase_advanced', 'new_phase': fase})

        # Controlla avanzamento automatico
        elif check_auto_advance_phase(partita_id):
            return jsonify({'status': 'auto_advanced'})

        return jsonify({'status': 'ok'})

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


# 6. PROCESSAMENTO AZIONI NOTTURNE
def process_night_actions(partita_id, turno):
    """Processa tutte le azioni notturne"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Ottieni tutte le azioni non processate del turno
        cursor.execute("""
            SELECT la.id, la.giocatore_id, la.tipo_azione, la.target_giocatore_id,
                   g.nome as attaccante, gt.nome as target
            FROM lupus_azioni la
            JOIN giocatori g ON la.giocatore_id = g.id
            LEFT JOIN giocatori gt ON la.target_giocatore_id = gt.id
            WHERE la.partita_id = %s AND la.turno = %s AND la.fase = 'night' 
            AND la.processata = FALSE
            ORDER BY la.id
        """, (partita_id, turno))

        azioni = cursor.fetchall()

        for azione_id, giocatore_id, tipo_azione, target_id, attaccante, target in azioni:

            if tipo_azione == 'kill' and target_id:
                # Elimina il target
                cursor.execute("""
                    UPDATE lupus_partecipazioni 
                    SET stato = 'morto', morte_turno = %s 
                    WHERE partita_id = %s AND giocatore_id = %s
                """, (turno, partita_id, target_id))

                # Log eliminazione
                cursor.execute("""
                    INSERT INTO lupus_eventi (partita_id, turno, fase, tipo_evento, descrizione)
                    VALUES (%s, %s, 'night', 'morte', %s)
                """, (partita_id, turno, f'{target} è stato eliminato durante la notte'))

            # Marca azione come processata
            cursor.execute("""
                UPDATE lupus_azioni SET processata = TRUE WHERE id = %s
            """, (azione_id,))

        conn.commit()
        return True

    except Exception as e:
        print(f"Errore processamento azioni notturne: {e}")
        return False
    finally:
        cursor.close()
        conn.close()


# 7. TERMINAZIONE GIOCO
def end_lupus_game(partita_id, vincitore):
    """Termina il gioco e dichiara il vincitore"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            UPDATE lupus_partite 
            SET stato = 'ended', vincitore = %s, fine_partita = NOW() 
            WHERE id = %s
        """, (vincitore, partita_id))

        # Log fine partita
        cursor.execute("""
            INSERT INTO lupus_eventi (partita_id, turno, fase, tipo_evento, descrizione)
            VALUES (%s, (SELECT turno_numero FROM lupus_partite WHERE id = %s), 
                    'ended', 'fine_partita', %s)
        """, (partita_id, partita_id, f'Partita terminata! Vittoria: {vincitore}'))

        # Aggiorna stato generale gioco
        cursor.execute("""
            UPDATE stato_gioco SET gioco_attivo = NULL, 
            messaggio = %s, ultimo_aggiornamento = NOW() WHERE id = 1
        """, (f'Partita Lupus terminata! Hanno vinto i {vincitore}! 🎉',))

        conn.commit()
        return True

    except Exception as e:
        print(f"Errore terminazione gioco: {e}")
        return False
    finally:
        cursor.close()
        conn.close()


def update_lupus_phase_timer(partita_id, fase):
    """Imposta timer di 30 secondi per tutte le fasi"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Timer fisso di 30 secondi per tutte le fasi
        fine_fase = datetime.now() + timedelta(seconds=30)

        cursor.execute("""
            UPDATE lupus_partite 
            SET fine_fase = %s, ultimo_aggiornamento = NOW()
            WHERE id = %s
        """, (fine_fase, partita_id))

        conn.commit()
        return True

    except Exception as e:
        print(f"Errore aggiornamento timer: {e}")
        return False
    finally:
        cursor.close()
        conn.close()


# MODIFICA 2: Controllo automatico avanzamento fasi
def check_auto_advance_phase(partita_id):
    """Controlla se può avanzare automaticamente senza aspettare tutti"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Ottieni info partita
        cursor.execute("""
            SELECT fase_corrente, turno_numero 
            FROM lupus_partite 
            WHERE id = %s
        """, (partita_id,))

        result = cursor.fetchone()
        if not result:
            return False

        fase, turno = result

        if fase == 'night':
            # Controlla se tutti i lupi e ruoli speciali hanno agito
            cursor.execute("""
                SELECT COUNT(*) as total_attivi,
                       COUNT(CASE WHEN ha_fatto_azione = TRUE THEN 1 END) as hanno_agito
                FROM lupus_giocatori lg
                JOIN lupus_ruoli lr ON lg.ruolo_id = lr.id
                WHERE lg.partita_id = %s 
                AND lg.stato = 'vivo'
                AND (lr.team = 'lupi' OR lr.nome IN ('Veggente', 'Guardia'))
            """, (partita_id,))

            result = cursor.fetchone()
            if result and result[0] > 0 and result[0] == result[1]:
                # Tutti hanno agito, avanza al giorno
                advance_to_next_phase(partita_id, 'day')
                return True

        elif fase == 'voting':
            # Controlla se tutti i vivi hanno votato
            cursor.execute("""
                SELECT COUNT(*) as total_vivi,
                       COUNT(CASE WHEN ha_votato = TRUE THEN 1 END) as hanno_votato
                FROM lupus_giocatori 
                WHERE partita_id = %s AND stato = 'vivo'
            """, (partita_id,))

            result = cursor.fetchone()
            if result and result[0] > 0 and result[0] == result[1]:
                # Tutti hanno votato, processa risultati
                process_voting_results(partita_id, turno)
                return True

        return False

    except Exception as e:
        print(f"Errore controllo auto-avanzamento: {e}")
        return False
    finally:
        cursor.close()
        conn.close()





# MODIFICA 4: Processamento votazioni modificato per gestire voti mancanti
def process_voting_results(partita_id, turno):
    """Processa risultati votazione anche con voti mancanti"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Conta voti per ogni giocatore
        cursor.execute("""
            SELECT target_id, COUNT(*) as voti
            FROM lupus_azioni 
            WHERE partita_id = %s AND turno = %s 
            AND tipo_azione = 'vote' AND target_id IS NOT NULL
            GROUP BY target_id
            ORDER BY voti DESC
        """, (partita_id, turno))

        voti = cursor.fetchall()

        if not voti:
            # Nessun voto, nessuna eliminazione
            cursor.execute("""
                INSERT INTO lupus_eventi (partita_id, turno, fase, tipo_evento, descrizione)
                VALUES (%s, %s, 'voting', 'no_elimination', 'Nessun voto valido - Nessuna eliminazione')
            """, (partita_id, turno))
        else:
            # Elimina il giocatore con più voti
            eliminato_id = voti[0][0]
            voti_ricevuti = voti[0][1]

            # Controlla pareggio
            if len(voti) > 1 and voti[1][1] == voti_ricevuti:
                # Pareggio - nessuna eliminazione
                cursor.execute("""
                    INSERT INTO lupus_eventi (partita_id, turno, fase, tipo_evento, descrizione)
                    VALUES (%s, %s, 'voting', 'tie', 'Pareggio nella votazione - Nessuna eliminazione')
                """, (partita_id, turno))
            else:
                # Elimina giocatore
                cursor.execute("""
                    UPDATE lupus_giocatori 
                    SET stato = 'eliminato', ultimo_aggiornamento = NOW()
                    WHERE id = %s
                """, (eliminato_id,))

                # Log eliminazione
                cursor.execute("""
                    SELECT nome FROM lupus_giocatori WHERE id = %s
                """, (eliminato_id,))
                nome_eliminato = cursor.fetchone()[0]

                cursor.execute("""
                    INSERT INTO lupus_eventi (partita_id, turno, fase, tipo_evento, descrizione)
                    VALUES (%s, %s, 'voting', 'elimination', %s)
                """, (partita_id, turno, f'{nome_eliminato} è stato eliminato con {voti_ricevuti} voti'))

        # Reset stati per prossimo turno
        cursor.execute("""
            UPDATE lupus_giocatori 
            SET ha_votato = FALSE, ha_fatto_azione = FALSE, ultimo_aggiornamento = NOW()
            WHERE partita_id = %s
        """, (partita_id,))

        # Controlla condizioni vittoria
        if check_win_condition(partita_id):
            conn.commit()
            return True

        # Avanza alla notte del turno successivo
        advance_to_next_phase(partita_id, 'night', new_turn=True)

        conn.commit()
        return True

    except Exception as e:
        print(f"Errore processamento voti: {e}")
        return False
    finally:
        cursor.close()
        conn.close()


# MODIFICA 5: Avanzamento fluido tra fasi
def advance_to_next_phase(partita_id, next_phase, new_turn=False):
    """Avanza alla fase successiva con timer di 30 secondi"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        if new_turn:
            # Nuovo turno
            cursor.execute("""
                UPDATE lupus_partite 
                SET turno_numero = turno_numero + 1, fase_corrente = %s,
                    tempo_fase_inizio = NOW(), ultimo_aggiornamento = NOW()
                WHERE id = %s
            """, (next_phase, partita_id))

            cursor.execute("SELECT turno_numero FROM lupus_partite WHERE id = %s", (partita_id,))
            nuovo_turno = cursor.fetchone()[0]
        else:
            # Stessa fase, solo cambio fase
            cursor.execute("""
                UPDATE lupus_partite 
                SET fase_corrente = %s, tempo_fase_inizio = NOW(), ultimo_aggiornamento = NOW()
                WHERE id = %s
            """, (next_phase, partita_id))
            nuovo_turno = None

        # Aggiorna timer a 30 secondi
        update_lupus_phase_timer(partita_id, next_phase)
        conn.commit()
        return True

    except Exception as e:
        print(f"Errore avanzamento fase: {e}")
        return False
    finally:
        cursor.close()
        conn.close()


# Chiamata per creare le tabelle (da eseguire una volta)
if __name__ == "__main__":
    create_lupus_tables()


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')