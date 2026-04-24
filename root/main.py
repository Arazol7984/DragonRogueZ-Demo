import sqlite3
import json
import random
import os
from flask import Flask, render_template, jsonify, request

app = Flask(__name__)
app.secret_key = "dragon_rogue_z_2026_build"

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

# --- 25+ SHOP ITEMS ---
ALL_SHOP_ITEMS = {
    "senzu": {"name": "Senzu Bean", "desc": "Fully restores VIT.", "cost": 250},
    "training": {"name": "Gravity Room", "desc": "Increases PL by 500.", "cost": 600},
    "weighted_gear": {"name": "Weighted Gear", "desc": "+10% Defense permanently.", "cost": 450},
    "scouter_v2": {"name": "Scouter v2", "desc": "+10% Crit (Cap 40%).", "cost": 500},
    "ki_catalyst": {"name": "Ki Catalyst", "desc": "Start battles with +20 Ki.", "cost": 400},
    "fruit_tree": {"name": "Fruit of Might", "desc": "Massive +1000 PL boost.", "cost": 1200},
    "tail_regrow": {"name": "Tail Ointment", "desc": "+5% Lifesteal on hits.", "cost": 700},
    "capsule_coffee": {"name": "Capsule Coffee", "desc": "Regen 5 Ki every turn.", "cost": 350},
    "alloy_plating": {"name": "Alloy Plating", "desc": "Reduce enemy dmg by 50.", "cost": 550},
    "zenkai_boost": {"name": "Zenkai Injector", "desc": "Low HP dmg bonus +20%.", "cost": 800},
    "katchin_shield": {"name": "Katchin Shard", "desc": "Block 95% of damage.", "cost": 900},
    "adrenaline": {"name": "Saiyan Rage", "desc": "+25% Jab damage.", "cost": 300},
    "spare_battery": {"name": "Overclocker", "desc": "Skills cost 10% less Ki.", "cost": 650},
    "meditation_mat": {"name": "Old Mat", "desc": "Jab Ki gains increased.", "cost": 250},
    "prophetic_fish": {"name": "Oracle Snack", "desc": "10% chance to dodge.", "cost": 1000},
    "dende_blessing": {"name": "Namekian Wish", "desc": "+2000 Max HP.", "cost": 1500},
    "heavy_boots": {"name": "Heavy Boots", "desc": "+500 Max HP, -5% Dodge.", "cost": 400},
    "ultra_holy_water": {"name": "Sacred Water", "desc": "+300 PL, +2% Crit.", "cost": 550},
    "protein_shake": {"name": "Saiyan Protein", "desc": "Increases HP by 300.", "cost": 200},
    "advanced_armor": {"name": "Elite Armor", "desc": "Reduces dmg by 15%.", "cost": 1100},
    "oxygen_mask": {"name": "Void Mask", "desc": "Immune to turn-skip moves.", "cost": 450},
    "stardust_shard": {"name": "Stardust", "desc": "Crit Damage +25%.", "cost": 850},
    "gravity_cuffs": {"name": "PL Dampeners", "desc": "Double rewards next wave.", "cost": 750},
    "miso_soup": {"name": "Chi-Chi's Soup", "desc": "Restore 50% HP.", "cost": 150},
    "training_sword": {"name": "Z-Sword Fragment", "desc": "+750 PL.", "cost": 950}
}

# --- GAME ENGINE ---
class GameState:
    def __init__(self):
        self.reset()

    def reset(self, char_type="goku"):
        self.wave = 1
        self.char_type = char_type
        self.zeni = 500
        self.ki = 40
        self.current_shop = []
        self.defense_mod = 1.0
        self.crit_chance = 0.05
        self.lifesteal = 0.0
        self.ki_regen = 0
        self.sb_cooldown = 0
        
        # Power Level Normalization
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
        # Boss Logic
        if self.wave == 30:
            return {"name": "VEGETA", "hp": 10000, "max_hp": 10000, "pl": 18000, "moves": ["Galick Gun", "Final Burst"]}
        elif self.wave == 20:
            return {"name": "NAPPA", "hp": 4500, "max_hp": 4500, "pl": 4000, "moves": ["DX Bomber", "Giant Storm"]}
        elif self.wave == 10:
            name = "ELITE SOLDIER" if self.char_type == "raditz" else "RADITZ"
            return {"name": name, "hp": 1500, "max_hp": 1500, "pl": 1500, "moves": ["Double Sunday", "Saturday Crush"]}

        # Normalized Zone Scaling
        if self.wave < 10:
            pl = 400 + (self.wave - 1) * 75 # Hits ~1000 at Wave 9
        elif self.wave < 20:
            pl = 1600 + (self.wave - 11) * 268 # Hits ~3750 at Wave 19
        elif self.wave < 30:
            pl = 4500 + (self.wave - 21) * 812 # Hits ~11000 at Wave 29
        else:
            pl = 18000 + (self.wave - 30) * 1200
            
        hp = 300 + (self.wave * 200)
        return {"name": "SAIBAMAN", "hp": hp, "max_hp": hp, "pl": pl, "moves": ["Acid Spray", "Tackle"]}

    def generate_shop(self):
        keys = list(ALL_SHOP_ITEMS.keys())
        selected_keys = random.sample(keys, 4)
        self.current_shop = [{"id": k, **ALL_SHOP_ITEMS[k]} for k in selected_keys]
        return self.current_shop

