import os
import time
import sqlite3
import threading
from datetime import datetime
from flask import Flask
import telebot
from telebot import types

# ----------------------------------------------------
# 1. CONFIGURATION & SERVEUR FLASK POUR RENDER
# ----------------------------------------------------
app = Flask(__name__)

@app.route('/')
def home():
    return "B2K SafeBank Coach Bot v6.1 est en ligne et actif 24/7 !"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", 10000)))

threading.Thread(target=run_flask, daemon=True).start()

# ----------------------------------------------------
# 2. BASE DE DONNÉES SQLITE
# ----------------------------------------------------
def init_db():
    conn = sqlite3.connect("savings_v6.db", check_same_thread=False)
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
# 3. INITIALISATION DU BOT & ADMIN
# ----------------------------------------------------
TOKEN = "8870329936:AAHxHlJH9qN6GG_vZ9jUPUiA4_JfeE6ni8E"
bot = telebot.TeleBot(TOKEN)

ADMIN_CHAT_ID = None 
user_states = {}

def set_bot_commands():
    commands = [
        types.BotCommand("start", "Ouvrir le coffre-fort 💼"),
        types.BotCommand("projets", "Voir mes objectifs 📂"),
        types.BotCommand("tester", "Tester le rappel (Admin) ⏰"),
        types.BotCommand("annonce", "Annoncer les maj (Admin) 🚀"),
        types.BotCommand("aide", "Comment ça marche 🤖")
    ]
    bot.set_my_commands(commands)

set_bot_commands()

@bot.message_handler(commands=['aide'])
def help_cmd(message):
    text = (
        "🤖 **LE COACH & TON BANQUIER**\n"
        "───────────────────────────\n"
        "Yo poto ! Ici, on gère ton cash avec style et discipline.\n\n"
        "• **Objectif ou Réserve de cash :** Choisis d'économiser pour un article ou juste pour ta sécurité.\n"
        "• **Rappel automatique :** Le bot t'envoie une alerte à l'heure précise que tu as choisie.\n"
        "• **Sécurité :** Validation en 2 étapes pour éviter les faux clics."
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(commands=['annonce'])
def annonce_cmd(message):
    if ADMIN_CHAT_ID and message.chat.id != ADMIN_CHAT_ID:
        bot.send_message(message.chat.id, "⛔ Commande réservée à l'administrateur.")
        return
    text = (
        "🚀 **ANNONCE OFFICIELLE - MISE À JOUR B2K v6.1** 🚀\n"
        "───────────────────────────\n"
        "• Correction du moteur de rappel automatique (synchronisation des heures).\n"
        "• Sécurisation stricte des commandes admin (`/tester`, `/annonce`).\n"
        "• Gestion fluide des retours et suppression de coffres."
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(commands=['tester'])
def tester_cmd(message):
    chat_id = message.chat.id
    if ADMIN_CHAT_ID and chat_id != ADMIN_CHAT_ID:
        bot.send_message(chat_id, "⛔ Commande réservée à l'administrateur.")
        return
        
    conn = sqlite3.connect("savings_v6.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT project_id, project_name, daily_target FROM projects WHERE chat_id=? LIMIT 1", (chat_id,))
    proj = cursor.fetchone()
    conn.close()
    
    if not proj:
        bot.send_message(chat_id, "⚠️ Crée d'abord un projet avec /start pour tester ton rappel !")
        return
    
    pid, name, daily = proj
    text = (
        "⏰ **[TEST DE RAPPEL AUTOMATIQUE]**\n"
        "───────────────────────────\n"
        f"🚨 **Hé l'ami, c'est l'heure d'ajouter de l'argent pour *{name}* !**\n"
        f"As-tu vraiment l'argent pour verser tes **{daily:,.0f} HTG** du jour ?"
    )
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(f"✅ Oui, valider mon versement", callback_data=f"conf_pay_norm_{pid}"),
        types.InlineKeyboardButton("🔥 Ajouter un bonus libre", callback_data=f"pay_bonus_{pid}"),
        types.InlineKeyboardButton("📂 Voir le coffre", callback_data=f"select_proj_{pid}")
    )
    bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(commands=['projets', 'start'])
def start_cmd(message):
    global ADMIN_CHAT_ID
    if ADMIN_CHAT_ID is None:
        ADMIN_CHAT_ID = message.chat.id
    show_main_menu(message.chat.id)

def show_main_menu(chat_id):
    conn = sqlite3.connect("savings_v6.db", check_same_thread=False)
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
        "Choisis ton objectif du moment :"
    )
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    for p in projects:
        pid, name, target, saved, daily = p
        progress = int((saved / target) * 100) if target > 0 else 0
        markup.add(types.InlineKeyboardButton(f"🎯 {name} ({progress}% ➔ {saved:,.0f}/{target:,.0f} HTG)", callback_data=f"select_proj_{pid}"))
    
    markup.add(types.InlineKeyboardButton("➕ Créer un nouvel objectif", callback_data="create_new"))
    
    bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=markup)

