import sqlite3
import json
import random
import os
from flask import Flask, render_template, jsonify, request

app = Flask(__name__)
app.secret_key = "dragon_rogue_z_2026_build"

# --- DATABASE & ROSTER LOGIC ---
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

# --- 25+ SHOP ITEMS ---
ALL_SHOP_ITEMS = {
    "senzu": {"name": "Senzu Bean", "desc": "Fully restores HP.", "cost": 250},
    "training": {"name": "Gravity Room", "desc": "+500 Power Level.", "cost": 600},
    "weighted_gear": {"name": "Weighted Gear", "desc": "+10% Defense.", "cost": 450},
    "scouter_v2": {"name": "Elite Scouter", "desc": "+10% Crit (Cap 40%).", "cost": 500},
    "ki_catalyst": {"name": "Ki Catalyst", "desc": "Start with +20 Ki.", "cost": 400},
    "fruit_tree": {"name": "Fruit of Might", "desc": "+1000 PL boost.", "cost": 1200},
    "tail_regrow": {"name": "Tail Ointment", "desc": "+5% Lifesteal.", "cost": 700},
    "capsule_coffee": {"name": "Capsule Coffee", "desc": "Regen 5 Ki every turn.", "cost": 350},
    "alloy_plating": {"name": "Alloy Plating", "desc": "Flat -50 Dmg taken.", "cost": 550},
    "zenkai_boost": {"name": "Zenkai Injector", "desc": "Low HP Dmg +20%.", "cost": 800},
    "katchin_shield": {"name": "Katchin Shard", "desc": "Block 15% Dmg.", "cost": 900},
    "adrenaline": {"name": "Saiyan Rage", "desc": "+25% Jab Damage.", "cost": 300},
    "spare_battery": {"name": "Overclocker", "desc": "Skills cost -10% Ki.", "cost": 650},
    "meditation_mat": {"name": "Old Mat", "desc": "+2 Ki from Jabs.", "cost": 250},
    "prophetic_fish": {"name": "Oracle Snack", "desc": "10% Dodge chance.", "cost": 1000},
    "dende_blessing": {"name": "Namekian Wish", "desc": "+2000 Max HP.", "cost": 1500},
    "heavy_boots": {"name": "Heavy Boots", "desc": "+500 Max HP, -5% Dodge.", "cost": 400},
    "ultra_holy_water": {"name": "Sacred Water", "desc": "+300 PL, +2% Crit.", "cost": 550},
    "protein_shake": {"name": "Saiyan Protein", "desc": "+300 HP.", "cost": 200},
    "advanced_armor": {"name": "Elite Armor", "desc": "-15% Dmg Taken.", "cost": 1100},
    "oxygen_mask": {"name": "Void Mask", "desc": "Prevents Stun.", "cost": 450},
    "stardust_shard": {"name": "Stardust", "desc": "+25% Crit Damage.", "cost": 850},
    "gravity_cuffs": {"name": "PL Dampeners", "desc": "Double rewards next wave.", "cost": 750},
    "miso_soup": {"name": "Chi-Chi's Soup", "desc": "Restore 50% HP.", "cost": 150},
    "training_sword": {"name": "Z-Sword Shard", "desc": "+750 PL.", "cost": 950}
}

class GameState:
    def __init__(self):
        self.reset()

    def reset(self, char_type="goku"):
        self.wave = 1
        self.char_type = char_type
        self.zeni = 500
        self.ki = 100
        self.current_shop = []
        self.defense_mod = 1.0
        self.crit_chance = 0.05
        self.lifesteal = 0.0
        self.sb_cooldown = 0
        
        if char_type == "vegeta": self.pl, self.base_max_hp = 18000, 5000
        elif char_type == "nappa": self.pl, self.base_max_hp = 4000, 3500
        elif char_type == "raditz": self.pl, self.base_max_hp = 1200, 1500
        else: self.pl, self.base_max_hp = 415, 800
            
        self.update_stats()
        self.hp = self.max_hp
        self.enemy = self.spawn_enemy()

    def update_stats(self):
        self.max_hp = int(self.base_max_hp + (self.pl * 0.05))

    def spawn_enemy(self):
        if self.wave == 30: return {"name": "VEGETA", "hp": 10000, "max_hp": 10000, "pl": 18000}
        if self.wave == 20: return {"name": "NAPPA", "hp": 4500, "max_hp": 4500, "pl": 4000}
        if self.wave == 10: return {"name": "RADITZ", "hp": 1500, "max_hp": 1500, "pl": 1500}
        
        if self.wave < 10: pl = 400 + (self.wave - 1) * 75
        elif self.wave < 20: pl = 1600 + (self.wave - 11) * 268
        elif self.wave < 30: pl = 4500 + (self.wave - 21) * 812
        else: pl = 18000 + (self.wave - 30) * 1200
            
        hp = 300 + (self.wave * 200)
        return {"name": "SAIBAMAN", "hp": hp, "max_hp": hp, "pl": pl}

    def generate_shop(self):
        keys = random.sample(list(ALL_SHOP_ITEMS.keys()), 4)
        self.current_shop = [{"id": k, **ALL_SHOP_ITEMS[k]} for k in keys]

