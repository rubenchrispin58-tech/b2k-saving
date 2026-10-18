import os
import time
import sqlite3
import threading
from datetime import datetime
from flask import Flask
import telebot
from telebot import types

# ----------------------------------------------------
# 1. SERVEUR FLASK POUR RENDER
# ----------------------------------------------------
app = Flask(__name__)

@app.route('/')
def home():
    return "B2K SafeBank Coach Bot est en ligne et sécurisé 24/7 !"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", 10000)))

threading.Thread(target=run_flask, daemon=True).start()

# ----------------------------------------------------
# 2. BASE DE DONNÉES SQLITE
# ----------------------------------------------------
def init_db():
    conn = sqlite3.connect("savings_v3.db", check_same_thread=False)
    cursor = conn.cursor()
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
# 3. INITIALISATION DU BOT
# ----------------------------------------------------
TOKEN = "8870329936:AAHxHlJH9qN6GG_vZ9jUPUiA4_JfeE6ni8E"
bot = telebot.TeleBot(TOKEN)

# Dictionnaire pour gérer les états des utilisateurs (étapes de création/bonus)
user_states = {}

# Configuration du menu des commandes Telegram
def set_bot_commands():
    commands = [
        types.BotCommand("start", "Ouvrir mon coffre-fort & tableau de bord 💼"),
        types.BotCommand("projets", "Voir tous mes objectifs d'épargne 📂"),
        types.BotCommand("aide", "Comprendre comment fonctionne ton banquier 🤖")
    ]
    bot.set_my_commands(commands)

set_bot_commands()

@bot.message_handler(commands=['aide'])
def help_cmd(message):
    text = (
        "🤖 ** GUIDE DE TON BANQUIER PERSONNEL**\n"
        "───────────────────────────\n"
        "Yo poto ! Ici, on gère ton capital comme un investisseur sérieux.\n\n"
        "• **Versement quotidien :** Ton effort régulier de chaque jour.\n"
        "• **Bonus libre :** Un extra que tu ajoutes pour faire fondre l'objectif plus vite, sans remplacer ton versement du lendemain.\n"
        "• **Sécurité :** Chaque validation demande une double confirmation pour éviter les fausses manœuvres !"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(commands=['projets', 'start'])
def start_cmd(message):
    chat_id = message.chat.id
    show_main_menu(chat_id)

def show_main_menu(chat_id):
    conn = sqlite3.connect("savings_v3.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT project_id, project_name, target_amount, saved_amount, daily_target FROM projects WHERE chat_id=?", (chat_id,))
    projects = cursor.fetchall()
    conn.close()

    if not projects:
        start_new_project_wizard(chat_id)
        return

    text = (
        "💼 **SAFE-BANK | TES COFFRES-FORTS**\n"
        "───────────────────────────\n"
        "Yo l'artiste ! Quel objectif on surveille aujourd'hui ?"
    )
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    for p in projects:
        pid, name, target, saved, daily = p
        progress = int((saved / target) * 100) if target > 0 else 0
        markup.add(types.InlineKeyboardButton(f"🎯 {name} ({progress}% ➔ {saved:,.0f}/{target:,.0f} HTG)", callback_data=f"select_proj_{pid}"))
    
    markup.add(types.InlineKeyboardButton("➕ Créer un nouvel objectif", callback_data="create_new"))
    
    bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=markup)

# ----------------------------------------------------
# 4. ASSISTANT DE CRÉATION DE PROJET (WIZARD)
# ----------------------------------------------------
def start_new_project_wizard(chat_id):
    user_states[chat_id] = {'step': 'NAME'}
    text = (
        "🚀 **NOUVEL OBJECTIF FINANCIER**\n"
        "───────────────────────────\n"
        "✍️ **Quel est le nom de ton projet ?**\n"
        "*(Exemple: Casque Bluetooth, Nouvelle Console, Investissement)*"
    )
    bot.send_message(chat_id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.chat.id in user_states and user_states[msg.chat.id].get('step') in ['NAME', 'TARGET', 'DAILY', 'TIME'])
