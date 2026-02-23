import streamlit as st
import sqlite3
import pandas as pd
from datetime import date, datetime

# --- FUNZIONE DI INIZIALIZZAZIONE ---
def init_db():
    conn = sqlite3.connect('registro_lavoro.db')
    c = conn.cursor()
    # Crea la tabella lavori se non esiste
    c.execute('''CREATE TABLE IF NOT EXISTS lavori 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL)''')
    # Crea la tabella sessioni se non esiste
    c.execute('''CREATE TABLE IF NOT EXISTS sessioni 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, lavoro_id INTEGER, 
                  data TEXT, ore REAL, descrizione TEXT,
                  FOREIGN KEY (lavoro_id) REFERENCES lavori (id))''')
    conn.commit()
    conn.close()

# Esegui l'inizializzazione ogni volta che l'app parte
init_db()
conn.close()