# ----------------------------------------------------
# 4. ASSISTANT DE CRÉATION
# ----------------------------------------------------
def start_new_project_wizard(chat_id):
    user_states[chat_id] = {'step': 'TYPE_CHOICE'}
    text = (
        "🚀 **NOUVEL OBJECTIF FINANCIER**\n"
        "───────────────────────────\n"
        "Quel type de coffre veux-tu ouvrir ?"
    )
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🎯 Objectif d'achat", callback_data="type_achat"),
        types.InlineKeyboardButton("💵 Réserve de cash libre", callback_data="type_reserve")
    )
    bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data in ["type_achat", "type_reserve"])
def handle_type_choice(call):
    chat_id = call.message.chat.id
    if call.data == "type_reserve":
        user_states[chat_id] = {'step': 'TARGET', 'name': 'Réserve de cash libre'}
        text = "💵 Quel est le **montant total de cash** que tu veux accumuler dans ta réserve ?\n*(Exemple: 25000)*"
    else:
        user_states[chat_id] = {'step': 'NAME'}
        text = "✍️ **Quel est le nom de ton projet d'achat ?**\n*(Exemple: Nouveau téléphone, Matériel)*"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Retour", callback_data="back_to_menu"))
    
    bot.edit_message_text(text, chat_id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.chat.id in user_states and user_states[msg.chat.id].get('step') in ['NAME', 'TARGET', 'DAILY', 'TIME'])