def handle_wizard(msg):
    chat_id = msg.chat.id
    state = user_states[chat_id]
    
    if state['step'] == 'NAME':
        state['name'] = msg.text
        state['step'] = 'TARGET'
        bot.send_message(chat_id, f"🎯 Quel est le **montant total en HTG** pour **{msg.text}** ?\n*(Exemple: 25000)*", parse_mode="Markdown")
        
    elif state['step'] == 'TARGET':
        try:
            state['target'] = float(msg.text.replace(" ", ""))
            state['step'] = 'DAILY'
            bot.send_message(chat_id, "💵 Combien veux-tu verser **chaque jour** pour ce plan ?\n*(Exemple: 200)*", parse_mode="Markdown")
        except:
            bot.send_message(chat_id, "⚠️ Entre un montant valide en chiffres (ex: 25000).")

    elif state['step'] == 'DAILY':
        try:
            state['daily'] = float(msg.text.replace(" ", ""))
            state['step'] = 'TIME'
            bot.send_message(chat_id, "⏰ À quelle **heure** veux-tu ton rappel quotidien ?\n*(Format HH:MM, exemple: 08:30 ou 19:00)*", parse_mode="Markdown")
        except:
            bot.send_message(chat_id, "⚠️ Entre un montant journalier valide (ex: 200).")

    elif state['step'] == 'TIME':
        time_str = msg.text.strip()
        try:
            datetime.strptime(time_str, "%H:%M")
            state['time'] = time_str
            
            conn = sqlite3.connect("savings_v3.db", check_same_thread=False)
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
                f"🎉 **OBJECTIF VERROUILLÉ AVEC SUCCÈS !**\n"
                f"───────────────────────────\n"
                f"📌 **Plan :** {proj_name}\n"
                f"🎯 **Cible :** {target:,.0f} HTG\n"
                f"💵 **Versement quotidien :** {daily:,.0f} HTG / jour\n"
                f"⏰ **Rappel programmé à :** {notif}\n\n"
                f"Tape /projets pour ouvrir ton tableau de bord."
            )
            bot.send_message(chat_id, text, parse_mode="Markdown")
        except ValueError:
            bot.send_message(chat_id, "⚠️ Format d'heure invalide. Utilise exactement le format **HH:MM** (ex: 08:30).")

# ----------------------------------------------------
# 5. GESTION DES INTERACTIONS & BOUTONS
# ----------------------------------------------------
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    data = call.data

    # Suppression propre de l'ancien message pour éviter le fouillis
    try:
        bot.delete_message(chat_id, message_id)
    except:
        pass

    if data == "create_new":
        start_new_project_wizard(chat_id)
        return

    if data == "back_home":
        show_main_menu(chat_id)
        return

    if data.startswith("select_proj_"):
        proj_id = int(data.split("_")[2])
        show_project_dashboard(chat_id, proj_id)
        return

    # --- ÉTAPE DE CONFIRMATION VERSEMENT QUOTIDIEN ---
    if data.startswith("conf_pay_norm_"):
        proj_id = int(data.split("_")[3])
        conn = sqlite3.connect("savings_v3.db", check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT project_name, daily_target FROM projects WHERE project_id=?", (proj_id,))
        proj = cursor.fetchone()
        conn.close()
        
        if proj:
            name, daily = proj
            text = (
                f"⚠️ **CONFIRMATION REQUISE**\n"
                f"───────────────────────────\n"
                f"Veux-tu vraiment valider ton versement quotidien de **{daily:,.0f} HTG** pour *{name}* ?"
            )
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("✅ Oui, valider", callback_data=f"exec_pay_norm_{proj_id}"),
                types.InlineKeyboardButton("❌ Annuler", callback_data=f"select_proj_{proj_id}")
            )
            bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=markup)
        return

    # --- EXÉCUTION VERSEMENT QUOTIDIEN ---
    if data.startswith("exec_pay_norm_"):
        proj_id = int(data.split("_")[3])
        conn = sqlite3.connect("savings_v3.db", check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT project_name, daily_target FROM projects WHERE project_id=?", (proj_id,))
        proj = cursor.fetchone()
        if proj:
            name, daily = proj
            cursor.execute("UPDATE projects SET saved_amount = saved_amount + ? WHERE project_id=?", (daily, proj_id))
            conn.commit()
            bot.send_message(chat_id, f"💎 **ENCAISSÉ !**\n+{daily:,.0f} HTG ajoutés à ton coffre *{name}*.\n\n*Ton banquier est fier de ta constance ! 📈*", parse_mode="Markdown")
        conn.close()
        show_project_dashboard(chat_id, proj_id)
        return

    # --- DEMANDE DE BONUS (SAISIE CLAVIER) ---
    if data.startswith("pay_bonus_"):
        proj_id = int(data.split("_")[2])
        user_states[chat_id] = {'step': 'BONUS_AMT', 'proj_id': proj_id}
        
        text = (
            "🔥 **AJOUT D'UN BONUS LIBRE**\n"
            "───────────────────────────\n"
            "*(Rappelle-toi : ce bonus fait baisser ton objectif global, mais n'annule pas ton versement de demain !)*\n\n"
            "✍️ **Écris le montant du bonus en chiffres :**"
        )
        bot.send_message(chat_id, text, parse_mode="Markdown")
        return

    # --- ANALYSE & PRÉVISIONS ---
    if data.startswith("analyze_"):
        proj_id = int(data.split("_")[2])
        conn = sqlite3.connect("savings_v3.db", check_same_thread=False)
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
                f"📊 **RAPPORT FINANCIER : {name}**\n"
                f"───────────────────────────\n"
                f"🎯 **Cible totale :** {target:,.0f} HTG\n"
                f"💎 **Déjà sécurisé :** {saved:,.0f} HTG\n"
                f"⏳ **Reste à accumuler :** {remaining:,.0f} HTG\n\n"
                f"🔮 **Projection bancaire (au rythme de {daily:,.0f} HTG/jour) :**\n"
                f"• Dans **1 semaine** ➔ {min(target, sim_1w):,.0f} HTG\n"
                f"• Dans **1 mois** ➔ {min(target, sim_1m):,.0f} HTG\n\n"
                f"💡 *Ton capital grandit chaque jour. Continue comme ça poto !*"
            )
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 Retour au coffre", callback_data=f"select_proj_{proj_id}"))
            bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=markup)
        return

