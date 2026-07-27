import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import uuid
import urllib.parse

# Configurazione Pagina
st.set_page_config(
    page_title="Nuova Proloco Torre San Patrizio",
    page_icon="🍷",
    layout="centered"
)

# Costanti di Configurazione
PREZZO_ADULTO = 60
PREZZO_BAMBINO = 25
CAPARRA_ADULTO = 30
CAPARRA_BAMBINO = 15

LISTA_OPERATORI = [
    "Alimentari Ribichini Coal",
    "Alimentari Villa Zara",
    "Proloco TSP",
    "Luigi Croceri",
    "Andrea Mazzoni",
    "Valentino Ianua'",
    "Valentino Seri",
    "Marco Monti",
    "Bar La Torre",
    "Bar Antonia",
    "Circolo Villa Zara"
]

# Connessione a Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

# Gestione Stato della Sessione (Login)
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.operatore = ""

# --- SCHERMATA DI LOGIN ---
if not st.session_state.logged_in:
    st.title("Nuova Proloco Torre San Patrizio")
    st.subheader("Cassa & Prenotazioni Cene")
    
    with st.form("login_form"):
        operatore_sel = st.selectbox("Seleziona Operatore / Esercente", [""] + LISTA_OPERATORI)
        pin_sel = st.text_input("PIN di Accesso", type="password")
        btn_login = st.form_submit_button("Accedi alla Cassa", use_container_width=True)
        
        if btn_login:
            if not operatore_sel:
                st.error("Seleziona un operatore prima di continuare.")
            elif not pin_sel:
                st.error("Inserisci il PIN di accesso.")
            else:
                st.session_state.logged_in = True
                st.session_state.operatore = operatore_sel
                st.rerun()

# --- SCHERMATA PRINCIPALE (GESTIONE PRENOTAZIONI) ---
else:
    # Header
    col_head1, col_head2 = st.columns([3, 1])
    with col_head1:
        st.title("CENA IN BIANCO")
        st.caption("Data Evento: 06/08/2026")
    with col_head2:
        st.write(f"👤 **{st.session_state.operatore}**")
        if st.button("Esci / Logout"):
            st.session_state.logged_in = False
            st.session_state.operatore = ""
            st.rerun()

    st.divider()

    st.subheader("✍️ Nuova Prenotazione")

    with st.form("prenotazione_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            cognome = st.text_input("Cognome *")
            telefono = st.text_input("Telefono / WhatsApp *")
            adulti = st.number_input("N° Adulti (€60)", min_value=0, value=1, step=1)
        with col2:
            nome = st.text_input("Nome *")
            email = st.text_input("Email (Opzionale)")
            bambini = st.number_input("N° Bambini (€25)", min_value=0, value=0, step=1)

        st.divider()

        # Calcolo automatico della caparra consigliata
        caparra_suggerita = (adulti * CAPARRA_ADULTO) + (bambini * CAPARRA_BAMBINO)
        
        col3, col4 = st.columns(2)
        with col3:
            blocchetto = st.text_input("N° Blocchetto / Ricevuta *", placeholder="Es. N° 045")
            metodo_pagamento = st.selectbox("Metodo Pagamento", ["Contanti", "POS/Carta", "Bonifico"])
        with col4:
            caparra_versata = st.number_input("Caparra Incassata (€)", min_value=0.0, value=float(caparra_suggerita), step=0.5)
            note = st.text_input("Note / Intolleranze", placeholder="Es. Vegetariano")

        st.info(f"💡 Caparra Consigliata: **€ {caparra_suggerita:.2f}**")

        btn_salva = st.form_submit_button("💾 Salva e Registra Prenotazione", use_container_width=True)

        if btn_salva:
            if not cognome or not nome or not telefono or not blocchetto:
                st.error("Compila tutti i campi obbligatori marcati con (*).")
            else:
                try:
                    # Elaborazione dati
                    cod_fam = "FAM-" + str(uuid.uuid4())[:5].upper()
                    richiesti = adulti + bambini
                    caparra_dovuta = (adulti * CAPARRA_ADULTO) + (bambini * CAPARRA_BAMBINO)
                    costo_totale = (adulti * PREZZO_ADULTO) + (bambini * PREZZO_BAMBINO)
                    saldo = costo_totale - caparra_versata
                    data_ora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

                    # Creazione DataFrame per inserimento
                    nuova_riga = pd.DataFrame([{
                        "CodFam": cod_fam,
                        "ID": "",
                        "Data": data_ora,
                        "Cognome": cognome,
                        "Nome": nome,
                        "Telefono": telefono,
                        "Adulti": adulti,
                        "Bambini": bambini,
                        "Totale": richiesti,
                        "Caparra Dovuta": caparra_dovuta,
                        "Caparra Versata": caparra_versata,
                        "Saldo": saldo,
                        "Pagamento": metodo_pagamento,
                        "Tavolo": "Da assegnare",
                        "Stato": "Confermata",
                        "Note": note,
                        "Blocchetto": blocchetto,
                        "Operatore": st.session_state.operatore
                    }])

                    # Lettura dati esistenti e aggiunta
                    df_esistente = conn.read(worksheet="PRENOTAZIONI", ttl=0)
                    df_aggiornato = pd.concat([df_esistente, nuova_riga], ignore_index=True)
                    
                    # Scrittura su Google Sheets
                    conn.update(worksheet="PRENOTAZIONI", data=df_aggiornato)

                    # Output di successo
                    st.success("✅ Prenotazione registrata con successo!")
                    
                    # Generazione Messaggio WhatsApp
                    tel_clean = ''.join(filter(str.isdigit, telefono))
                    if len(tel_clean) == 10:
                        tel_clean = "39" + tel_clean

                    msg_wa = (
                        f"*NUOVA PROLOCO TORRE SAN PATRIZIO*\n"
                        f"*Ricevuta Prenotazione: CENA IN BIANCO*\n\n"
                        f"Gentile *{nome} {cognome}*,\n"
                        f"Confermiamo la prenotazione effettuata presso *{st.session_state.operatore}*.\n\n"
                        f"📌 *Codice:* {cod_fam}\n"
                        f"🎟️ *Ricevuta N°:* {blocchetto}\n"
                        f"👥 *Partecipanti:* {adulti} Adulti, {bambini} Bambini\n"
                        f"💶 *Caparra Versata:* €{caparra_versata:.2f}\n\n"
                        f"Conservi questo messaggio. Ci vediamo alla serata!"
                    )
                    url_wa = f"https://api.whatsapp.com/send?phone={tel_clean}&text={urllib.parse.quote(msg_wa)}"

                    st.markdown(f'''
                        <a href="{url_wa}" target="_blank" style="text-decoration:none;">
                            <div style="background-color:#25D366;color:white;padding:12px;border-radius:8px;text-align:center;font-weight:bold;margin-top:10px;">
                                📲 Invia Conferma WhatsApp al Cliente
                            </div>
                        </a>
                    ''', unsafe_allow_html=True)

                except Exception as e:
                    st.error(f"Errore durante il salvataggio sul Google Sheet: {e}")