state = GameState()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get-unlocked')
def get_unlocked_route():
    return jsonify({"unlocked": get_unlocked()})

@app.route('/select-char', methods=['POST'])
def select_char():
    data = request.get_json()
    char = data.get('character', 'goku')
    state.reset(char)
    return jsonify({"player": vars(state), "enemy": state.enemy})

@app.route('/battle-action', methods=['POST'])
def battle_action():
    data = request.get_json()
    skill = data.get('skill')
    
    base_dmg = 55 if skill == 'jab' else 260 if skill == 'kamehameha' else 650
    final_dmg = int(base_dmg * (1 + (state.pl / 500)))
    is_crit = random.random() < state.crit_chance
    if is_crit: final_dmg = int(final_dmg * 1.5)

    state.enemy["hp"] = max(0, state.enemy["hp"] - final_dmg)
    
    if state.lifesteal > 0:
        state.hp = min(state.max_hp, state.hp + int(final_dmg * state.lifesteal))

    enemy_msg = ""
    game_over = False
    if state.enemy["hp"] > 0:
        e_dmg = int(state.enemy["pl"] * 0.08 * state.defense_mod)
        state.hp = max(0, state.hp - e_dmg)
        enemy_msg = f"{state.enemy['name']} attacks for {e_dmg}!"
        if state.hp <= 0: game_over = True
    else:
        if state.enemy["name"] in ["RADITZ", "NAPPA", "VEGETA"]:
            save_unlock(state.enemy["name"].lower())
        state.pl += int(state.enemy["pl"] * 0.10)
        state.zeni += 200 + (state.wave * 25)
        state.generate_shop()

    state.sb_cooldown = max(0, state.sb_cooldown - 1)
    return jsonify({
        "message": f"{final_dmg} damage!",
        "enemy_msg": enemy_msg,
        "player": vars(state),
        "enemy": state.enemy,
        "enemy_killed": state.enemy["hp"] <= 0,
        "game_over": game_over,
        "is_crit": is_crit,
        "shop_items": state.current_shop
    })

@app.route('/purchase', methods=['POST'])
def purchase():
    item_id = request.get_json().get('item_id')
    item = ALL_SHOP_ITEMS.get(item_id)
    if item and state.zeni >= item['cost']:
        state.zeni -= item['cost']
        if item_id == "senzu": state.hp = state.max_hp
        elif item_id == "training": state.pl += 500
        elif item_id == "scouter_v2": state.crit_chance = min(0.40, state.crit_chance + 0.10)
        elif item_id == "tail_regrow": state.lifesteal += 0.05
        elif item_id == "fruit_tree": state.pl += 1000
        elif item_id == "dende_blessing": state.base_max_hp += 2000
        elif item_id == "miso_soup": state.hp = min(state.max_hp, state.hp + state.max_hp // 2)
        elif item_id == "protein_shake": state.base_max_hp += 300
        elif item_id == "weighted_gear": state.defense_mod *= 0.9
        elif item_id == "advanced_armor": state.defense_mod *= 0.85
        state.update_stats()
        return jsonify({"player": vars(state)})
    return jsonify({"error": "Failed"}), 400

@app.route('/next-enemy', methods=['POST'])
def next_enemy():
    state.wave += 1
    state.enemy = state.spawn_enemy()
    return jsonify({"enemy": state.enemy, "player": vars(state)})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)