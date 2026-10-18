import os
import time
import sqlite3
from flask import Flask
from threading import Thread
import telebot
from telebot import types

# ----------------------------------------------------
# 1. SERVEUR FLASK & GARDE-FOU RENDER
# ----------------------------------------------------
app = Flask(__name__)

@app.route('/')
def home():
    return "B2K Save Coach Bot est en ligne et fonctionnel 24/7 !"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", 10000)))

Thread(target=run_flask, daemon=True).start()

# ----------------------------------------------------
# 2. INITIALISATION BASE DE DONNÉES SQLITE
# ----------------------------------------------------
def init_db():
    conn = sqlite3.connect("savings.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            chat_id INTEGER PRIMARY KEY,
            project_name TEXT,
            target_amount REAL,
            saved_amount REAL,
            daily_target REAL,
            days_total INTEGER
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# ----------------------------------------------------
# 3. BOT TELEGRAM & LOGIQUE INTERACTIVE
# ----------------------------------------------------
TOKEN = "8870329936:AAHxHlJH9qN6GG_vZ9jUPUiA4_JfeE6ni8E"
bot = telebot.TeleBot(TOKEN)

# Dictionnaire temporaire pour la création de projet
user_states = {}

@bot.message_handler(commands=['start'])
def start_cmd(message):
    chat_id = message.chat.id
    
    conn = sqlite3.connect("savings.db")
    cursor = conn.cursor()
    cursor.execute("SELECT project_name, target_amount, saved_amount, daily_target FROM users WHERE chat_id=?", (chat_id,))
    user = cursor.fetchone()
    conn.close()

    if user:
        project, target, saved, daily = user
        remaining = max(0, target - saved)
        progress = int((saved / target) * 100) if target > 0 else 0
        
        text = (
            f"🐷 **COACH ÉPARGNE B2K | TABLEAU DE BORD**\n"
            f"───────────────────────────\n"
            f"🎯 **Projet en cours :** {project}\n"
            f"💰 **Objectif Total :** {target:,.0f} HTG\n"
            f"💵 **Déjà Économisé :** {saved:,.0f} HTG ({progress}%)\n"
            f"⏳ **Reste à mettre :** {remaining:,.0f} HTG\n"
            f"📌 **Cible quotidienne :** ~{daily:,.0f} HTG / jour\n\n"
            f"👇 *Que veux-tu faire aujourd'hui ?*"
        )
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton(f"✅ Valider ma mise ({daily:,.0f} HTG)", callback_data="pay_normal"),
            types.InlineKeyboardButton("🔥 Payer le Double (Avancer plus vite)", callback_data="pay_double"),
            types.InlineKeyboardButton("📊 Analyser & Simuler mes résultats", callback_data="analyze"),
            types.InlineKeyboardButton("⚙️ Créer un nouveau projet", callback_data="new_project")
        )
        bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=markup)
    else:
        ask_new_project(chat_id)

def ask_new_project(chat_id):
    user_states[chat_id] = {'step': 'NAME'}
    text = (
        "🚀 **BIENVENUE DANS B2K SAVE COACH !**\n"
        "───────────────────────────\n"
        "Je vais t'aider à économiser pour réaliser tes projets (iPhone, Matériel, Épargne).\n\n"
        "✍️ **Écris-moi le nom de ton projet :**\n"
        "*(Exemple: iPhone 14, Ma Chambre, Moto)*"
    )
    bot.send_message(chat_id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.chat.id in user_states)
