#!/usr/bin/env python3
"""
Script completo per setup database birthday_game - Versione senza Lupus
"""

import mysql.connector
import sys
import json

# Configurazione database (modifica se necessario)
DB_CONFIG = {
    'host': 'localhost',
    'user': 'claudio',
    'password': 'Superrapa22',
    'database': 'birthday_game'
}


def get_db_connection():
    """Crea connessione al database"""
    try:
        return mysql.connector.connect(**DB_CONFIG)
    except mysql.connector.Error as err:
        print(f"Errore connessione database: {err}")
        return None


def create_all_tables():
    """Crea tutte le tabelle necessarie"""

    tables = {
        'personaggi': """
            CREATE TABLE IF NOT EXISTS personaggi (
                id INT AUTO_INCREMENT PRIMARY KEY,
                nome VARCHAR(255) NOT NULL,
                descrizione TEXT,
                disponibile BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """,

        'giocatori': """
            CREATE TABLE IF NOT EXISTS giocatori (
                id INT AUTO_INCREMENT PRIMARY KEY,
                nome VARCHAR(255) NOT NULL UNIQUE,
                squadra ENUM('Rossi', 'Blu', 'Verdi', 'Gialli') NOT NULL,
                personaggio_id INT,
                punti_totali INT DEFAULT 0,
                foto_profilo VARCHAR(255),
                escluso_da_gioco BOOLEAN DEFAULT FALSE,
                ultima_attivita TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (personaggio_id) REFERENCES personaggi(id) ON DELETE SET NULL
            )
        """,

        'foto_profili': """
            CREATE TABLE IF NOT EXISTS foto_profili (
                id INT AUTO_INCREMENT PRIMARY KEY,
                nome_file VARCHAR(255) NOT NULL,
                nome_originale VARCHAR(255),
                giocatore_id INT,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (giocatore_id) REFERENCES giocatori(id) ON DELETE CASCADE
            )
        """,

        'stato_gioco': """
            CREATE TABLE IF NOT EXISTS stato_gioco (
                id INT PRIMARY KEY DEFAULT 1,
                gioco_attivo VARCHAR(50),
                messaggio TEXT,
                ultimo_aggiornamento TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """,

        'partecipazioni': """
            CREATE TABLE IF NOT EXISTS partecipazioni (
                id INT AUTO_INCREMENT PRIMARY KEY,
                giocatore_id INT NOT NULL,
                gioco VARCHAR(50) NOT NULL,
                punti INT DEFAULT 0,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (giocatore_id) REFERENCES giocatori(id) ON DELETE CASCADE
            )
        """,

        'quiz_domande': """
            CREATE TABLE IF NOT EXISTS quiz_domande (
                id INT AUTO_INCREMENT PRIMARY KEY,
                domanda TEXT NOT NULL,
                opzione_a VARCHAR(255) NOT NULL,
                opzione_b VARCHAR(255) NOT NULL,
                opzione_c VARCHAR(255) NOT NULL,
                opzione_d VARCHAR(255) NOT NULL,
                risposta_corretta ENUM('a', 'b', 'c', 'd') NOT NULL,
                categoria VARCHAR(100) DEFAULT 'generale',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """,

        'quiz_risposte': """
            CREATE TABLE IF NOT EXISTS quiz_risposte (
                id INT AUTO_INCREMENT PRIMARY KEY,
                giocatore_id INT NOT NULL,
                domanda_id INT NOT NULL,
                risposta_data ENUM('a', 'b', 'c', 'd') NOT NULL,
                corretta BOOLEAN NOT NULL,
                tempo_risposta INT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (giocatore_id) REFERENCES giocatori(id) ON DELETE CASCADE,
                FOREIGN KEY (domanda_id) REFERENCES quiz_domande(id) ON DELETE CASCADE,
                UNIQUE KEY unique_risposta_per_domanda (giocatore_id, domanda_id)
            )
        """,

        'indovina_persone': """
            CREATE TABLE IF NOT EXISTS indovina_persone (
                id INT AUTO_INCREMENT PRIMARY KEY,
                nome VARCHAR(255) NOT NULL,
                descrizione TEXT,
                foto_filename VARCHAR(255),
                attivo BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """,

        'indovina_indizi': """
            CREATE TABLE IF NOT EXISTS indovina_indizi (
                id INT AUTO_INCREMENT PRIMARY KEY,
                persona_id INT NOT NULL,
                indizio TEXT NOT NULL,
                ordine INT NOT NULL,
                punti INT DEFAULT 50,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (persona_id) REFERENCES indovina_persone(id) ON DELETE CASCADE,
                UNIQUE KEY unique_ordine_per_persona (persona_id, ordine)
            )
        """,

        'indovina_partite': """
            CREATE TABLE IF NOT EXISTS indovina_partite (
                id INT AUTO_INCREMENT PRIMARY KEY,
                giocatore_id INT NOT NULL,
                persona_id INT NOT NULL,
                indizi_richiesti INT DEFAULT 0,
                punti_guadagnati INT DEFAULT 0,
                tempo_impiegato INT,
                risposta_corretta BOOLEAN DEFAULT FALSE,
                completata BOOLEAN DEFAULT FALSE,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (giocatore_id) REFERENCES giocatori(id) ON DELETE CASCADE,
                FOREIGN KEY (persona_id) REFERENCES indovina_persone(id) ON DELETE CASCADE
            )
        """,

        'indovina_risposte': """
            CREATE TABLE IF NOT EXISTS indovina_risposte (
                id INT AUTO_INCREMENT PRIMARY KEY,
                partita_id INT NOT NULL,
                giocatore_id INT NOT NULL,
                indizio_numero INT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (partita_id) REFERENCES indovina_partite(id) ON DELETE CASCADE,
                FOREIGN KEY (giocatore_id) REFERENCES giocatori(id) ON DELETE CASCADE,
                UNIQUE KEY unique_risposta_per_indizio (partita_id, giocatore_id, indizio_numero)
            )
        """,

        'votazione_costumi': """
            CREATE TABLE IF NOT EXISTS votazione_costumi (
                id INT AUTO_INCREMENT PRIMARY KEY,
                votante_id INT NOT NULL,
                votato_id INT NOT NULL,
                categoria VARCHAR(100) NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (votante_id) REFERENCES giocatori(id) ON DELETE CASCADE,
                FOREIGN KEY (votato_id) REFERENCES giocatori(id) ON DELETE CASCADE,
                UNIQUE KEY unique_voto_per_categoria (votante_id, categoria)
            )
        """,

        'disconnessioni': """
            CREATE TABLE IF NOT EXISTS disconnessioni (
                id INT AUTO_INCREMENT PRIMARY KEY,
                giocatore_id INT NOT NULL,
                motivo TEXT,
                gamemaster_action BOOLEAN DEFAULT FALSE,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (giocatore_id) REFERENCES giocatori(id) ON DELETE CASCADE
            )
        """,

        'esclusioni_gioco': """
            CREATE TABLE IF NOT EXISTS esclusioni_gioco (
                id INT AUTO_INCREMENT PRIMARY KEY,
                giocatore_id INT NOT NULL,
                gioco_corrente VARCHAR(50),
                motivo TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (giocatore_id) REFERENCES giocatori(id) ON DELETE CASCADE
            )
        """
    }

    conn = get_db_connection()
    if not conn:
        return False

    cursor = conn.cursor()

    try:
        print("🔧 Creazione tabelle in corso...")

        # Crea le tabelle nell'ordine corretto (rispettando le foreign key)
        creation_order = [
            'personaggi', 'giocatori', 'foto_profili', 'stato_gioco',
            'partecipazioni', 'quiz_domande', 'quiz_risposte', 'indovina_persone',
            'indovina_indizi', 'indovina_partite', 'indovina_risposte',
            'votazione_costumi', 'disconnessioni', 'esclusioni_gioco'
        ]

        for table_name in creation_order:
            if table_name in tables:
                cursor.execute(tables[table_name])
                print(f"✅ Tabella '{table_name}' creata/verificata")

        # Inserisci stato gioco iniziale
        cursor.execute("""
            INSERT IGNORE INTO stato_gioco (id, gioco_attivo, messaggio) 
            VALUES (1, NULL, 'In attesa del gamemaster...')
        """)

        conn.commit()
        print("✅ Setup tabelle completato con successo!")
        return True

    except mysql.connector.Error as err:
        print(f"❌ Errore creazione tabelle: {err}")
        return False

    finally:
        cursor.close()
        conn.close()


