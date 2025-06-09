from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
import json
from datetime import datetime
import secrets

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Cambia con una chiave sicura

# Password del gamemaster (da cambiare!)
GAMEMASTER_PASSWORD = 'festa2025'

# Configurazione database MySQL
DB_CONFIG = {
    'host': 'localhost',
    'user': 'claudio',
    'password': 'Superrapa22',
    'database': 'birthday_game'
}


def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)


# Route principale
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.get_json()
        nome = data.get('nome')
        squadra = data.get('squadra')
        personaggio_id = data.get('personaggio_id')

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            # Verifica che il personaggio non sia già preso
            cursor.execute("SELECT nome FROM personaggi WHERE id = %s AND disponibile = TRUE", (personaggio_id,))
            personaggio = cursor.fetchone()

            if not personaggio:
                return jsonify({'success': False, 'error': 'Personaggio non disponibile'})

            # Registra il giocatore
            cursor.execute("""
                INSERT INTO giocatori (nome, squadra, personaggio_id, punti_totali) 
                VALUES (%s, %s, %s, 0)
            """, (nome, squadra, personaggio_id))

            # Marca il personaggio come non disponibile
            cursor.execute("UPDATE personaggi SET disponibile = FALSE WHERE id = %s", (personaggio_id,))

            conn.commit()

            session['player_id'] = cursor.lastrowid
            session['player_name'] = nome
            session['team'] = squadra
            session['personaggio'] = personaggio[0]

            return jsonify({'success': True, 'redirect': '/dashboard'})
        except mysql.connector.Error as err:
            return jsonify({'success': False, 'error': str(err)})
        finally:
            cursor.close()
            conn.close()

    # GET: mostra form con personaggi disponibili
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, nome, descrizione, immagine FROM personaggi WHERE disponibile = TRUE ORDER BY nome")
    personaggi = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('register.html', personaggi=personaggi)


@app.route('/dashboard')
def dashboard():
    if 'player_id' not in session:
        return redirect(url_for('register'))

    # Controlla lo stato del gioco corrente
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT gioco_attivo, messaggio FROM stato_gioco WHERE id = 1")
    stato = cursor.fetchone()
    cursor.close()
    conn.close()

    gioco_attivo = stato[0] if stato else None
    messaggio = stato[1] if stato else "In attesa del gamemaster..."

    return render_template('dashboard.html', gioco_attivo=gioco_attivo, messaggio=messaggio)


# ROUTES GAMEMASTER
@app.route('/gamemaster', methods=['GET', 'POST'])
def gamemaster():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == GAMEMASTER_PASSWORD:
            session['is_gamemaster'] = True
            return redirect(url_for('gamemaster_panel'))
        else:
            return render_template('gamemaster_login.html', error='Password errata')

    return render_template('gamemaster_login.html')


@app.route('/gamemaster/panel')
def gamemaster_panel():
    if not session.get('is_gamemaster'):
        return redirect(url_for('gamemaster'))

    conn = get_db_connection()
    cursor = conn.cursor()

    # Stato attuale del gioco
    cursor.execute("SELECT gioco_attivo, messaggio FROM stato_gioco WHERE id = 1")
    stato_attuale = cursor.fetchone()

    # Statistiche giocatori
    cursor.execute("SELECT COUNT(*) FROM giocatori")
    num_giocatori = cursor.fetchone()[0]

    # Partecipazioni per gioco
    cursor.execute("""
        SELECT gioco, COUNT(DISTINCT giocatore_id) as partecipanti 
        FROM partecipazioni 
        GROUP BY gioco
    """)
    partecipazioni = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('gamemaster_panel.html',
                           stato_attuale=stato_attuale,
                           num_giocatori=num_giocatori,
                           partecipazioni=partecipazioni)


@app.route('/gamemaster/set-game', methods=['POST'])
def set_active_game():
    if not session.get('is_gamemaster'):
        return jsonify({'error': 'Non autorizzato'})

    data = request.get_json()
    gioco = data.get('gioco')
    messaggio = data.get('messaggio', '')

    conn = get_db_connection()
    cursor = conn.cursor()

    # Aggiorna o inserisci lo stato del gioco
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
        return redirect(url_for('register'))

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
    risposte = data.get('risposte')

    conn = get_db_connection()
    cursor = conn.cursor()

    # Calcola punteggio
    punti = 0
    for domanda_id, risposta in risposte.items():
        cursor.execute("SELECT risposta_corretta FROM quiz_domande WHERE id = %s", (domanda_id,))
        corretta = cursor.fetchone()[0]
        if risposta == corretta:
            punti += 10

    # Aggiorna punteggio giocatore
    cursor.execute("""
        UPDATE giocatori 
        SET punti_totali = punti_totali + %s 
        WHERE id = %s
    """, (punti, session['player_id']))

    # Registra partecipazione
    cursor.execute("""
        INSERT INTO partecipazioni (giocatore_id, gioco, punti, timestamp) 
        VALUES (%s, 'quiz_personalizzato', %s, NOW())
    """, (session['player_id'], punti))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({'punti': punti, 'message': f'Hai guadagnato {punti} punti!'})


# INDOVINA CHI
@app.route('/indovina-chi')
def indovina_chi():
    if 'player_id' not in session:
        return redirect(url_for('register'))

    # Verifica che il gioco sia attivo
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT gioco_attivo FROM stato_gioco WHERE id = 1")
    stato = cursor.fetchone()

    if not stato or stato[0] != 'indovina_chi':
        cursor.close()
        conn.close()
        return redirect(url_for('dashboard'))

    cursor.execute("SELECT * FROM indovina_chi ORDER BY RAND() LIMIT 5")
    indovinelli = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('indovina_chi.html', indovinelli=indovinelli)


