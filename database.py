import sqlite3

def inizializza_db():
    """Crea il database e le tabelle se non esistono."""
    with sqlite3.connect('registro_lavoro.db') as conn:
        cursor = conn.cursor()
        
        # Tabella per i diversi lavori/clienti
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS lavori (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL UNIQUE
            )
        ''')
        
        # Tabella per le sessioni di lavoro effettive
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessioni (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lavoro_id INTEGER,
                data DATE NOT NULL,
                ore REAL NOT NULL,
                descrizione TEXT,
                FOREIGN KEY (lavoro_id) REFERENCES lavori (id)
            )
        ''')
        conn.commit()
    print("Database inizializzato correttamente!")

if __name__ == "__main__":
    inizializza_db()