import sqlite3
import json
import random
import os
import uuid
from flask import Flask, render_template, jsonify, request, session

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dragon_rogue_z_2026_build_ULTIMATE")
# Force Jinja to re-read templates each request and never let the browser
# cache the SPA shell, so frontend edits show up on a normal refresh.
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.jinja_env.auto_reload = True

BUILD_TAG = "KERNEL_V7.9.2 / 2026-04-25"

@app.after_request
def _add_no_cache(resp):
    if request.path == '/' or request.path.endswith('.html'):
        resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        resp.headers['Pragma'] = 'no-cache'
        resp.headers['Expires'] = '0'
    resp.headers['X-DRZ-Build'] = BUILD_TAG
    return resp

# Single-browser-tab game instances keyed by Flask session (see current_state()).
# This app is designed for local / single-player use; hosting for many concurrent
# users would need session cleanup or external storage for game_states.
game_states = {}

# Local single-player fallback: one shared GameState used when sessions are
# unavailable (e.g. cookies blocked). This guarantees that progression like
# wave counter and shop never silently resets between requests.
_shared_state = None

# --- DATABASE & ROSTER LOGIC ---
def init_db():
    """Initializes the SQLite database to track character unlocks and permanent Zenkai boosts."""
    conn = sqlite3.connect('save_data.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS progress 
                 (id INTEGER PRIMARY KEY, unlocked_chars TEXT, zenkai_level INTEGER)''')
    c.execute("SELECT COUNT(*) FROM progress")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO progress (unlocked_chars, zenkai_level) VALUES (?, ?)", (json.dumps(['goku']), 0))
    conn.commit()
    conn.close()

def get_save_data():
    try:
        conn = sqlite3.connect('save_data.db')
        c = conn.cursor()
        c.execute("SELECT unlocked_chars, zenkai_level FROM progress WHERE id = 1")
        row = c.fetchone()
        conn.close()
        return (json.loads(row[0]), row[1]) if row else (['goku'], 0)
    except (sqlite3.Error, json.JSONDecodeError, TypeError, ValueError):
        return (['goku'], 0)


def boss_unlock_char_id(enemy_name):
    """Map boss display name to roster id for unlocks. Post-30 elites do not unlock."""
    if not enemy_name:
        return None
    n = enemy_name.upper().strip()
    if n == "RADITZ":
        return "raditz"
    if n == "NAPPA":
        return "nappa"
    if n == "VEGETA":
        return "vegeta"
    return None


def current_state():
    """Return the GameState bound to this client.

    Tries the Flask session first (multi-browser friendly). Falls back to a
    process-wide shared state so single-player local play never loses wave
    progression even if the session cookie is missing or rejected.
    """
    global _shared_state
    try:
        if 'game_sid' not in session:
            session['game_sid'] = str(uuid.uuid4())
            session.permanent = True
        sid = session['game_sid']
        if sid not in game_states:
            if _shared_state is None:
                _shared_state = GameState()
            # Reuse the shared state for the first session bound on this server
            # so refreshes / new tabs continue the same run by default.
            game_states[sid] = _shared_state
        return game_states[sid]
    except RuntimeError:
        if _shared_state is None:
            _shared_state = GameState()
        return _shared_state

def save_unlock(char_id):
    chars, zenkai = get_save_data()
    if char_id not in chars:
        chars.append(char_id)
        conn = sqlite3.connect('save_data.db')
        c = conn.cursor()
        c.execute("UPDATE progress SET unlocked_chars = ? WHERE id = 1", (json.dumps(chars),))
        conn.commit()
        conn.close()

init_db()

# --- EXPANDED SHOP SYSTEM ---
ALL_SHOP_ITEMS = {
    "senzu": {"name": "Senzu Bean", "desc": "Fully restores HP and clears status effects.", "base_cost": 120},
    "gravity_x10": {"name": "10x Gravity", "desc": "High PL boost, but reduces current HP by 10%.", "base_cost": 180},
    "gravity_x100": {"name": "100x Gravity", "desc": "Massive PL boost scaling with Wave.", "base_cost": 450},
    "scouter_v3": {"name": "Prototype Scouter", "desc": "+15% Crit and reveals Enemy Weakness.", "base_cost": 350},
    "ki_overdrive": {"name": "Ki Overdrive", "desc": "Double Ki gain, but take 5% more damage.", "base_cost": 250},
    "fruit_tree": {"name": "Fruit of Might", "desc": "Permanent +15% damage multiplier.", "base_cost": 500},
    "tail_regrow": {"name": "Ancient Ointment", "desc": "+8% Lifesteal per hit.", "base_cost": 400},
    "alloy_plating": {"name": "Katchin Armor", "desc": "Reduces all incoming damage by 150 flat.", "base_cost": 400},
    "adrenaline": {"name": "Saiyan Pride", "desc": "Damage increases as your HP decreases.", "base_cost": 300},
    "prophetic_fish": {"name": "Oracle Snack", "desc": "+12% Dodge chance.", "base_cost": 600},
    "dende_blessing": {"name": "Grand Elder's Gift", "desc": "Massive HP increase (+2500).", "base_cost": 750},
    "z_sword": {"name": "Z-Sword Fragment", "desc": "Grants 20% Defense Penetration.", "base_cost": 550},
    "spirit_water": {"name": "Ultra Divine Water", "desc": "Randomly boosts a stat significantly.", "base_cost": 400},
    "yardrat_manual": {"name": "Yardrat Secret", "desc": "+20% Speed (Dodge and Counter chance).", "base_cost": 500}
}

class GameState:
    def __init__(self):
        self.reset()

    def reset(self, char_type="goku"):
        self.wave = 1
        self.char = char_type # Synced with front-end name
        self.zeni = 500
        self.ki = 100
        self.current_shop = []
        self.defense_mod = 1.0
        self.crit_chance = 0.05
        self.lifesteal = 0.0
        self.ki_regen = 5
        self.flat_reduction = 0
        self.dodge_chance = 0.03
        self.def_pen = 0.0
        self.is_guarding = False
        self.status_effects = []
        self.ki_gain_mult = 1.0
        self.adrenaline_scale = 0.0
        self.outgoing_damage_mult = 1.0
        
        _, self.zenkai_level = get_save_data()
        
        zenkai_mult = 1 + (self.zenkai_level * 0.1)
        if char_type == "vegeta": self.pl, self.base_max_hp = int(18000 * zenkai_mult), 5000
        elif char_type == "nappa": self.pl, self.base_max_hp = int(4000 * zenkai_mult), 3500
        elif char_type == "raditz": self.pl, self.base_max_hp = int(1200 * zenkai_mult), 1500
        else: self.pl, self.base_max_hp = int(415 * zenkai_mult), 800
            
        self.update_stats()
        self.hp = self.max_hp
        self.enemy = self.spawn_enemy()

    def update_stats(self):
        self.max_hp = int(self.base_max_hp + (self.pl * 0.06))

    def spawn_enemy(self):
        if self.wave % 10 == 0:
            if self.wave == 10: return {"name": "RADITZ", "hp": 2400, "max_hp": 2400, "pl": 1500, "boss": True}
            if self.wave == 20: return {"name": "NAPPA", "hp": 6000, "max_hp": 6000, "pl": 4000, "boss": True}
            if self.wave == 30: return {"name": "VEGETA", "hp": 25000, "max_hp": 25000, "pl": 18000, "boss": True}
            hp = 25000 + (self.wave * 2000)
            pl = 18000 + (self.wave * 500)
            return {"name": f"ELITE SARENBAN W{self.wave}", "hp": hp, "max_hp": hp, "pl": pl, "boss": True}
        
        pl = int(400 * (1.15 ** (self.wave - 1)))
        hp = int(300 + (self.wave * 180))
        return {"name": "SAIBAMAN", "hp": hp, "max_hp": hp, "pl": pl, "boss": False}

    def apply_zenkai(self):
        if self.hp < (self.max_hp * 0.15):
            self.zenkai_level += 1
            conn = sqlite3.connect('save_data.db')
            c = conn.cursor()
            c.execute("UPDATE progress SET zenkai_level = ? WHERE id = 1", (self.zenkai_level,))
            conn.commit()
            conn.close()
            return True
        return False

    def generate_shop(self):
        keys = random.sample(list(ALL_SHOP_ITEMS.keys()), 6)
        scale = 1 + (self.wave * 0.12)
        self.current_shop = []
        for k in keys:
            item = ALL_SHOP_ITEMS[k].copy()
            item["id"] = k
            item["cost"] = int(item["base_cost"] * scale)
            self.current_shop.append(item)

@app.route('/')
def index():
    return render_template('index.html', build_tag=BUILD_TAG)

@app.route('/get-unlocked')
def get_unlocked_route():
    chars, zenkai = get_save_data()
    return jsonify({"unlocked": chars, "zenkai": zenkai})

@app.route('/select-char', methods=['POST'])
def select_char():
    state = current_state()
    data = request.get_json()
    char = data.get('character', 'goku')
    state.reset(char)
    return jsonify({"player": vars(state), "enemy": state.enemy})

@app.route('/battle-action', methods=['POST'])
def battle_action():
    state = current_state()
    data = request.get_json()
    skill = data.get('skill')
    
    ki_cost = 0
    base_dmg = 0
    if skill == 'guard': 
        state.is_guarding = True
    else:
        state.is_guarding = False
        # FIX: Individual skill damage and ki logic
        if skill in ['jab', 'rapid_attack', 'combo', 'kick']: 
            base_dmg = 60
            ki_add = int(10 * state.ki_gain_mult)
            state.ki = min(100, state.ki + ki_add)
        elif skill == 'slam':
            base_dmg = 160
            ki_cost = 15
        elif skill in ['kamehameha', 'double_sunday', 'bomber_dx', 'galick_gun']:
            base_dmg = 320
            ki_cost = 30
        elif skill in ['spirit_bomb', 'saturday_crash', 'mouth_beam', 'final_flash']:
            base_dmg = 850
            ki_cost = 80
            
    if state.ki < ki_cost:
        return jsonify({"error": "Insufficient Ki"}), 400
    
    state.ki -= ki_cost
    raw_dmg = base_dmg * (1 + (state.pl / 450))
    low_hp_bonus = 1.0
    if state.adrenaline_scale > 0 and state.max_hp > 0:
        low_hp_bonus += state.adrenaline_scale * (1.0 - (state.hp / state.max_hp))
    raw_dmg *= state.outgoing_damage_mult * low_hp_bonus
    final_dmg = int(raw_dmg * (1 + state.def_pen))
    
    is_crit = random.random() < state.crit_chance
    if is_crit: final_dmg = int(final_dmg * 1.6)

    state.enemy["hp"] = max(0, state.enemy["hp"] - final_dmg)
    if skill != 'guard' and state.lifesteal > 0 and final_dmg > 0:
        heal = int(final_dmg * state.lifesteal)
        state.hp = min(state.max_hp, state.hp + heal)
    
    enemy_msg = ""
    game_over = False
    zenkai_triggered = False
    
    if state.enemy["hp"] > 0:
        if random.random() < state.dodge_chance:
            enemy_msg = f"{state.enemy['name']} missed!"
        else:
            e_base = state.enemy["pl"] * 0.12
            if state.enemy.get("boss"): e_base *= 1.25
            e_dmg = int(e_base * state.defense_mod) - state.flat_reduction
            if state.is_guarding: e_dmg = int(e_dmg * 0.25)
            state.hp = max(0, state.hp - max(20, e_dmg))
            enemy_msg = f"{state.enemy['name']} counter-attacks for {max(20, e_dmg)}!"
            if state.hp <= 0: game_over = True
    else:
        if state.enemy.get("boss"):
            unlock_id = boss_unlock_char_id(state.enemy["name"])
            if unlock_id:
                save_unlock(unlock_id)
            state.zeni += 500
        zenkai_triggered = state.apply_zenkai()
        state.pl += int(state.enemy["pl"] * 0.12)
        cleared_wave = state.wave
        state.zeni += 100 + (cleared_wave * 25)
        # Advance the sector immediately so the HUD ticks up the moment the
        # enemy dies. /next-enemy only respawns; it must NOT bump the wave.
        state.wave = cleared_wave + 1
        state.generate_shop()

    return jsonify({
        "message": f"CRITICAL! {final_dmg}" if is_crit else f"{final_dmg} damage!",
        "enemy_msg": enemy_msg,
        "player": vars(state),
        "enemy": state.enemy,
        "enemy_killed": state.enemy["hp"] <= 0,
        "game_over": game_over,
        "zenkai": zenkai_triggered,
        "shop_items": state.current_shop
    })

@app.route('/purchase', methods=['POST'])
def purchase():
    state = current_state()
    item_id = request.get_json().get('item_id')
    item_data = next((i for i in state.current_shop if i["id"] == item_id), None)
    if not item_data or state.zeni < item_data["cost"]:
        return jsonify({"error": "Cannot buy"}), 400
    
    state.zeni -= item_data["cost"]
    s_scale = 1 + (state.wave * 0.08)

    if item_id == "senzu":
        state.hp = state.max_hp
        state.status_effects = []
    elif item_id == "gravity_x10":
        state.pl += int(350 * s_scale)
        state.hp = max(1, int(state.hp * 0.9))
    elif item_id == "gravity_x100":
        state.pl += int(800 * s_scale)
    elif item_id == "dende_blessing":
        state.base_max_hp += 2500
    elif item_id == "z_sword":
        state.def_pen += 0.15
    elif item_id == "prophetic_fish":
        state.dodge_chance = min(0.4, state.dodge_chance + 0.12)
    elif item_id == "scouter_v3":
        state.crit_chance = min(0.5, state.crit_chance + 0.15)
    elif item_id == "fruit_tree":
        state.outgoing_damage_mult *= 1.15
    elif item_id == "ki_overdrive":
        state.ki_gain_mult = 2.0
        state.defense_mod *= 1.05
    elif item_id == "tail_regrow":
        state.lifesteal = min(0.5, state.lifesteal + 0.08)
    elif item_id == "alloy_plating":
        state.flat_reduction += 150
    elif item_id == "adrenaline":
        state.adrenaline_scale = max(state.adrenaline_scale, 0.5)
    elif item_id == "yardrat_manual":
        state.dodge_chance = min(0.45, state.dodge_chance + 0.12)
    elif item_id == "spirit_water":
        roll = random.choice(["pl", "pl2", "hp", "crit", "dodge", "def_pen"])
        if roll == "pl":
            state.pl = int(state.pl * 1.15)
        elif roll == "pl2":
            state.pl += int(600 * s_scale)
        elif roll == "hp":
            state.base_max_hp += int(1200 * s_scale)
        elif roll == "crit":
            state.crit_chance = min(0.5, state.crit_chance + 0.1)
        elif roll == "dodge":
            state.dodge_chance = min(0.45, state.dodge_chance + 0.1)
        else:
            state.def_pen += 0.12
    
    state.update_stats()
    return jsonify({"player": vars(state)})

@app.route('/next-enemy', methods=['POST'])
def next_enemy():
    state = current_state()
    # Wave was already advanced when the previous enemy was defeated.
    # Just spawn the foe for the current wave.
    state.enemy = state.spawn_enemy()
    return jsonify({"enemy": state.enemy, "player": vars(state)})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)