def handle_wizard(msg):
    chat_id = msg.chat.id
    state = user_states[chat_id]
    
    if state['step'] == 'NAME':
        state['name'] = msg.text
        state['step'] = 'TARGET'
        text = f"🎯 Quel est le **montant total en HTG** pour **{msg.text}** ?\n*(Exemple: 30000)*"
    elif state['step'] == 'TARGET':
        try:
            state['target'] = float(msg.text.replace(" ", ""))
            state['step'] = 'DAILY'
            text = "💵 Combien veux-tu verser **chaque jour** pour ce plan ?\n*(Exemple: 250)*"
        except:
            bot.send_message(chat_id, "⚠️ Entre un montant valide en chiffres (ex: 30000).")
            return
    elif state['step'] == 'DAILY':
        try:
            state['daily'] = float(msg.text.replace(" ", ""))
            state['step'] = 'TIME'
            text = "⏰ À quelle **heure précise** veux-tu ton rappel quotidien ?\n*(Format HH:MM strict, exemple: 09:00 ou 18:30)*"
        except:
            bot.send_message(chat_id, "⚠️ Entre un montant journalier valide (ex: 250).")
            return
    elif state['step'] == 'TIME':
        time_str = msg.text.strip()
        try:
            datetime.strptime(time_str, "%H:%M")
            state['time'] = time_str
            today_str = datetime.now().strftime("%Y-%m-%d")
            
            conn = sqlite3.connect("savings_v6.db", check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO projects (chat_id, project_name, target_amount, saved_amount, daily_target, notify_time, start_date, days_count)
                VALUES (?, ?, ?, 0, ?, ?, ?, 0)
            ''', (chat_id, state['name'], state['target'], state['daily'], state['time'], today_str))
            conn.commit()
            conn.close()
            
            del user_states[chat_id]
            bot.send_message(chat_id, f"🎉 **OBJECTIF VERROUILLÉ !**\n📌 Plan : {state['name']}\n⏰ Rappel programmé à : {time_str}\n\nTape /projets pour ouvrir ton tableau de bord.", parse_mode="Markdown")
            return
        except ValueError:
            bot.send_message(chat_id, "⚠️ Format d'heure invalide. Utilise exactement le format **HH:MM** (ex: 09:00).")
            return

    bot.send_message(chat_id, text, parse_mode="Markdown")

# ----------------------------------------------------
# 5. GESTION DES INTERACTIONS & SUPPRESSION DE PROJET
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

    if data == "create_new" or data == "back_to_menu":
        if chat_id in user_states:
            del user_states[chat_id]
        show_main_menu(chat_id)
        return

    if data == "back_home":
        show_main_menu(chat_id)
        return

    if data.startswith("select_proj_"):
        proj_id = int(data.split("_")[2])
        show_project_dashboard(chat_id, proj_id)
        return

    if data.startswith("delete_proj_"):
        proj_id = int(data.split("_")[2])
        conn = sqlite3.connect("savings_v6.db", check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT project_name FROM projects WHERE project_id=?", (proj_id,))
        p = cursor.fetchone()
        conn.close()
        
        if p:
            name = p[0]
            text = f"⚠️ **SUPPRESSION DE COFFRE**\n\nVeux-tu vraiment supprimer définitivement le coffre *{name}* ? Cette action est irréversible."
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("🗑️ Oui, supprimer", callback_data=f"confirm_del_{proj_id}"),
                types.InlineKeyboardButton("🔙 Annuler", callback_data=f"select_proj_{proj_id}")
            )
            bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=markup)
        return

    if data.startswith("confirm_del_"):
        proj_id = int(data.split("_")[2])
        conn = sqlite3.connect("savings_v6.db", check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM projects WHERE project_id=?", (proj_id,))
        cursor.execute("DELETE FROM bonuses WHERE project_id=?", (proj_id,))
        conn.commit()
        conn.close()
        
        bot.send_message(chat_id, "🗑️ **Coffre supprimé avec succès.**", parse_mode="Markdown")
        show_main_menu(chat_id)
        return

    if data.startswith("conf_pay_norm_"):
        proj_id = int(data.split("_")[3])
        conn = sqlite3.connect("savings_v6.db", check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT project_name, daily_target FROM projects WHERE project_id=?", (proj_id,))
        proj = cursor.fetchone()
        conn.close()
        
        if proj:
            name, daily = proj
            text = f"🛡️ **VÉRIFICATION 1 / 2**\n\nAs-tu vraiment l'argent pour le moment pour verser tes **{daily:,.0f} HTG** dans *{name}* ?"
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton("👉 Oui, j'ai l'argent", callback_data=f"conf2_pay_{proj_id}"),
                types.InlineKeyboardButton("🔙 Annuler", callback_data=f"select_proj_{proj_id}")
            )
            bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=markup)
        return

    if data.startswith("conf2_pay_"):
        proj_id = int(data.split("_")[2])
        text = "🛡️ **VÉRIFICATION 2 / 2 (DISCIPLINE)**\n\n🧠 Tu dois être sérieux dans l'économie. Il faut avoir de la discipline. Es-tu 100% carré ?"
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("✅ OUI, ENCAISSER LE VERSEMENT", callback_data=f"exec_pay_norm_{proj_id}"),
            types.InlineKeyboardButton("🔙 Annuler", callback_data=f"select_proj_{proj_id}")
        )
        bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=markup)
        return

    if data.startswith("exec_pay_norm_"):
        proj_id = int(data.split("_")[3])
        conn = sqlite3.connect("savings_v6.db", check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT project_name, daily_target, days_count FROM projects WHERE project_id=?", (proj_id,))
        proj = cursor.fetchone()
        if proj:
            name, daily, days_count = proj
            new_days = days_count + 1
            cursor.execute("UPDATE projects SET saved_amount = saved_amount + ?, days_count = ? WHERE project_id=?", (daily, new_days, proj_id))
            conn.commit()
            bot.send_message(chat_id, f"💎 **VALIDÉ ET SÉCURISÉ !**\n+{daily:,.0f} HTG injectés dans *{name}*.\n\n📈 *C'est ça la vraie discipline poto !*", parse_mode="Markdown")
        conn.close()
        show_project_dashboard(chat_id, proj_id)
        return

    if data.startswith("pay_bonus_"):
        proj_id = int(data.split("_")[2])
        user_states[chat_id] = {'step': 'BONUS_AMT', 'proj_id': proj_id}
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Retour", callback_data=f"select_proj_{proj_id}"))
        
        bot.send_message(chat_id, "🔥 **AJOUT D'UN BONUS LIBRE**\n\n✍️ **Écris le montant du bonus en chiffres :**", parse_mode="Markdown", reply_markup=markup)
        return

    if data.startswith("view_bonuses_"):
        proj_id = int(data.split("_")[2])
        conn = sqlite3.connect("savings_v6.db", check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT project_name FROM projects WHERE project_id=?", (proj_id,))
        p = cursor.fetchone()
        cursor.execute("SELECT amount, date_added FROM bonuses WHERE project_id=?", (proj_id,))
        bonuses = cursor.fetchall()
        conn.close()
        
        if p:
            text = f"📂 **HISTORIQUE DES BONUS : {p[0]}**\n\n"
            if not bonuses:
                text += "Aucun bonus enregistré."
            else:
                total = 0
                for b in bonuses:
                    total += b[0]
                    text += f"• **+{b[0]:,.0f} HTG** (le {b[1]})\n"
                text += f"\n💰 **Total :** {total:,.0f} HTG"
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 Retour au coffre", callback_data=f"select_proj_{proj_id}"))
            bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=markup)
        return

    if data.startswith("analyze_"):
        proj_id = int(data.split("_")[2])
        conn = sqlite3.connect("savings_v6.db", check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT project_name, target_amount, saved_amount, daily_target, days_count FROM projects WHERE project_id=?", (proj_id,))
        proj = cursor.fetchone()
        conn.close()
        
        if proj:
            name, target, saved, daily, days_count = proj
            remaining = max(0, target - saved)
            days_left = int(remaining / daily) if daily > 0 else 0
            
            text = f"📊 **RAPPORT FINANCIER**\n\n🎯 Objectif : {name}\n💎 Sécurisé : {saved:,.0f} / {target:,.0f} HTG\n⏳ Reste : {days_left} jours d'effort.\n📌 Jours validés : {days_count}"
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 Retour au coffre", callback_data=f"select_proj_{proj_id}"))
            bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=markup)
        return

def show_project_dashboard(chat_id, proj_id):
    conn = sqlite3.connect("savings_v6.db", check_same_thread=False)
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
        types.InlineKeyboardButton("📂 Voir l'historique des bonus", callback_data=f"view_bonuses_{proj_id}"),
        types.InlineKeyboardButton("📊 Analyser mes performances", callback_data=f"analyze_{proj_id}"),
        types.InlineKeyboardButton("🗑️ Supprimer ce coffre", callback_data=f"delete_proj_{proj_id}"),
        types.InlineKeyboardButton("🔙 Retour à mes coffres", callback_data="back_home")
    )

    bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.chat.id in user_states and user_states[msg.chat.id].get('step') == 'BONUS_AMT')
def handle_bonus_input(msg):
    chat_id = msg.chat.id
    state = user_states[chat_id]
    proj_id = state['proj_id']
    
    try:
        bonus_amt = float(msg.text.replace(" ", ""))
        today_date = datetime.now().strftime("%Y-%m-%d")
        
        conn = sqlite3.connect("savings_v6.db", check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("UPDATE projects SET saved_amount = saved_amount + ? WHERE project_id=?", (bonus_amt, proj_id))
        cursor.execute("INSERT INTO bonuses (project_id, amount, date_added) VALUES (?, ?, ?)", (proj_id, bonus_amt, today_date))
        conn.commit()
        conn.close()
        
        del user_states[chat_id]
        bot.send_message(chat_id, f"🚀 **BONUS ENREGISTRÉ !**\n+{bonus_amt:,.0f} HTG injectés !\n\n*La discipline paie l'ami !*", parse_mode="Markdown")
        show_project_dashboard(chat_id, proj_id)
    except:
        bot.send_message(chat_id, "⚠️ Entre un montant valide en chiffres (ex: 500).")

# ----------------------------------------------------
# 6. MOTEUR DE RAPPEL AUTOMATIQUE 24/7 (SYNCHRO LOCALE)
# ----------------------------------------------------
def background_scheduler():
    while True:
        # Utilisation de l'heure locale pour correspondre parfaitement aux réglages
        now_str = datetime.now().strftime("%H:%M")
        try:
            conn = sqlite3.connect("savings_v6.db", check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute("SELECT chat_id, project_id, project_name, daily_target FROM projects WHERE notify_time=?", (now_str,))
            alerts = cursor.fetchall()
            conn.close()
            
            for alert in alerts:
                c_id, pid, pname, pdaily = alert
                text = (
                    "⏰ **[RAPPEL QUOTIDIEN B2K]**\n"
                    "───────────────────────────\n"
                    f"🚨 **Hé l'ami, c'est l'heure d'ajouter de l'argent pour *{pname}* !**\n"
                    f"As-tu vraiment l'argent pour verser tes **{pdaily:,.0f} HTG** du jour ?"
                )
                markup = types.InlineKeyboardMarkup(row_width=1)
                markup.add(
                    types.InlineKeyboardButton("✅ Oui, valider mon versement", callback_data=f"conf_pay_norm_{pid}"),
                    types.InlineKeyboardButton("🔥 Ajouter un bonus libre", callback_data=f"pay_bonus_{pid}"),
                    types.InlineKeyboardButton("📂 Voir le coffre", callback_data=f"select_proj_{pid}")
                )
                try:
                    bot.send_message(c_id, text, parse_mode="Markdown", reply_markup=markup)
                except:
                    pass
        except Exception as e:
            print("Erreur scheduler:", e)
            
        time.sleep(30) # Vérifie toutes les 30 secondes pour ne rater aucune minute

threading.Thread(target=background_scheduler, daemon=True).start()

# ----------------------------------------------------
# 7. LANCEMENT
# ----------------------------------------------------
if __name__ == '__main__':
    bot.remove_webhook()
    time.sleep(1)
    bot.infinity_polling(skip_pending=True)