@app.route('/submit-indovina-chi', methods=['POST'])
def submit_indovina_chi():
    if 'player_id' not in session:
        return jsonify({'error': 'Non autorizzato'})

    data = request.get_json()
    risposte = data.get('risposte')

    conn = get_db_connection()
    cursor = conn.cursor()

    punti = 0
    for indovinello_id, risposta in risposte.items():
        cursor.execute("SELECT risposta_corretta FROM indovina_chi WHERE id = %s", (indovinello_id,))
        corretta = cursor.fetchone()[0]
        if risposta.lower().strip() == corretta.lower().strip():
            punti += 15

    cursor.execute("""
        UPDATE giocatori 
        SET punti_totali = punti_totali + %s 
        WHERE id = %s
    """, (punti, session['player_id']))

    cursor.execute("""
        INSERT INTO partecipazioni (giocatore_id, gioco, punti, timestamp) 
        VALUES (%s, 'indovina_chi', %s, NOW())
    """, (session['player_id'], punti))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({'punti': punti, 'message': f'Hai guadagnato {punti} punti!'})


# QUIZ A SQUADRE
@app.route('/quiz-squadre')
def quiz_squadre():
    if 'player_id' not in session:
        return redirect(url_for('register'))

    # Verifica che il gioco sia attivo
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT gioco_attivo FROM stato_gioco WHERE id = 1")
    stato = cursor.fetchone()

    if not stato or stato[0] != 'quiz_squadre':
        cursor.close()
        conn.close()
        return redirect(url_for('dashboard'))

    cursor.close()
    conn.close()
    return render_template('quiz_squadre.html')


@app.route('/get-team-question')
def get_team_question():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM quiz_squadre ORDER BY RAND() LIMIT 1")
    domanda = cursor.fetchone()
    cursor.close()
    conn.close()

    if domanda:
        return jsonify({
            'id': domanda[0],
            'domanda': domanda[1],
            'opzioni': json.loads(domanda[2])
        })
    return jsonify({'error': 'Nessuna domanda disponibile'})


@app.route('/submit-team-answer', methods=['POST'])
def submit_team_answer():
    if 'player_id' not in session:
        return jsonify({'error': 'Non autorizzato'})

    data = request.get_json()
    domanda_id = data.get('domanda_id')
    risposta = data.get('risposta')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT risposta_corretta FROM quiz_squadre WHERE id = %s", (domanda_id,))
    corretta = cursor.fetchone()[0]

    punti = 20 if risposta == corretta else 0

    # Aggiorna punti squadra
    cursor.execute("""
        UPDATE giocatori 
        SET punti_totali = punti_totali + %s 
        WHERE squadra = %s
    """, (punti // 4, session['team']))  # Dividi punti tra membri squadra

    cursor.execute("""
        INSERT INTO partecipazioni (giocatore_id, gioco, punti, timestamp) 
        VALUES (%s, 'quiz_squadre', %s, NOW())
    """, (session['player_id'], punti // 4))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({
        'corretto': risposta == corretta,
        'punti': punti // 4,
        'risposta_corretta': corretta
    })


# VOTAZIONE COSTUMI
@app.route('/votazione-costumi')
def votazione_costumi():
    if 'player_id' not in session:
        return redirect(url_for('register'))

    # Verifica che il gioco sia attivo
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT gioco_attivo FROM stato_gioco WHERE id = 1")
    stato = cursor.fetchone()

    if not stato or stato[0] != 'votazione_costumi':
        cursor.close()
        conn.close()
        return redirect(url_for('dashboard'))

    cursor.execute("""
        SELECT p.nome, p.descrizione, p.immagine 
        FROM personaggi p 
        JOIN giocatori g ON p.id = g.personaggio_id 
        WHERE p.disponibile = FALSE
    """)
    personaggi_in_gioco = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('votazione_costumi.html', personaggi=personaggi_in_gioco)


@app.route('/vote-costume', methods=['POST'])
def vote_costume():
    if 'player_id' not in session:
        return jsonify({'error': 'Non autorizzato'})

    data = request.get_json()
    personaggio_votato = data.get('personaggio')

    conn = get_db_connection()
    cursor = conn.cursor()

    # Verifica se ha già votato
    cursor.execute("""
        SELECT id FROM voti_costumi 
        WHERE votante_id = %s
    """, (session['player_id'],))

    if cursor.fetchone():
        return jsonify({'error': 'Hai già votato!'})

    # Registra voto
    cursor.execute("""
        INSERT INTO voti_costumi (votante_id, personaggio_votato, timestamp) 
        VALUES (%s, %s, NOW())
    """, (session['player_id'], personaggio_votato))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({'success': True, 'message': 'Voto registrato!'})


# CLASSIFICA
@app.route('/classifica')
def classifica():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Classifica individuale
    cursor.execute("""
        SELECT g.nome, g.squadra, p.nome as personaggio, g.punti_totali 
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

    # Risultati votazione costumi
    cursor.execute("""
        SELECT personaggio_votato, COUNT(*) as voti 
        FROM voti_costumi 
        GROUP BY personaggio_votato 
        ORDER BY voti DESC
    """)
    voti_costumi = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('classifica.html',
                           individuale=classifica_individuale,
                           squadre=classifica_squadre,
                           costumi=voti_costumi)


@app.route('/api/classifica')
def api_classifica():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT g.nome, g.squadra, g.punti_totali 
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
        'punti': player[2]
    } for player in top_players])


if __name__ == '__main__':
    app.run(debug=True)