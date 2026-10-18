import os
import time
import sqlite3
import threading
from datetime import datetime, time as dtime
from flask import Flask
import telebot
from telebot import types

# ----------------------------------------------------
# 1. SERVEUR FLASK & GARDE-FOU RENDER
# ----------------------------------------------------
app = Flask(__name__)

@app.route('/')
def home():
    return "B2K Multi-Project Savings Bot est en ligne !"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", 10000)))

threading.Thread(target=run_flask, daemon=True).start()

# ----------------------------------------------------
# 2. INITIALISATION DE LA BASE DE DONNÉES SQLITE
# ----------------------------------------------------
def init_db():
    conn = sqlite3.connect("savings_v2.db", check_same_thread=False)
    cursor = conn.cursor()
    # Table des projets multiples par utilisateur
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS projects (
            project_id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            project_name TEXT,
            target_amount REAL,
            saved_amount REAL,
            daily_target REAL,
            notify_time TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# ----------------------------------------------------
# 3. CONFIGURATION DU BOT TELEGRAM
# ----------------------------------------------------
TOKEN = "8870329936:AAHxHlJH9qN6GG_vZ9jUPUiA4_JfeE6ni8E"
bot = telebot.TeleBot(TOKEN)

# États temporaires pour la création guidée d'un projet
user_states = {}

@bot.message_handler(commands=['start'])
def start_cmd(message):
    chat_id = message.chat.id
    show_main_menu(chat_id)

def show_main_menu(chat_id, message_id=None):
    conn = sqlite3.connect("savings_v2.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT project_id, project_name, target_amount, saved_amount, daily_target FROM projects WHERE chat_id=?", (chat_id,))
    projects = cursor.fetchall()
    conn.close()

    if not projects:
        start_new_project_wizard(chat_id)
        return

    text = (
        "🐷 **MES PROJETS D'ÉPARGNE B2K**\n"
        "───────────────────────────\n"
        "Sélectionne un projet ci-dessous pour voir ton tableau de bord ou en ajouter un nouveau :"
    )
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    for p in projects:
        pid, name, target, saved, daily = p
        progress = int((saved / target) * 100) if target > 0 else 0
        markup.add(types.InlineKeyboardButton(f"📁 {name} ({progress}% - {saved:,.0f}/{target:,.0f} HTG)", callback_data=f"select_proj_{pid}"))
    
    markup.add(types.InlineKeyboardButton("➕ Créer un nouveau projet d'épargne", callback_data="create_new"))

    if message_id:
        try:
            bot.edit_message_text(text, chat_id, message_id, parse_mode="Markdown", reply_markup=markup)
            return
        except:
            pass
    bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=markup)

# ----------------------------------------------------
# 4. ASSISTANT DE CRÉATION DE PROJET (WIZARD)
# ----------------------------------------------------
def start_new_project_wizard(chat_id):
    user_states[chat_id] = {'step': 'NAME'}
    text = (
        "🚀 **NOUVEAU PROJET D'ÉPARGNE**\n"
        "───────────────────────────\n"
        "✍️ **Écris le nom de ton projet :**\n"
        "*(Exemple: iPhone 16 Pro, Moto, Chambre)*"
    )
    bot.send_message(chat_id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.chat.id in user_states)
