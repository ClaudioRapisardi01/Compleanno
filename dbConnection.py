#!/usr/bin/env python3
"""
Script completo per setup database birthday_game con supporto Lupus in Fabula
Aggiorna il tuo dbConnection.py con questo codice
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
    """Crea tutte le tabelle necessarie incluso Lupus"""

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
        """,

        # TABELLE LUPUS IN FABULA
        'lupus_ruoli': """
            CREATE TABLE IF NOT EXISTS lupus_ruoli (
                id INT AUTO_INCREMENT PRIMARY KEY,
                nome VARCHAR(100) NOT NULL UNIQUE,
                emoji VARCHAR(10) DEFAULT '🎭',
                team ENUM('lupi', 'cittadini', 'neutral') NOT NULL,
                descrizione TEXT,
                azione_notturna BOOLEAN DEFAULT FALSE,
                azione_diurna BOOLEAN DEFAULT FALSE,
                priorita_azione INT DEFAULT 5,
                attivo BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """,

        'lupus_configurazioni': """
            CREATE TABLE IF NOT EXISTS lupus_configurazioni (
                id INT AUTO_INCREMENT PRIMARY KEY,
                nome_config VARCHAR(100) NOT NULL,
                descrizione TEXT,
                min_giocatori INT DEFAULT 6,
                max_giocatori INT DEFAULT 20,
                durata_notte_secondi INT DEFAULT 120,
                durata_giorno_secondi INT DEFAULT 180,
                durata_votazione_secondi INT DEFAULT 90,
                ruoli_configurazione JSON,
                attiva BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """,

        'lupus_partite': """
            CREATE TABLE IF NOT EXISTS lupus_partite (
                id INT AUTO_INCREMENT PRIMARY KEY,
                stato ENUM('waiting', 'in_progress', 'ended') DEFAULT 'waiting',
                fase_corrente ENUM('setup', 'night', 'day', 'voting', 'ended') DEFAULT 'setup',
                tempo_fase_inizio TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                durata_fase_secondi INT DEFAULT 120,
                turno_numero INT DEFAULT 1,
                vincitore ENUM('lupi', 'cittadini', 'neutral') NULL,
                config_utilizzata INT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (config_utilizzata) REFERENCES lupus_configurazioni(id) ON DELETE SET NULL
            )
        """,

        'lupus_partecipazioni': """
            CREATE TABLE IF NOT EXISTS lupus_partecipazioni (
                id INT AUTO_INCREMENT PRIMARY KEY,
                partita_id INT NOT NULL,
                giocatore_id INT NOT NULL,
                ruolo_id INT NOT NULL,
                stato ENUM('vivo', 'morto', 'eliminato') DEFAULT 'vivo',
                morte_turno INT NULL,
                morte_fase ENUM('notte', 'votazione') NULL,
                simulato BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (partita_id) REFERENCES lupus_partite(id) ON DELETE CASCADE,
                FOREIGN KEY (giocatore_id) REFERENCES giocatori(id) ON DELETE CASCADE,
                FOREIGN KEY (ruolo_id) REFERENCES lupus_ruoli(id) ON DELETE CASCADE,
                UNIQUE KEY unique_partita_giocatore (partita_id, giocatore_id)
            )
        """,

        'lupus_azioni': """
            CREATE TABLE IF NOT EXISTS lupus_azioni (
                id INT AUTO_INCREMENT PRIMARY KEY,
                partita_id INT NOT NULL,
                turno INT NOT NULL,
                fase ENUM('notte', 'giorno') NOT NULL,
                giocatore_id INT NOT NULL,
                tipo_azione ENUM('kill', 'protect', 'investigate', 'heal', 'block') NOT NULL,
                target_giocatore_id INT,
                successo BOOLEAN DEFAULT FALSE,
                risultato VARCHAR(255),
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (partita_id) REFERENCES lupus_partite(id) ON DELETE CASCADE,
                FOREIGN KEY (giocatore_id) REFERENCES giocatori(id) ON DELETE CASCADE,
                FOREIGN KEY (target_giocatore_id) REFERENCES giocatori(id) ON DELETE CASCADE,
                UNIQUE KEY unique_action_per_turno (partita_id, turno, giocatore_id, fase)
            )
        """,

        'lupus_votazioni': """
            CREATE TABLE IF NOT EXISTS lupus_votazioni (
                id INT AUTO_INCREMENT PRIMARY KEY,
                partita_id INT NOT NULL,
                turno INT NOT NULL,
                votante_giocatore_id INT NOT NULL,
                votato_giocatore_id INT NOT NULL,
                peso_voto INT DEFAULT 1,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (partita_id) REFERENCES lupus_partite(id) ON DELETE CASCADE,
                FOREIGN KEY (votante_giocatore_id) REFERENCES giocatori(id) ON DELETE CASCADE,
                FOREIGN KEY (votato_giocatore_id) REFERENCES giocatori(id) ON DELETE CASCADE,
                UNIQUE KEY unique_voto_per_turno (partita_id, turno, votante_giocatore_id)
            )
        """,

        'lupus_eventi': """
            CREATE TABLE IF NOT EXISTS lupus_eventi (
                id INT AUTO_INCREMENT PRIMARY KEY,
                partita_id INT NOT NULL,
                turno INT NOT NULL,
                fase ENUM('setup', 'notte', 'giorno', 'votazione') NOT NULL,
                tipo_evento ENUM('cambio_fase', 'morte', 'eliminazione', 'investigazione', 'protezione', 'victory') NOT NULL,
                descrizione TEXT,
                giocatori_coinvolti JSON,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (partita_id) REFERENCES lupus_partite(id) ON DELETE CASCADE
            )
        """,

        'lupus_bots': """
            CREATE TABLE IF NOT EXISTS lupus_bots (
                id INT AUTO_INCREMENT PRIMARY KEY,
                nome VARCHAR(100) NOT NULL,
                emoji VARCHAR(10) DEFAULT '🤖',
                personalita ENUM('aggressivo', 'difensivo', 'casuale', 'intelligente') DEFAULT 'casuale',
                attivo BOOLEAN DEFAULT TRUE
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
            'disconnessioni', 'esclusioni_gioco', 'lupus_ruoli',
            'lupus_configurazioni', 'lupus_partite', 'lupus_partecipazioni',
            'lupus_azioni', 'lupus_votazioni', 'lupus_eventi', 'lupus_bots'
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
        print(f"❌ Errore durante la creazione tabelle: {err}")
        conn.rollback()
        return False

    finally:
        cursor.close()
        conn.close()


def insert_lupus_data():
    """Inserisce dati iniziali per Lupus in Fabula"""
    conn = get_db_connection()
    if not conn:
        return False

    cursor = conn.cursor()

    try:
        print("🐺 Inserimento dati Lupus in Fabula...")

        # Inserisci ruoli base
        ruoli_lupus = [
            ('Lupo', '🐺', 'lupi', 'Elimina un cittadino ogni notte', True, 8),
            ('Lupo Alpha', '🐺👑', 'lupi', 'Lupo leader con capacità speciali', True, 9),
            ('Cittadino', '👤', 'cittadini', 'Vince se elimina tutti i lupi', False, 5),
            ('Veggente', '🔮', 'cittadini', 'Può investigare il ruolo di un giocatore ogni notte', True, 10),
            ('Guardia', '🛡️', 'cittadini', 'Può proteggere un giocatore ogni notte', True, 9),
            ('Medico', '⚕️', 'cittadini', 'Può curare un giocatore ferito', True, 7),
            ('Sindaco', '🏛️', 'cittadini', 'Il suo voto vale doppio', False, 5),
            ('Cacciatore', '🏹', 'cittadini', 'Quando muore può eliminare un altro giocatore', False, 6),
            ('Strega', '🧙‍♀️', 'cittadini', 'Ha una pozione di vita e una di morte', True, 8),
            ('Cupido', '💘', 'neutral', 'Crea una coppia di innamorati all\'inizio', True, 11),
            ('Innamorato', '💕', 'neutral', 'Muore se muore il partner', False, 5),
            ('Idiota del Villaggio', '🤪', 'cittadini', 'Non può essere eliminato al primo voto', False, 5)
        ]

        cursor.executemany("""
            INSERT IGNORE INTO lupus_ruoli (nome, emoji, team, descrizione, azione_notturna, priorita_azione) 
            VALUES (%s, %s, %s, %s, %s, %s)
        """, ruoli_lupus)

        # Inserisci configurazioni predefinite
        configurazioni = [
            ('Mini (3-4 giocatori)', 'Configurazione per test con pochi giocatori', 3, 4, 60, 90, 60,
             json.dumps({"Lupo": 1, "Veggente": 1, "Cittadino": 2})),
            ('Piccola (5-6)', 'Partita veloce per principianti', 5, 6, 90, 120, 60,
             json.dumps({"Lupo": 1, "Veggente": 1, "Guardia": 1, "Cittadino": 3})),
            ('Media (7-10)', 'Partita standard', 7, 10, 120, 150, 90,
             json.dumps({"Lupo": 2, "Veggente": 1, "Guardia": 1, "Sindaco": 1, "Cittadino": 4})),
            ('Grande (11-16)', 'Partita con molti ruoli', 11, 16, 120, 180, 90,
             json.dumps(
                 {"Lupo": 3, "Lupo Alpha": 1, "Veggente": 1, "Guardia": 1, "Medico": 1, "Sindaco": 1, "Cacciatore": 1,
                  "Cittadino": 6})),
            ('Enorme (17-25)', 'Per grandi gruppi', 17, 25, 150, 200, 120,
             json.dumps(
                 {"Lupo": 4, "Lupo Alpha": 1, "Veggente": 1, "Guardia": 1, "Medico": 1, "Sindaco": 1, "Cacciatore": 1,
                  "Strega": 1, "Cittadino": 14})),
            ('Mega (26-40)', 'Per feste enormi come la tua!', 26, 40, 180, 240, 150,
             json.dumps(
                 {"Lupo": 6, "Lupo Alpha": 1, "Veggente": 2, "Guardia": 2, "Medico": 1, "Sindaco": 1, "Cacciatore": 1,
                  "Strega": 1, "Cupido": 1, "Cittadino": 24}))
        ]

        cursor.executemany("""
            INSERT IGNORE INTO lupus_configurazioni 
            (nome_config, descrizione, min_giocatori, max_giocatori, durata_notte_secondi, durata_giorno_secondi, durata_votazione_secondi, ruoli_configurazione)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, configurazioni)

        # Inserisci bot per simulazioni
        bots = [
            ('🤖 Bot Marco', '🤖', 'intelligente'),
            ('🤖 Bot Laura', '🤖', 'difensivo'),
            ('🤖 Bot Giuseppe', '🤖', 'aggressivo'),
            ('🤖 Bot Anna', '🤖', 'casuale'),
            ('🤖 Bot Francesco', '🤖', 'intelligente'),
            ('🤖 Bot Maria', '🤖', 'difensivo'),
            ('🤖 Bot Luigi', '🤖', 'aggressivo'),
            ('🤖 Bot Sara', '🤖', 'casuale'),
            ('🤖 Bot Antonio', '🤖', 'intelligente'),
            ('🤖 Bot Elena', '🤖', 'difensivo'),
            ('🤖 Bot Roberto', '🤖', 'aggressivo'),
            ('🤖 Bot Giulia', '🤖', 'casuale'),
            ('🤖 Bot Alessandro', '🤖', 'intelligente'),
            ('🤖 Bot Chiara', '🤖', 'difensivo'),
            ('🤖 Bot Matteo', '🤖', 'aggressivo'),
            ('🤖 Bot Federica', '🤖', 'casuale')
        ]

        cursor.executemany("""
            INSERT IGNORE INTO lupus_bots (nome, emoji, personalita) 
            VALUES (%s, %s, %s)
        """, bots)

        conn.commit()
        print("✅ Dati Lupus inseriti con successo!")

        # Verifica inserimento
        cursor.execute("SELECT COUNT(*) FROM lupus_ruoli WHERE attivo = TRUE")
        ruoli_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM lupus_configurazioni WHERE attiva = TRUE")
        config_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM lupus_bots WHERE attivo = TRUE")
        bots_count = cursor.fetchone()[0]

        print(f"📊 Inseriti: {ruoli_count} ruoli, {config_count} configurazioni, {bots_count} bot")
        return True

    except mysql.connector.Error as err:
        print(f"❌ Errore inserimento dati Lupus: {err}")
        conn.rollback()
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
            ('🦄 Creatura Magica', 'Un essere fantastico e colorato'),
            ('🐱‍👤 Ninja', 'Un guerriero delle ombre'),
            ('🏴‍☠️ Pirata', 'Un avventuriero dei sette mari'),
            ('🧚‍♀️ Fata', 'Una creatura magica benefica'),
            ('🦸‍♀️ Supereroina', 'Una donna con poteri straordinari'),
            ('🤴 Principe', 'Un nobile di stirpe reale')
        ]

        cursor.executemany("""
            INSERT INTO personaggi (nome, descrizione) VALUES (%s, %s)
        """, personaggi_esempio)

        # Inserisci domande quiz di esempio (specifiche per compleanno)
        domande_esempio = [
            ('Qual è il colore preferito del festeggiato?', 'Blu', 'Rosso', 'Verde', 'Nero', 'a', 'personale'),
            ('In che anno è nato il festeggiato?', '1990', '1995', '1988', '1992', 'c', 'personale'),
            ('Qual è il suo film preferito?', 'Inception', 'Avatar', 'Titanic', 'Matrix', 'b', 'personale'),
            ('Quale sport pratica di più?', 'Calcio', 'Tennis', 'Nuoto', 'Palestra', 'd', 'personale'),
            ('Qual è la sua pizza preferita?', 'Margherita', 'Quattro stagioni', 'Marinara', 'Capricciosa', 'a',
             'personale'),
            ('Dove è nato il festeggiato?', 'Roma', 'Milano', 'Napoli', 'Torino', 'a', 'personale'),
            ('Qual è il suo hobby principale?', 'Lettura', 'Videogiochi', 'Cucina', 'Fotografia', 'b', 'personale'),
            ('Che lavoro fa?', 'Ingegnere', 'Medico', 'Insegnante', 'Programmatore', 'd', 'personale'),
            ('Qual è la sua stagione preferita?', 'Primavera', 'Estate', 'Autunno', 'Inverno', 'b', 'personale'),
            ('Quanti fratelli/sorelle ha?', '0', '1', '2', '3', 'b', 'personale')
        ]

        cursor.executemany("""
            INSERT INTO quiz_domande (domanda, opzione_a, opzione_b, opzione_c, opzione_d, risposta_corretta, categoria) 
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, domande_esempio)

        # Inserisci persone per Indovina Chi (amici/familiari del festeggiato)
        persone_esempio = [
            ('Marco Rossi', 'Un amico di lunga data del festeggiato, sempre pronto a scherzare'),
            ('Laura Bianchi', 'Collega di lavoro molto simpatica e organizzata'),
            ('Giuseppe Verdi', 'Il vicino di casa sempre disponibile ad aiutare'),
            ('Anna Neri', 'Amica dell\'università con cui condivide tante avventure'),
            ('Francesco Blu', 'Compagno di squadra di calcetto e partner di allenamento'),
            ('Maria Gialli', 'Cugina del festeggiato, chef in erba e amante dei viaggi'),
            ('Roberto Grigi', 'Amico di famiglia, appassionato di tecnologia'),
            ('Elena Viola', 'Collega e amica, esperta di arte e cultura')
        ]

        cursor.executemany("""
            INSERT INTO indovina_persone (nome, descrizione) VALUES (%s, %s)
        """, persone_esempio)

        # Inserisci indizi di esempio per le prime persone
        indizi_esempio = [
            (1, 'Questa persona lavora nel settore IT e ama i videogiochi', 1, 50),
            (1, 'Ha i capelli castani e porta sempre gli occhiali da vista', 2, 40),
            (1, 'È nato nello stesso anno del festeggiato e condivide la passione per il calcio', 3, 30),
            (1, 'Suona la chitarra nel tempo libero e ha una band amatoriale', 4, 20),
            (1, 'È il migliore amico del festeggiato dalle scuole superiori', 5, 10),

            (2, 'Lavora nello stesso ufficio del festeggiato da 3 anni', 1, 50),
            (2, 'È sempre puntualissima e organizza tutti gli eventi aziendali', 2, 40),
            (2, 'Ha una laurea in economia e parla fluentemente inglese', 3, 30),
            (2, 'Ama la palestra e pratica yoga ogni mattina', 4, 20),
            (2, 'È diventata amica del festeggiato durante un progetto di lavoro', 5, 10),

            (3, 'Vive nella casa accanto a quella del festeggiato', 1, 50),
            (3, 'Ha un bellissimo giardino pieno di fiori e verdure', 2, 40),
            (3, 'È pensionato e dedica molto tempo ai suoi nipoti', 3, 30),
            (3, 'Ogni domenica mattina lava la macchina nel cortile', 4, 20),
            (3, 'Ha le chiavi di casa del festeggiato per le emergenze', 5, 10)
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


def check_tables():
    """Verifica che tutte le tabelle esistano"""
    required_tables = [
        'personaggi', 'giocatori', 'foto_profili', 'stato_gioco',
        'partecipazioni', 'quiz_domande', 'indovina_persone',
        'indovina_indizi', 'indovina_partite', 'indovina_risposte',
        'disconnessioni', 'esclusioni_gioco', 'lupus_ruoli',
        'lupus_configurazioni', 'lupus_partite', 'lupus_partecipazioni',
        'lupus_azioni', 'lupus_votazioni', 'lupus_eventi', 'lupus_bots'
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
    print("🎮 Setup Completo Database Birthday Game + Lupus in Fabula")
    print("=" * 60)

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

    # Inserisci dati Lupus
    if not insert_lupus_data():
        print("❌ Errore inserimento dati Lupus")
        sys.exit(1)

    # Inserisci dati di esempio
    if not insert_sample_data():
        print("❌ Errore inserimento dati di esempio")
        sys.exit(1)

    print("\n🎉 Setup completato con successo!")
    print("🐺 Lupus in Fabula è ora configurato e supporta:")
    print("   • Da 3 a 40+ giocatori")
    print("   • Bot automatici per simulazione")
    print("   • 6 configurazioni predefinite")
    print("   • 12 ruoli diversi")
    print("   • Gestione automatica delle fasi")
    print("\nIl database è pronto per la tua festa! 🎂")


if __name__ == "__main__":
    main()