def insert_sample_data():
    """Inserisce dati di esempio"""
    conn = get_db_connection()
    if not conn:
        return False

    cursor = conn.cursor()

    try:
        print("📝 Inserimento dati di esempio...")

        # Personaggi di esempio
        personaggi = [
            ('Mario Bros', 'L\'idraulico più famoso del mondo! Salta su funghi e salva principesse.'),
            ('Pikachu', 'Il Pokémon elettrico più carino che ci sia! ⚡'),
            ('Wonder Woman', 'Amazzone guerriera con lazo della verità e braccialetti magici.'),
            ('Harry Potter', 'Il mago con la cicatrice a saetta più famoso di Hogwarts.'),
            ('Spider-Man', 'L\'arrampicamuri di quartiere che lancia ragnatele.'),
            ('Hermione Granger', 'La strega più intelligente della sua generazione.'),
            ('Batman', 'Il cavaliere oscuro di Gotham City.'),
            ('Elsa', 'La regina dei ghiacci con poteri magici.'),
            ('Joker', 'Il principe del crimine con il sorriso inquietante.'),
            ('Deadpool', 'Il mercenario chiacchierone in rosso e nero.')
        ]

        for nome, descrizione in personaggi:
            cursor.execute("""
                INSERT IGNORE INTO personaggi (nome, descrizione, disponibile)
                VALUES (%s, %s, TRUE)
            """, (nome, descrizione))

        # Domande quiz di esempio
        quiz_domande = [
            {
                'domanda': 'Qual è il colore preferito del festeggiato?',
                'a': 'Rosso', 'b': 'Blu', 'c': 'Verde', 'd': 'Giallo',
                'corretta': 'b', 'categoria': 'personale'
            },
            {
                'domanda': 'Qual è il cibo preferito del festeggiato?',
                'a': 'Pizza', 'b': 'Pasta', 'c': 'Hamburger', 'd': 'Sushi',
                'corretta': 'a', 'categoria': 'personale'
            },
            {
                'domanda': 'In che anno è nato il festeggiato?',
                'a': '1990', 'b': '1995', 'c': '2000', 'd': '1985',
                'corretta': 'c', 'categoria': 'personale'
            },
            {
                'domanda': 'Qual è lo sport preferito del festeggiato?',
                'a': 'Calcio', 'b': 'Tennis', 'c': 'Basket', 'd': 'Nuoto',
                'corretta': 'a', 'categoria': 'hobby'
            },
            {
                'domanda': 'Qual è la destinazione di viaggio dei sogni del festeggiato?',
                'a': 'Giappone', 'b': 'Stati Uniti', 'c': 'Australia', 'd': 'Norvegia',
                'corretta': 'a', 'categoria': 'viaggi'
            }
        ]

        for q in quiz_domande:
            cursor.execute("""
                INSERT IGNORE INTO quiz_domande (domanda, opzione_a, opzione_b, opzione_c, opzione_d, risposta_corretta, categoria)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (q['domanda'], q['a'], q['b'], q['c'], q['d'], q['corretta'], q['categoria']))

        # Persone per Indovina Chi di esempio
        indovina_persone = [
            ('Marco Rossi', 'Amico di lunga data, appassionato di calcio'),
            ('Laura Bianchi', 'Collega di lavoro, ama i viaggi'),
            ('Giuseppe Verde', 'Compagno di università, musicista'),
            ('Anna Gialli', 'Amica d\'infanzia, chef professionista'),
            ('Roberto Neri', 'Cugino del festeggiato, appassionato di tecnologia')
        ]

        for nome, descrizione in indovina_persone:
            cursor.execute("""
                INSERT IGNORE INTO indovina_persone (nome, descrizione, attivo)
                VALUES (%s, %s, TRUE)
            """, (nome, descrizione))

        # Indizi di esempio (solo se le persone esistono)
        cursor.execute("SELECT id, nome FROM indovina_persone LIMIT 5")
        persone = cursor.fetchall()

        indizi_esempi = {
            0: [  # Marco Rossi
                ('Gioca a calcio tutti i weekend', 1, 100),
                ('Ha una collezione di maglie del Milan', 2, 80),
                ('Lavora come ingegnere informatico', 3, 60),
                ('Il suo secondo nome è Antonio', 4, 40),
                ('Ha due gatti chiamati Gigi e Pippo', 5, 20)
            ],
            1: [  # Laura Bianchi
                ('Ha visitato più di 30 paesi', 1, 100),
                ('Parla fluentemente 4 lingue', 2, 80),
                ('Lavora in una agenzia di viaggi', 3, 60),
                ('È nata a Firenze', 4, 40),
                ('Il suo hobby è la fotografia', 5, 20)
            ]
        }

        for i, (persona_id, nome) in enumerate(persone[:2]):  # Solo primi due per esempio
            if i in indizi_esempi:
                for indizio, ordine, punti in indizi_esempi[i]:
                    cursor.execute("""
                        INSERT IGNORE INTO indovina_indizi (persona_id, indizio, ordine, punti)
                        VALUES (%s, %s, %s, %s)
                    """, (persona_id, indizio, ordine, punti))

        conn.commit()
        print("✅ Dati di esempio inseriti con successo!")
        return True

    except mysql.connector.Error as err:
        print(f"❌ Errore inserimento dati: {err}")
        conn.rollback()
        return False

    finally:
        cursor.close()
        conn.close()


def check_tables():
    """Verifica che tutte le tabelle esistano"""
    required_tables = [
        'personaggi', 'giocatori', 'foto_profili', 'stato_gioco',
        'partecipazioni', 'quiz_domande', 'quiz_risposte', 'indovina_persone',
        'indovina_indizi', 'indovina_partite', 'indovina_risposte',
        'votazione_costumi', 'disconnessioni', 'esclusioni_gioco'
    ]

    conn = get_db_connection()
    if not conn:
        return False

    cursor = conn.cursor()

    try:
        cursor.execute("SHOW TABLES")
        existing_tables = [table[0] for table in cursor.fetchall()]

        missing_tables = [table for table in required_tables if table not in existing_tables]

        if missing_tables:
            print(f"⚠️ Tabelle mancanti: {missing_tables}")
            return False
        else:
            print("✅ Tutte le tabelle necessarie sono presenti")
            return True

    except mysql.connector.Error as err:
        print(f"❌ Errore verifica tabelle: {err}")
        return False

    finally:
        cursor.close()
        conn.close()


def main():
    """Funzione principale"""
    print("🎮 Setup Database Birthday Game")
    print("=" * 40)

    # Verifica connessione
    print("🔍 Verifica connessione database...")
    conn = get_db_connection()
    if not conn:
        print("❌ Impossibile connettersi al database. Verifica la configurazione.")
        sys.exit(1)
    conn.close()
    print("✅ Connessione database OK")

    # Crea tabelle
    if not create_all_tables():
        print("❌ Errore durante la creazione tabelle")
        sys.exit(1)

    # Verifica tabelle
    if not check_tables():
        print("❌ Verifica tabelle fallita")
        sys.exit(1)

    # Inserisci dati di esempio
    if not insert_sample_data():
        print("❌ Errore inserimento dati di esempio")
        sys.exit(1)

    print("\n🎉 Setup completato con successo!")
    print("🎯 Il database è pronto per:")
    print("   • Quiz Personalizzati")
    print("   • Indovina Chi")
    print("   • Votazione Costumi")
    print("   • Gestione Giocatori")
    print("\nIl database è pronto per la tua festa! 🎂")


if __name__ == "__main__":
    main()