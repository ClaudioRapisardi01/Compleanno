#!/usr/bin/env python3
"""
Script per setup automatico del database birthday_game
Esegui questo script per creare tutte le tabelle necessarie
"""

import mysql.connector
import sys

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


def create_tables():
    """Crea tutte le tabelle necessarie"""

    # SQL per creare le tabelle
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
                UNIQUE KEY unique_persona_ordine (persona_id, ordine)
            )
        """,

        'indovina_partite': """
            CREATE TABLE IF NOT EXISTS indovina_partite (
                id INT AUTO_INCREMENT PRIMARY KEY,
                persona_id INT NOT NULL,
                indizio_corrente INT DEFAULT 1,
                stato ENUM('attiva', 'completata', 'annullata') DEFAULT 'attiva',
                tempo_inizio TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                tempo_fine TIMESTAMP NULL,
                FOREIGN KEY (persona_id) REFERENCES indovina_persone(id) ON DELETE CASCADE
            )
        """,

        'indovina_risposte': """
            CREATE TABLE IF NOT EXISTS indovina_risposte (
                id INT AUTO_INCREMENT PRIMARY KEY,
                partita_id INT NOT NULL,
                giocatore_id INT NOT NULL,
                risposta VARCHAR(255) NOT NULL,
                indizio_numero INT NOT NULL,
                corretta BOOLEAN DEFAULT FALSE,
                punti_ottenuti INT DEFAULT 0,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (partita_id) REFERENCES indovina_partite(id) ON DELETE CASCADE,
                FOREIGN KEY (giocatore_id) REFERENCES giocatori(id) ON DELETE CASCADE,
                UNIQUE KEY unique_risposta_per_indizio (partita_id, giocatore_id, indizio_numero)
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
            'partecipazioni', 'quiz_domande', 'indovina_persone',
            'indovina_indizi', 'indovina_partite', 'indovina_risposte',
            'disconnessioni', 'esclusioni_gioco'
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
        print("✅ Setup database completato con successo!")
        return True

    except mysql.connector.Error as err:
        print(f"❌ Errore durante la creazione tabelle: {err}")
        conn.rollback()
        return False

    finally:
        cursor.close()
        conn.close()


def check_tables():
    """Verifica che tutte le tabelle esistano"""
    required_tables = [
        'personaggi', 'giocatori', 'foto_profili', 'stato_gioco',
        'partecipazioni', 'quiz_domande', 'indovina_persone',
        'indovina_indizi', 'indovina_partite', 'indovina_risposte',
        'disconnessioni', 'esclusioni_gioco'
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


def insert_sample_data():
    """Inserisce dati di esempio se le tabelle sono vuote"""
    conn = get_db_connection()
    if not conn:
        return False

    cursor = conn.cursor()

    try:
        # Verifica se ci sono già dati
        cursor.execute("SELECT COUNT(*) FROM personaggi")
        if cursor.fetchone()[0] > 0:
            print("ℹ️ Dati già presenti, skip inserimento dati di esempio")
            return True

        print("📊 Inserimento dati di esempio...")

        # Inserisci personaggi di esempio
        personaggi_esempio = [
            ('🦸 Supereroe', 'Un personaggio con superpoteri incredibili'),
            ('🕵️ Detective', 'Un investigatore privato molto astuto'),
            ('👑 Regina/Re', 'Una figura regale e maestosa'),
            ('🎭 Attore/Attrice', 'Una star del cinema e del teatro'),
            ('🧙 Mago/Strega', 'Un personaggio magico con poteri misteriosi'),
            ('🤖 Robot', 'Un androide del futuro'),
            ('🦹 Villain', 'Il cattivo della storia'),
            ('👨‍🚀 Astronauta', 'Un esploratore dello spazio'),
            ('🧟 Zombie', 'Un non-morto affamato di cervelli'),
            ('🦄 Creatura Magica', 'Un essere fantastico e colorato')
        ]

        cursor.executemany("""
            INSERT INTO personaggi (nome, descrizione) VALUES (%s, %s)
        """, personaggi_esempio)

        # Inserisci domande quiz di esempio
        domande_esempio = [
            ('Qual è il colore preferito del festeggiato?', 'Blu', 'Rosso', 'Verde', 'Nero', 'a', 'personale'),
            ('In che anno è nato il festeggiato?', '1990', '1995', '1988', '1992', 'c', 'personale'),
            ('Qual è il suo film preferito?', 'Inception', 'Avatar', 'Titanic', 'Matrix', 'b', 'personale'),
            ('Quale sport pratica di più?', 'Calcio', 'Tennis', 'Nuoto', 'Palestra', 'd', 'personale'),
            ('Qual è la sua pizza preferita?', 'Margherita', 'Quattro stagioni', 'Marinara', 'Capricciosa', 'a',
             'personale')
        ]

        cursor.executemany("""
            INSERT INTO quiz_domande (domanda, opzione_a, opzione_b, opzione_c, opzione_d, risposta_corretta, categoria) 
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, domande_esempio)

        # Inserisci persone per Indovina Chi
        persone_esempio = [
            ('Marco Rossi', 'Un amico di lunga data del festeggiato'),
            ('Laura Bianchi', 'Collega di lavoro molto simpatica'),
            ('Giuseppe Verdi', 'Il vicino di casa sempre disponibile'),
            ('Anna Neri', 'Amica dell\'università'),
            ('Francesco Blu', 'Compagno di squadra di calcetto')
        ]

        cursor.executemany("""
            INSERT INTO indovina_persone (nome, descrizione) VALUES (%s, %s)
        """, persone_esempio)

        # Inserisci indizi di esempio per la prima persona
        indizi_esempio = [
            (1, 'Questa persona lavora nel settore IT', 1, 50),
            (1, 'Ha i capelli castani e porta sempre gli occhiali', 2, 40),
            (1, 'È nato nello stesso anno del festeggiato', 3, 30),
            (1, 'Suona la chitarra nel tempo libero', 4, 20),
            (1, 'È il migliore amico del festeggiato dalle superiori', 5, 10)
        ]

        cursor.executemany("""
            INSERT INTO indovina_indizi (persona_id, indizio, ordine, punti) VALUES (%s, %s, %s, %s)
        """, indizi_esempio)

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
    if not create_tables():
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
    print("Il database è pronto per l'utilizzo.")


if __name__ == "__main__":
    main()