def handle_wizard(msg):
    chat_id = msg.chat.id
    state = user_states[chat_id]
    
    if state['step'] == 'NAME':
        state['name'] = msg.text
        state['step'] = 'TARGET'
        bot.send_message(chat_id, f"🎯 Quel est le **montant total en HTG** pour **{msg.text}** ?\n*(Exemple: 50000)*", parse_mode="Markdown")
        
    elif state['step'] == 'TARGET':
        try:
            state['target'] = float(msg.text.replace(" ", ""))
            state['step'] = 'DAILY'
            bot.send_message(chat_id, "💵 Combien veux-tu économiser **chaque jour** pour ce projet ?\n*(Exemple: 250)*", parse_mode="Markdown")
        except:
            bot.send_message(chat_id, "⚠️ Entre un montant valide en chiffres (ex: 50000).")

    elif state['step'] == 'DAILY':
        try:
            state['daily'] = float(msg.text.replace(" ", ""))
            state['step'] = 'TIME'
            bot.send_message(chat_id, "⏰ À quelle **heure** veux-tu recevoir ton rappel quotidien ?\n*(Écris au format HH:MM, par exemple: 09:00 ou 18:30)*", parse_mode="Markdown")
        except:
            bot.send_message(chat_id, "⚠️ Entre un montant journalier valide (ex: 250).")

    elif state['step'] == 'TIME':
        time_str = msg.text.strip()
        try:
            # Valide le format de l'heure
            datetime.strptime(time_str, "%H:%M")
            state['time'] = time_str
            
            # Enregistrement dans SQLite
            conn = sqlite3.connect("savings_v2.db", check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO projects (chat_id, project_name, target_amount, saved_amount, daily_target, notify_time)
                VALUES (?, ?, ?, 0, ?, ?)
            ''', (chat_id, state['name'], state['target'], state['daily'], state['time']))
            conn.commit()
            conn.close()
            
            proj_name = state['name']
            daily = state['daily']
            target = state['target']
            notif = state['time']
            
            del user_states[chat_id]
            
            text = (
                f"🎉 **PROJET CRÉÉ AVEC SUCCÈS !**\n"
                f"───────────────────────────\n"
                f"📌 **Projet :** {proj_name}\n"
                f"🎯 **Cible :** {target:,.0f} HTG\n"
                f"💵 **Mise quotidienne :** {daily:,.0f} HTG / jour\n"
                f"⏰ **Rappel quotidien réglé à :** {notif}\n\n"
                f"Tape /start pour voir ton tableau de bord."
            )
            bot.send_message(chat_id, text, parse_mode="Markdown")
        except ValueError:
            bot.send_message(chat_id, "⚠️ Format d'heure invalide. Utilise exactement le format **HH:MM** (ex: 09:00).")

# ----------------------------------------------------
# 5. GESTION DU TABLEAU DE BORD D'UN PROJET
# ----------------------------------------------------
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    data = call.data

    if data == "create_new":
        start_new_project_wizard(chat_id)
        return

    if data.startswith("select_proj_"):
        proj_id = int(data.split("_")[2])
        show_project_dashboard(chat_id, message_id, proj_id)
        return

    if data.startswith("pay_norm_"):
        proj_id = int(data.split("_")[2])
        conn = sqlite3.connect("savings_v2.db", check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT project_name, target_amount, saved_amount, daily_target FROM projects WHERE project_id=?", (proj_id,))
        proj = cursor.fetchone()
        if proj:
            name, target, saved, daily = proj
            new_saved = saved + daily
            cursor.execute("UPDATE projects SET saved_amount=? WHERE project_id=?", (new_saved, proj_id))
            conn.commit()
            bot.answer_callback_query(call.id, f"✅ +{daily:,.0f} HTG validés pour aujourd'hui !")
        conn.close()
        show_project_dashboard(chat_id, message_id, proj_id)
        return

    if data.startswith("pay_bonus_"):
        proj_id = int(data.split("_")[2])
        # Demande de bonus personnalisé
        user_states[chat_id] = {'step': 'BONUS_AMT', 'proj_id': proj_id}
        bot.send_message(chat_id, "💰 **Ajouter un bonus (ex: 500 HTG)**\n*(Rappelle-toi : ce bonus fait baisser ton objectif global, mais n'annule pas ta mise quotidienne de demain !)*\n\n✍️ **Écris le montant du bonus en chiffres :**", parse_mode="Markdown")
        return

    if data.startswith("analyze_"):
        proj_id = int(data.split("_")[2])
        conn = sqlite3.connect("savings_v2.db", check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT project_name, target_amount, saved_amount, daily_target FROM projects WHERE project_id=?", (proj_id,))
        proj = cursor.fetchone()
        conn.close()
        
        if proj:
            name, target, saved, daily = proj
            remaining = max(0, target - saved)
            sim_1w = saved + (daily * 7)
            sim_1m = saved + (daily * 30)
            
            text = (
                f"📊 **ANALYSE : {name}**\n"
                f"───────────────────────────\n"
                f"🎯 **Cible totale :** {target:,.0f} HTG\n"
                f"💵 **Déjà épargné :** {saved:,.0f} HTG\n"
                f"⏳ **Reste à mettre :** {remaining:,.0f} HTG\n\n"
                f"🔮 **Projections si tu restes régulier ({daily:,.0f} HTG/jour) :**\n"
                f"• Dans **1 semaine** : {min(target, sim_1w):,.0f} HTG\n"
                f"• Dans **1 mois** : {min(target, sim_1m):,.0f} HTG\n\n"
                f"💡 *Chaque bonus que tu ajoutes accélère ta victoire finale !*"
            )
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 Retour au projet", callback_data=f"select_proj_{proj_id}"))
            bot.edit_message_text(text, chat_id, message_id, parse_mode="Markdown", reply_markup=markup)
        return

    if data == "back_home":
        show_main_menu(chat_id, message_id)
        return

def show_project_dashboard(chat_id, message_id, proj_id):
    conn = sqlite3.connect("savings_v2.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT project_name, target_amount, saved_amount, daily_target, notify_time FROM projects WHERE project_id=?", (proj_id,))
    proj = cursor.fetchone()
    conn.close()

    if not proj:
        show_main_menu(chat_id, message_id)
        return

    name, target, saved, daily, notif_time = proj
    remaining = max(0, target - saved)
    progress = int((saved / target) * 100) if target > 0 else 0

    text = (
        f"🎯 **PROJET : {name}**\n"
        f"───────────────────────────\n"
        f"💰 **Objectif Total :** {target:,.0f} HTG\n"
        f"💵 **Déjà Économisé :** {saved:,.0f} HTG ({progress}%)\n"
        f"⏳ **Reste à mettre :** {remaining:,.0f} HTG\n"
        f"📌 **Mise quotidienne :** {daily:,.0f} HTG / jour\n"
        f"⏰ **Rappel quotidien :** {notif_time}\n\n"
        f"👇 *Que veux-tu faire aujourd'hui ?*"
    )

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(f"✅ Valider ma mise ({daily:,.0f} HTG)", callback_data=f"pay_norm_{proj_id}"),
        types.InlineKeyboardButton("🔥 Ajouter un bonus (ex: 500 HTG)", callback_data=f"pay_bonus_{proj_id}"),
        types.InlineKeyboardButton("📊 Analyser & Prévisions", callback_data=f"analyze_{proj_id}"),
        types.InlineKeyboardButton("🔙 Retour à mes projets", callback_data="back_home")
    )

    try:
        bot.edit_message_text(text, chat_id, message_id, parse_mode="Markdown", reply_markup=markup)
    except:
        bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=markup)

# Gestion du texte pour l'ajout d'un bonus personnalisé
@bot.message_handler(func=lambda msg: msg.chat.id in user_states and user_states[msg.chat.id].get('step') == 'BONUS_AMT')
def handle_bonus_input(msg):
    chat_id = msg.chat.id
    state = user_states[chat_id]
    proj_id = state['proj_id']
    
    try:
        bonus_amt = float(msg.text.replace(" ", ""))
        conn = sqlite3.connect("savings_v2.db", check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("UPDATE projects SET saved_amount = saved_amount + ? WHERE project_id=?", (bonus_amt, proj_id))
        conn.commit()
        conn.close()
        
        del user_states[chat_id]
        bot.send_message(chat_id, f"🔥 **SUPER BONUS AJOUTÉ !**\n+{bonus_amt:,.0f} HTG enregistrés avec succès.\n\n*(Note : Ta mise quotidienne normale reste inchangée pour demain !)*", parse_mode="Markdown")
        show_main_menu(chat_id)
    except:
        bot.send_message(chat_id, "⚠️ Entre un montant de bonus valide en chiffres (ex: 500).")

# ----------------------------------------------------
# 6. LANCEMENT DU BOT
# ----------------------------------------------------
if __name__ == '__main__':
    bot.remove_webhook()
    time.sleep(1)
    bot.infinity_polling(skip_pending=True)