def handle_setup_steps(msg):
    chat_id = msg.chat.id
    state = user_states[chat_id]
    
    if state['step'] == 'NAME':
        state['project_name'] = msg.text
        state['step'] = 'TARGET'
        bot.send_message(chat_id, f"🎯 Quel est le **montant total en Gourdes (HTG)** nécessaire pour **{msg.text}** ?\n*(Exemple: 50000)*", parse_mode="Markdown")
        
    elif state['step'] == 'TARGET':
        try:
            target = float(msg.text.replace(" ", ""))
            state['target_amount'] = target
            state['step'] = 'DAYS'
            bot.send_message(chat_id, "⏱️ En **combien de jours** veux-tu atteindre cet objectif ?\n*(Exemple: 30 pour 1 mois, 60 pour 2 mois, 7 pour 1 semaine)*", parse_mode="Markdown")
        except:
            bot.send_message(chat_id, "⚠️ Réponds avec un nombre valide (ex: 50000).")

    elif state['step'] == 'DAYS':
        try:
            days = int(msg.text)
            target = state['target_amount']
            daily = target / days
            project = state['project_name']
            
            # Enregistrement SQL
            conn = sqlite3.connect("savings.db")
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO users (chat_id, project_name, target_amount, saved_amount, daily_target, days_total)
                VALUES (?, ?, ?, 0, ?, ?)
            ''', (chat_id, project, target, daily, days))
            conn.commit()
            conn.close()
            
            del user_states[chat_id]
            
            text = (
                f"🎉 **PROJET CONFIGURÉ AVEC SUCCÈS !**\n"
                f"───────────────────────────\n"
                f"📌 **Projet :** {project}\n"
                f"🎯 **Cible :** {target:,.0f} HTG en {days} jours\n"
                f"💡 **Mise quotidienne calculée :** {daily:,.0f} HTG / jour\n\n"
                f"Rappelle-toi : la régularité est la clé ! Tape /start pour ouvrir ton tableau de bord."
            )
            bot.send_message(chat_id, text, parse_mode="Markdown")
        except:
            bot.send_message(chat_id, "⚠️ Réponds avec un nombre de jours valide (ex: 60).")

# ----------------------------------------------------
# 4. GESTION DES ACTIONS ET DES BOUTONS
# ----------------------------------------------------
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    data = call.data

    conn = sqlite3.connect("savings.db")
    cursor = conn.cursor()
    cursor.execute("SELECT project_name, target_amount, saved_amount, daily_target FROM users WHERE chat_id=?", (chat_id,))
    user = cursor.fetchone()

    if data == "new_project":
        conn.close()
        ask_new_project(chat_id)
        return

    if not user:
        conn.close()
        ask_new_project(chat_id)
        return

    project, target, saved, daily = user

    if data == "pay_normal":
        new_saved = saved + daily
        cursor.execute("UPDATE users SET saved_amount=? WHERE chat_id=?", (new_saved, chat_id))
        conn.commit()
        bot.answer_callback_query(call.id, f"✅ +{daily:,.0f} HTG ajoutés !")
        conn.close()
        start_cmd(call.message)

    elif data == "pay_double":
        double_amount = daily * 2
        new_saved = saved + double_amount
        cursor.execute("UPDATE users SET saved_amount=? WHERE chat_id=?", (new_saved, chat_id))
        conn.commit()
        bot.answer_callback_query(call.id, f"🔥 SUPER ! +{double_amount:,.0f} HTG ajoutés (Double versement) !")
        conn.close()
        start_cmd(call.message)

    elif data == "analyze":
        conn.close()
        
        sim_1w = saved + (daily * 7)
        sim_2w = saved + (daily * 14)
        sim_1m = saved + (daily * 30)
        sim_2m = saved + (daily * 60)
        
        text = (
            f"📊 **ANALYSE & SIMULATION PROSPECTIVE**\n"
            f"───────────────────────────\n"
            f"🎯 **Projet :** {project} ({target:,.0f} HTG)\n\n"
            f"🔮 **Aperçu de tes économies futures si tu restes constant :**\n"
            f"• Dans **1 semaine** : {min(target, sim_1w):,.0f} HTG\n"
            f"• Dans **2 semaines** : {min(target, sim_2w):,.0f} HTG\n"
            f"• Dans **1 mois** : {min(target, sim_1m):,.0f} HTG\n"
            f"• Dans **2 mois** : {min(target, sim_2m):,.0f} HTG\n\n"
            f"💡 *En payant le double certains jours, tu réduis ce temps de moitié !*"
        )
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Retour au Tableau de Bord", callback_data="home_menu"))
        bot.edit_message_text(text, chat_id, message_id, parse_mode="Markdown", reply_markup=markup)

    elif data == "home_menu":
        conn.close()
        bot.delete_message(chat_id, message_id)
        start_cmd(call.message)

# ----------------------------------------------------
# 5. DÉMARRAGE DU BOT
# ----------------------------------------------------
if __name__ == '__main__':
    bot.remove_webhook()
    time.sleep(1)
    bot.infinity_polling(skip_pending=True)
