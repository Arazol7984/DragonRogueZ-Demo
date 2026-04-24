import sqlite3
import json
import random
from flask import Flask, render_template, jsonify, request

app = Flask(__name__)

# --- DATABASE PERSISTENCE ---
def init_db():
    conn = sqlite3.connect('save_data.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS progress 
                 (id INTEGER PRIMARY KEY, unlocked_chars TEXT)''')
    c.execute("SELECT COUNT(*) FROM progress")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO progress (unlocked_chars) VALUES (?)", (json.dumps(['goku']),))
    conn.commit()
    conn.close()

def get_unlocked():
    try:
        conn = sqlite3.connect('save_data.db')
        c = conn.cursor()
        c.execute("SELECT unlocked_chars FROM progress WHERE id = 1")
        row = c.fetchone()
        conn.close()
        return json.loads(row[0]) if row else ['goku']
    except:
        return ['goku']

def save_unlock(char_id):
    chars = get_unlocked()
    if char_id not in chars:
        chars.append(char_id)
        conn = sqlite3.connect('save_data.db')
        c = conn.cursor()
        c.execute("UPDATE progress SET unlocked_chars = ? WHERE id = 1", (json.dumps(chars),))
        conn.commit()
        conn.close()

init_db()

# --- EXPANDED SHOP DATA ---
ALL_SHOP_ITEMS = {
    "senzu": {"name": "Senzu Bean", "desc": "Fully restores VIT.", "cost": 300},
    "training": {"name": "Gravity Room", "desc": "Increases PL by 500.", "cost": 600},
    "weighted_gear": {"name": "Weighted Gear", "desc": "+10% Defense permanently.", "cost": 450},
    "scouter_v2": {"name": "Scouter v2", "desc": "+10% Crit Chance (Cap 40%).", "cost": 500},
    "ki_catalyst": {"name": "Ki Catalyst", "desc": "Start every battle with 20 extra Ki.", "cost": 400},
    "fruit_tree": {"name": "Fruit of Might", "desc": "Massive +1000 PL boost.", "cost": 1200},
    "tail_regrow": {"name": "Tail Ointment", "desc": "+5% Lifesteal on all attacks.", "cost": 700},
    "capsule_coffee": {"name": "Capsule Coffee", "desc": "Regen 5 Ki every turn.", "cost": 350},
    "alloy_plating": {"name": "Alloy Plating", "desc": "Reduces enemy damage by 50.", "cost": 550},
    "zenkai_boost": {"name": "Zenkai Injector", "desc": "Low health damage bonus +20%.", "cost": 800},
    "katchin_shield": {"name": "Katchin Shard", "desc": "Guard block 95% of damage.", "cost": 900},
    "adrenaline": {"name": "Saiyan Rage", "desc": "+25% Jab damage.", "cost": 300},
    "spare_battery": {"name": "Overclocker", "desc": "Skills cost 10% less Ki.", "cost": 650},
    "meditation_mat": {"name": "Old Mat", "desc": "Ki gains from Jabs increased.", "cost": 250},
    "prophetic_fish": {"name": "Oracle Snack", "desc": "10% chance to dodge counters.", "cost": 1000},
    "dende_blessing": {"name": "Namekian Wish", "desc": "+2000 Max Vit.", "cost": 1500},
}

# --- GAME ENGINE ---
class GameState:
    def __init__(self):
        self.reset()

    def reset(self, char_type="goku"):
        self.wave = 1
        self.char_type = char_type
        self.zeni = 400
        self.ki = 40
        self.current_shop = []
        
        # Stats & Mods
        self.defense_mod = 1.0
        self.crit_chance = 1/24  # Base 1/24 chance
        self.lifesteal = 0.0
        self.ki_regen = 0
        self.dodge_chance = 0.0
        
        if char_type == "vegeta": self.pl, self.base_max_hp = 18000, 5000
        elif char_type == "nappa": self.pl, self.base_max_hp = 4000, 3500
        elif char_type == "raditz": self.pl, self.base_max_hp = 1200, 1200
        else: self.pl, self.base_max_hp = 415, 800
            
        self.update_stats()
        self.hp = self.max_hp
        self.enemy = self.spawn_enemy()

    def update_stats(self):
        self.max_hp = int(self.base_max_hp + (self.pl * 0.05))

    def spawn_enemy(self):
        if self.wave % 30 == 0:
            hp = 8000 + (self.wave * 100)
            return {"name": "VEGETA", "hp": hp, "max_hp": hp, "pl": 18000 + (self.wave * 50)}
        elif self.wave % 20 == 0:
            hp = 4000 + (self.wave * 80)
            return {"name": "NAPPA", "hp": hp, "max_hp": hp, "pl": 4000 + (self.wave * 40)}
        elif self.wave % 10 == 0:
            name = "FRIEZASOLDIER" if self.char_type == "raditz" else "RADITZ"
            hp = 1500 + (self.wave * 50)
            return {"name": name, "hp": hp, "max_hp": hp, "pl": 1500 + (self.wave * 20)}

        hp = 250 + (self.wave * 45)
        pl = 320 + (self.wave * 30)
        e_name = random.choice(["SAIBAMAN", "FRIEZASOLDIER"]) if self.wave > 5 else "SAIBAMAN"
        return {"name": e_name, "hp": hp, "max_hp": hp, "pl": pl}

    def generate_shop(self):
        keys = list(ALL_SHOP_ITEMS.keys())
        selected_keys = random.sample(keys, 4)
        self.current_shop = [{"id": k, **ALL_SHOP_ITEMS[k]} for k in selected_keys]
        return self.current_shop

state = GameState()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get-unlocked')
def handle_get_unlocked():
    return jsonify({"unlocked": get_unlocked()})

@app.route('/select-char', methods=['POST'])
def select_char():
    data = request.get_json()
    char = data.get('character', 'goku')
    if char in get_unlocked():
        state.reset(char)
        return jsonify({"status": "success", "player": vars(state), "enemy": state.enemy})
    return jsonify({"error": "Character locked"}), 403

@app.route('/battle-action', methods=['POST'])
def battle_action():
    data = request.get_json()
    skill = data.get('skill')
    
    base_dmg, ki_cost, ki_gain = 0, 0, 0
    passive_mult = 1.0

    if state.char_type == "raditz":
        if state.enemy["hp"] < (state.enemy["max_hp"] * 0.5): passive_mult = 1.20
        if skill == 'jab': base_dmg, ki_gain = random.randint(45, 65), 12
        elif skill == 'meteor': base_dmg, ki_cost = random.randint(110, 155), 25
        elif skill == 'kamehameha': base_dmg, ki_cost = random.randint(190, 275), 30
        elif skill == 'spirit_bomb': base_dmg, ki_cost = random.randint(450, 680), 65
    else:
        missing_hp_percent = (state.max_hp - state.hp) / state.max_hp
        segments = int(missing_hp_percent / 0.25)
        passive_mult = 1.0 + (segments * 0.15)
        if skill == 'jab': base_dmg, ki_gain = random.randint(30, 50), 15
        elif skill == 'meteor': base_dmg, ki_cost = random.randint(80, 120), 20
        elif skill == 'kamehameha': base_dmg, ki_cost = random.randint(150, 220), 35
        elif skill == 'spirit_bomb': base_dmg, ki_cost = random.randint(350, 500), 70

    if skill == 'guard': ki_gain = 25

    scaling = pow(1 + (state.pl / 1000), 1.2) 
    is_crit = random.random() < state.crit_chance
    crit_mult = 1.5 if is_crit else 1.0
    
    final_dmg = int(base_dmg * scaling * passive_mult * crit_mult)
    state.ki = min(100, max(0, state.ki + ki_gain - ki_cost + state.ki_regen))
    state.enemy["hp"] = max(0, state.enemy["hp"] - final_dmg)

    enemy_killed = state.enemy["hp"] <= 0
    enemy_msg = ""
    if not enemy_killed:
        if random.random() > state.dodge_chance:
            e_scaling = 1 + (state.enemy["pl"] / 5000)
            e_dmg = int(random.randint(20, 40) * e_scaling * state.defense_mod)
            if skill == 'guard': e_dmg = int(e_dmg * 0.1)
            state.hp = max(0, state.hp - e_dmg)
            enemy_msg = f"{state.enemy['name']} counters for {e_dmg} damage!"
        else:
            enemy_msg = "You dodged the counter attack!"

    if enemy_killed:
        state.zeni += 150 + (state.wave * 10)
        state.generate_shop()
        if state.enemy["name"] in ["RADITZ", "NAPPA", "VEGETA"]:
            save_unlock(state.enemy["name"].lower())

    return jsonify({
        "message": f"Dealt {final_dmg} damage! {'(CRITICAL!)' if is_crit else ''}",
        "enemy_msg": enemy_msg,
        "player": vars(state),
        "enemy": state.enemy,
        "enemy_killed": enemy_killed,
        "shop_items": state.current_shop,
        "is_crit": is_crit
    })

@app.route('/purchase', methods=['POST'])
def purchase():
    data = request.get_json()
    item_id = data.get('item_id')
    item = ALL_SHOP_ITEMS.get(item_id)
    
    if item and state.zeni >= item['cost']:
        state.zeni -= item['cost']
        if item_id == "senzu": state.hp = state.max_hp
        elif item_id == "training": state.pl += 500
        elif item_id == "weighted_gear": state.defense_mod *= 0.9
        elif item_id == "scouter_v2": 
            state.crit_chance = min(0.40, state.crit_chance + 0.10)
        elif item_id == "fruit_tree": state.pl += 1000
        elif item_id == "tail_regrow": state.lifesteal += 0.05
        elif item_id == "capsule_coffee": state.ki_regen += 5
        elif item_id == "dende_blessing": state.base_max_hp += 2000
        
        state.update_stats()
        return jsonify({"player": vars(state)})
    return jsonify({"error": "Insufficient Zeni"}), 400

@app.route('/next-enemy', methods=['POST'])
def next_enemy():
    state.wave += 1
    state.enemy = state.spawn_enemy()
    return jsonify({"wave": state.wave, "enemy": state.enemy, "player": vars(state)})

if __name__ == '__main__':
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)