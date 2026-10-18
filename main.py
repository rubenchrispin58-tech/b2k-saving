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
# 2. BASE DE DONNÉES SQLITE (PROJETS + HISTORIQUE BONUS)
# ----------------------------------------------------
def init_db():
    conn = sqlite3.connect("savings_v4.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS projects (
            project_id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            project_name TEXT,
            target_amount REAL,
            saved_amount REAL,
            daily_target REAL,
            notify_time TEXT,
            start_date TEXT,
            days_count INTEGER DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bonuses (
            bonus_id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            amount REAL,
            date_added TEXT
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

user_states = {}

def set_bot_commands():
    commands = [
        types.BotCommand("start", "Ouvrir mon coffre-fort & tableau de bord 💼"),
        types.BotCommand("projets", "Voir tous mes objectifs d'épargne 📂"),
        types.BotCommand("aide", "Comprendre ton banquier 🤖")
    ]
    bot.set_my_commands(commands)

set_bot_commands()

@bot.message_handler(commands=['aide'])
def help_cmd(message):
    text = (
        "🤖 **LE COACH & TON BANQUIER PERSONNEL**\n"
        "───────────────────────────\n"
        "Yo poto ! Ici, pas de blague avec l'argent. La discipline, c'est la clé de la réussite.\n\n"
        "• **Versement quotidien :** Ton effort régulier.\n"
        "• **Bonus libre :** Un coup de boost pour faire baisser l'objectif plus vite (ne remplace pas le versement du lendemain).\n"
        "• **Discipline :** Si tu valides sans avoir payé, tu te mens à toi-même. Sois carré !"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(commands=['projets', 'start'])
def start_cmd(message):
    chat_id = message.chat.id
    show_main_menu(chat_id)

def show_main_menu(chat_id):
    conn = sqlite3.connect("savings_v4.db", check_same_thread=False)
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
        "*(Exemple: Casque Audio, Nouvelle Console, Investissement)*"
    )
    bot.send_message(chat_id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.chat.id in user_states and user_states[msg.chat.id].get('step') in ['NAME', 'TARGET', 'DAILY', 'TIME'])
def handle_wizard(msg):
    chat_id = msg.chat.id
    state = user_states[chat_id]
    
    if state['step'] == 'NAME':
        state['name'] = msg.text
        state['step'] = 'TARGET'
        bot.send_message(chat_id, f"🎯 Quel est le **montant total en HTG** pour **{msg.text}** ?\n*(Exemple: 30000)*", parse_mode="Markdown")
        
    elif state['step'] == 'TARGET':
        try:
            state['target'] = float(msg.text.replace(" ", ""))
            state['step'] = 'DAILY'
            bot.send_message(chat_id, "💵 Combien veux-tu verser **chaque jour** pour ce plan ?\n*(Exemple: 250)*", parse_mode="Markdown")
        except:
            bot.send_message(chat_id, "⚠️ Entre un montant valide en chiffres (ex: 30000).")

    elif state['step'] == 'DAILY':
        try:
            state['daily'] = float(msg.text.replace(" ", ""))
            state['step'] = 'TIME'
            bot.send_message(chat_id, "⏰ À quelle **heure** veux-tu ton rappel quotidien ?\n*(Format HH:MM, exemple: 09:00 ou 18:30)*", parse_mode="Markdown")
        except:
            bot.send_message(chat_id, "⚠️ Entre un montant journalier valide (ex: 250).")

    elif state['step'] == 'TIME':
        time_str = msg.text.strip()
        try:
            datetime.strptime(time_str, "%H:%M")
            state['time'] = time_str
            today_str = datetime.now().strftime("%Y-%m-%d")
            
            conn = sqlite3.connect("savings_v4.db", check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO projects (chat_id, project_name, target_amount, saved_amount, daily_target, notify_time, start_date, days_count)
                VALUES (?, ?, ?, 0, ?, ?, ?, 0)
            ''', (chat_id, state['name'], state['target'], state['daily'], state['time'], today_str))
            conn.commit()
            conn.close()
            
            del user_states[chat_id]
            
            text = (
                f"🎉 **OBJECTIF VERROUILLÉ AVEC SUCCÈS !**\n"
                f"───────────────────────────\n"
                f"📌 **Plan :** {state['name']}\n"
                f"🎯 **Cible :** {state['target']:,.0f} HTG\n"
                f"💵 **Versement quotidien :** {state['daily']:,.0f} HTG / jour\n"
                f"⏰ **Rappel programmé à :** {state['time']}\n\n"
                f"Tape /projets pour ouvrir ton tableau de bord."
            )
            bot.send_message(chat_id, text, parse_mode="Markdown")
        except ValueError:
            bot.send_message(chat_id, "⚠️ Format d'heure invalide. Utilise exactement le format **HH:MM** (ex: 09:00).")

# ----------------------------------------------------
# 5. GESTION DES INTERACTIONS & BOUTONS
# ----------------------------------------------------
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    data = call.data

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

    # --- ÉTAPE 1 DE CONFIRMATION (TRIPLE SÉCURITÉ CONTRE LES CLICS ACCIDENTELS) ---
    if data.startswith("conf_pay_norm_"):
        proj_id = int(data.split("_")[3])
        conn = sqlite3.connect("savings_v4.db", check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT project_name, daily_target FROM projects WHERE project_id=?", (proj_id,))
        proj = cursor.fetchone()
        conn.close()
        
        if proj:
            name, daily = proj
            text = (
                f"🛡️ **TRIPLE SÉCURITÉ - ÉTAPE 1/3**\n"
                f"───────────────────────────\n"
                f"Tu es sur le point de valider ton versement de **{daily:,.0f} HTG** pour *{name}*.\n\n"
                f"⚠️ *As-tu réellement déposé cet argent aujourd'hui ?*"
            )
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton("👉 Oui, continuer (1/3)", callback_data=f"conf2_pay_{proj_id}"),
                types.InlineKeyboardButton("❌ Annuler", callback_data=f"select_proj_{proj_id}")
            )
            bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=markup)
        return

    # --- ÉTAPE 2 DE CONFIRMATION ---
    if data.startswith("conf2_pay_"):
        proj_id = int(data.split("_")[2])
        text = (
            "🛡️ **TRIPLE SÉCURITÉ - ÉTAPE 2/3**\n"
            "───────────────────────────\n"
            "🧠 *Rappelle-toi ce que ton banquier te dit :*\n"
            "Si tu n'as pas vraiment ajouté de l'argent, tu commences à ne pas être sérieux dans le projet. C'est la discipline qui compte !\n\n"
            "Es-tu totalement sûr de toi ?"
        )
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("👉 Oui, je suis carré (2/3)", callback_data=f"conf3_pay_{proj_id}"),
            types.InlineKeyboardButton("❌ Oups, annuler", callback_data=f"select_proj_{proj_id}")
        )
        bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=markup)
        return

    # --- ÉTAPE 3 (FINALE) DE CONFIRMATION ---
    if data.startswith("conf3_pay_"):
        proj_id = int(data.split("_")[2])
        text = (
            "🛡️ **TRIPLE SÉCURITÉ - DERNIÈRE ÉTAPE (3/3)**\n"
            "───────────────────────────\n"
            "Dernière chance avant l'enregistrement définitif dans ton coffre."
        )
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("✅ CONFIRMER LE VERSEMENT", callback_data=f"exec_pay_norm_{proj_id}"),
            types.InlineKeyboardButton("❌ Annuler", callback_data=f"select_proj_{proj_id}")
        )
        bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=markup)
        return

    # --- EXÉCUTION DU VERSEMENT QUOTIDIEN ---
    if data.startswith("exec_pay_norm_"):
        proj_id = int(data.split("_")[3])
        conn = sqlite3.connect("savings_v4.db", check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT project_name, daily_target, days_count FROM projects WHERE project_id=?", (proj_id,))
        proj = cursor.fetchone()
        if proj:
            name, daily, days_count = proj
            new_days = days_count + 1
            cursor.execute("UPDATE projects SET saved_amount = saved_amount + ?, days_count = ? WHERE project_id=?", (daily, new_days, proj_id))
            conn.commit()
            
            bot.send_message(chat_id, f"💎 **ENCAISSÉ AVEC SUCCÈS !**\n+{daily:,.0f} HTG ajoutés à ton coffre *{name}*.\n\n📈 *Ton banquier valide ta rigueur !*", parse_mode="Markdown")
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

    # --- HISTORIQUE DES BONUS ---
    if data.startswith("view_bonuses_"):
        proj_id = int(data.split("_")[2])
        conn = sqlite3.connect("savings_v4.db", check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT project_name FROM projects WHERE project_id=?", (proj_id,))
        p = cursor.fetchone()
        
        cursor.execute("SELECT amount, date_added FROM bonuses WHERE project_id=?", (proj_id,))
        bonuses = cursor.fetchall()
        conn.close()
        
        if p:
            name = p[0]
            text = f"📂 **HISTORIQUE DES BONUS : {name}**\n───────────────────────────\n"
            if not bonuses:
                text += "Aucun bonus enregistré pour l'instant. C'est le moment d'en placer un ! 🔥"
            else:
                total_bonus = 0
                for b in bonuses:
                    amt, dt = b
                    total_bonus += amt
                    text += f"• **+{amt:,.0f} HTG** (le {dt})\n"
                text += f"\n💰 **Total des bonus injectés :** {total_bonus:,.0f} HTG"
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 Retour au coffre", callback_data=f"select_proj_{proj_id}"))
            bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=markup)
        return

    # --- ANALYSE & PRÉVISIONS (AVEC JOURS RESTANTS & DATE) ---
    if data.startswith("analyze_"):
        proj_id = int(data.split("_")[2])
        conn = sqlite3.connect("savings_v4.db", check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT project_name, target_amount, saved_amount, daily_target, days_count FROM projects WHERE project_id=?", (proj_id,))
        proj = cursor.fetchone()
        conn.close()
        
        if proj:
            name, target, saved, daily, days_count = proj
            remaining = max(0, target - saved)
            
            # Calcul du nombre de jours restants nécessaires
            days_left = int(remaining / daily) if daily > 0 else 0
            
            today_date_str = datetime.now().strftime("%d %B %Y")
            
            text = (
                f"📊 **RAPPORT FINANCIER & DISCIPLINE**\n"
                f"───────────────────────────\n"
                f"📅 **Aujourd'hui :** {today_date_str}\n"
                f"🎯 **Projet :** {name}\n"
                f"💎 **Déjà sécurisé :** {saved:,.0f} HTG / {target:,.0f} HTG\n"
                f"⏳ **Il te reste environ :** {days_left} jours d'effort pour tout boucler !\n\n"
                f"📌 **Ton parcours :** C'est ton **{days_count + 1}e jour** d'économie.\n"
                f"💡 *Demain sera un nouveau palier. Ne rate pas un jour, la régularité fait tout !*"
            )
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 Retour au coffre", callback_data=f"select_proj_{proj_id}"))
            bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=markup)
        return

def show_project_dashboard(chat_id, proj_id):
    conn = sqlite3.connect("savings_v4.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT project_name, target_amount, saved_amount, daily_target, notify_time, days_count FROM projects WHERE project_id=?", (proj_id,))
    proj = cursor.fetchone()
    conn.close()

    if not proj:
        show_main_menu(chat_id)
        return

    name, target, saved, daily, notif_time, days_count = proj
    remaining = max(0, target - saved)
    progress = int((saved / target) * 100) if target > 0 else 0
    
    today_str = datetime.now().strftime("%d %B %Y")

    text = (
        f"🎯 **COFFRE-FORT : {name}**\n"
        f"───────────────────────────\n"
        f"📅 **Date du jour :** {today_str}\n"
        f"🚨 *Rappel : Demain sera ton {days_count + 2}e jour d'économie, sois discipliné, ne rate pas un jour !*\n\n"
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
        types.InlineKeyboardButton("📂 Voir l'historique des bonus", callback_data=f"view_bonuses_{proj_id}"),
        types.InlineKeyboardButton("📊 Analyser mes performances & Jours restants", callback_data=f"analyze_{proj_id}"),
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
        today_date = datetime.now().strftime("%Y-%m-%d")
        
        conn = sqlite3.connect("savings_v4.db", check_same_thread=False)
        cursor = conn.cursor()
        # Mise à jour du total épargné
        cursor.execute("UPDATE projects SET saved_amount = saved_amount + ? WHERE project_id=?", (bonus_amt, proj_id))
        # Enregistrement dans l'historique des bonus
        cursor.execute("INSERT INTO bonuses (project_id, amount, date_added) VALUES (?, ?, ?)", (proj_id, bonus_amt, today_date))
        conn.commit()
        conn.close()
        
        del user_states[chat_id]
        bot.send_message(chat_id, f"🚀 **BONUS ENREGISTRÉ AVEC SUCCÈS !**\n+{bonus_amt:,.0f} HTG injectés dans ton coffre !\n\n*Rappelle-toi : ton versement quotidien de demain reste bien exigé. C'est la discipline qui paie l'ami !*", parse_mode="Markdown")
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