def show_project_dashboard(chat_id, proj_id):
    conn = sqlite3.connect("savings_v3.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT project_name, target_amount, saved_amount, daily_target, notify_time FROM projects WHERE project_id=?", (proj_id,))
    proj = cursor.fetchone()
    conn.close()

    if not proj:
        show_main_menu(chat_id)
        return

    name, target, saved, daily, notif_time = proj
    remaining = max(0, target - saved)
    progress = int((saved / target) * 100) if target > 0 else 0

    text = (
        f"🎯 **COFFRE-FORT : {name}**\n"
        f"───────────────────────────\n"
        f"💰 **Objectif Total :** {target:,.0f} HTG\n"
        f"💎 **Déjà Sécurisé :** {saved:,.0f} HTG ({progress}%)\n"
        f"⏳ **Reste à mettre :** {remaining:,.0f} HTG\n"
        f"📌 **Versement quotidien :** {daily:,.0f} HTG / jour\n"
        f"⏰ **Rappel programmé :** {notif_time}\n\n"
        f"👇 *Que fait-on pour ton capital aujourd'hui ?*"
    )

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(f"✅ Valider mon versement ({daily:,.0f} HTG)", callback_data=f"conf_pay_norm_{proj_id}"),
        types.InlineKeyboardButton("🔥 Ajouter un bonus libre", callback_data=f"pay_bonus_{proj_id}"),
        types.InlineKeyboardButton("📊 Analyser mes performances", callback_data=f"analyze_{proj_id}"),
        types.InlineKeyboardButton("🔙 Retour à mes coffres", callback_data="back_home")
    )

    bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=markup)

# ----------------------------------------------------
# 6. CAPTURE DES TEXTES (SAISIE DE BONUS)
# ----------------------------------------------------
@bot.message_handler(func=lambda msg: msg.chat.id in user_states and user_states[msg.chat.id].get('step') == 'BONUS_AMT')
def handle_bonus_input(msg):
    chat_id = msg.chat.id
    state = user_states[chat_id]
    proj_id = state['proj_id']
    
    try:
        bonus_amt = float(msg.text.replace(" ", ""))
        conn = sqlite3.connect("savings_v3.db", check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("UPDATE projects SET saved_amount = saved_amount + ? WHERE project_id=?", (bonus_amt, proj_id))
        conn.commit()
        conn.close()
        
        del user_states[chat_id]
        bot.send_message(chat_id, f"🚀 **BONUS VALIDÉ AVEC SUCCÈS !**\n+{bonus_amt:,.0f} HTG injectés dans ton coffre !\n\n*Ton versement quotidien de demain reste bien en place. Bien joué l'ami !*", parse_mode="Markdown")
        show_project_dashboard(chat_id, proj_id)
    except:
        bot.send_message(chat_id, "⚠️ Entre un montant de bonus valide en chiffres (ex: 500).")

# ----------------------------------------------------
# 7. LANCEMENT
# ----------------------------------------------------
if __name__ == '__main__':
    bot.remove_webhook()
    time.sleep(1)
    bot.infinity_polling(skip_pending=True)