state = GameState()

@app.route('/')
def index(): return render_template('index.html')

@app.route('/select-char', methods=['POST'])
def select_char():
    data = request.get_json()
    char = data.get('character', 'goku')
    state.reset(char)
    return jsonify({"status": "success", "player": vars(state), "enemy": state.enemy})

@app.route('/battle-action', methods=['POST'])
def battle_action():
    data = request.get_json()
    skill = data.get('skill')
    
    # Spirit Bomb Cooldown
    if skill == 'spirit_bomb':
        if state.sb_cooldown > 0:
            return jsonify({"message": f"Spirit Bomb cooling down! ({state.sb_cooldown} turns)", "player": vars(state)}), 400
        state.sb_cooldown = 3 # Ready in 2 turns

    # Raditz Move Restrictions
    display_skill = skill
    if state.char_type == "raditz" and skill in ['jab', 'ki_jab']:
        display_skill = "Tail Strike" # Raditz uses basic instead of jabs
    
    # Player Math
    base_dmg = 40 if skill == 'jab' else 150 if skill == 'kamehameha' else 400
    scaling = pow(1 + (state.pl / 1000), 1.2)
    final_dmg = int(base_dmg * scaling)
    
    # Apply Crit
    is_crit = random.random() < state.crit_chance
    if is_crit: final_dmg = int(final_dmg * 1.5)

    # Apply Lifesteal
    heal = int(final_dmg * state.lifesteal)
    state.hp = min(state.max_hp, state.hp + heal)

    state.enemy["hp"] = max(0, state.enemy["hp"] - final_dmg)
    enemy_killed = state.enemy["hp"] <= 0

    enemy_msg = ""
    if not enemy_killed:
        e_dmg = int(state.enemy["pl"] * 0.12 * state.defense_mod)
        state.hp = max(0, state.hp - e_dmg)
        enemy_msg = f"{state.enemy['name']} attacks for {e_dmg} damage!"
        
        # Check Death
        if state.hp <= 0:
            return jsonify({"game_over": True, "message": "You were defeated!"})

    if enemy_killed:
        # Dynamic PL Gain (10% of Enemy PL)
        pl_gain = int(state.enemy["pl"] * 0.10)
        state.pl += pl_gain
        # Dynamic Zeni (200 + 25 per wave)
        state.zeni += 200 + (state.wave * 25)
        state.generate_shop()
        state.update_stats()

    state.sb_cooldown = max(0, state.sb_cooldown - 1)
    return jsonify({"message": f"Used {display_skill}!", "enemy_msg": enemy_msg, "player": vars(state), "enemy_killed": enemy_killed})

@app.route('/purchase', methods=['POST'])
def purchase():
    data = request.get_json()
    item_id = data.get('item_id')
    item = ALL_SHOP_ITEMS.get(item_id)
    
    if item and state.zeni >= item['cost']:
        state.zeni -= item['cost']
        if item_id == "senzu": state.hp = state.max_hp
        elif item_id == "training": state.pl += 500
        elif item_id == "scouter_v2": state.crit_chance = min(0.40, state.crit_chance + 0.10)
        elif item_id == "tail_regrow": state.lifesteal += 0.05
        elif item_id == "dende_blessing": state.base_max_hp += 2000
        elif item_id == "protein_shake": state.base_max_hp += 300
        
        state.update_stats()
        return jsonify({"player": vars(state)})
    return jsonify({"error": "No Zeni"}), 400

@app.route('/next-enemy', methods=['POST'])
def next_enemy():
    state.wave += 1
    state.enemy = state.spawn_enemy()
    return jsonify({"wave": state.wave, "enemy": state.enemy, "player": vars(state)})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)