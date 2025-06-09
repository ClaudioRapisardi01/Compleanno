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




if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')