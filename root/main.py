import sqlite3
import json
import random
import os
from flask import Flask, render_template, jsonify, request, make_response

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dragon_rogue_z_2026_build")

_shared_state = None

# ─────────────────────────────────────────────────────────────────────────────
#  DATABASE
# ─────────────────────────────────────────────────────────────────────────────

def init_db():
    conn = sqlite3.connect("save_data.db")
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS progress
                 (id INTEGER PRIMARY KEY, unlocked_chars TEXT, zenkai_level INTEGER)""")
    c.execute("SELECT COUNT(*) FROM progress")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO progress (unlocked_chars, zenkai_level) VALUES (?, ?)",
                  (json.dumps(["goku"]), 0))
    conn.commit()
    conn.close()


def get_save_data():
    try:
        conn = sqlite3.connect("save_data.db")
        c = conn.cursor()
        c.execute("SELECT unlocked_chars, zenkai_level FROM progress WHERE id = 1")
        row = c.fetchone()
        conn.close()
        return (json.loads(row[0]), row[1]) if row else (["goku"], 0)
    except (sqlite3.Error, json.JSONDecodeError, TypeError, ValueError):
        return (["goku"], 0)


def save_unlock(char_id):
    if not char_id:
        return
    chars, _ = get_save_data()
    if char_id not in chars:
        chars.append(char_id)
        conn = sqlite3.connect("save_data.db")
        c = conn.cursor()
        c.execute("UPDATE progress SET unlocked_chars = ? WHERE id = 1", (json.dumps(chars),))
        conn.commit()
        conn.close()


def save_zenkai(level):
    conn = sqlite3.connect("save_data.db")
    c = conn.cursor()
    c.execute("UPDATE progress SET zenkai_level = ? WHERE id = 1", (level,))
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────────────────────────────────────
#  STATIC GAME DATA
# ─────────────────────────────────────────────────────────────────────────────

CHAR_ROSTER = {
    "goku":     {"base_pl": 415,   "base_hp": 800,  "sprite_set": True,  "unlock_by": None,     "category": "Z-WARRIORS"},
    "tien":     {"base_pl": 180,   "base_hp": 700,  "sprite_set": False, "unlock_by": None,     "category": "Z-WARRIORS"},
    "yamcha":   {"base_pl": 120,   "base_hp": 650,  "sprite_set": False, "unlock_by": None,     "category": "Z-WARRIORS"},
    "piccolo":  {"base_pl": 320,   "base_hp": 750,  "sprite_set": False, "unlock_by": None,     "category": "Z-WARRIORS"},
    "krillin":  {"base_pl": 210,   "base_hp": 700,  "sprite_set": False, "unlock_by": None,     "category": "Z-WARRIORS"},
    "chiaotzu": {"base_pl": 90,    "base_hp": 500,  "sprite_set": False, "unlock_by": None,     "category": "Z-WARRIORS"},
    "raditz":   {"base_pl": 1200,  "base_hp": 1500, "sprite_set": True,  "unlock_by": "RADITZ", "category": "RIVALS"},
    "nappa":    {"base_pl": 4000,  "base_hp": 3500, "sprite_set": True,  "unlock_by": "NAPPA",  "category": "RIVALS"},
    "vegeta":   {"base_pl": 18000, "base_hp": 5000, "sprite_set": True,  "unlock_by": "VEGETA", "category": "RIVALS"},
}

MOVES = {
    "jab":            {"base_dmg": 60,  "ki_cost": 0,  "ki_gain": 10},
    "slam":           {"base_dmg": 160, "ki_cost": 15, "ki_gain": 0},
    "kamehameha":     {"base_dmg": 320, "ki_cost": 30, "ki_gain": 0},
    "double_sunday":  {"base_dmg": 280, "ki_cost": 30, "ki_gain": 0},
    "bomber_dx":      {"base_dmg": 340, "ki_cost": 30, "ki_gain": 0},
    "galick_gun":     {"base_dmg": 360, "ki_cost": 30, "ki_gain": 0},
    "spirit_bomb":    {"base_dmg": 850, "ki_cost": 80, "ki_gain": 0},
    "saturday_crash": {"base_dmg": 700, "ki_cost": 80, "ki_gain": 0},
    "mouth_beam":     {"base_dmg": 800, "ki_cost": 80, "ki_gain": 0},
    "final_flash":    {"base_dmg": 900, "ki_cost": 80, "ki_gain": 0},
    "guard":          {"base_dmg": 0,   "ki_cost": 0,  "ki_gain": 5},
}

SAGAS = [
    {"name": "SAIYAN",  "start": 1,   "end": 30},
    {"name": "NAMEK",   "start": 31,  "end": 60},
    {"name": "FRIEZA",  "start": 61,  "end": 90},
    {"name": "ANDROID", "start": 91,  "end": 120},
    {"name": "CELL",    "start": 121, "end": 150},
    {"name": "BUU",     "start": 151, "end": 999},
]

ENEMY_POOLS = {
    "SAIYAN": {
        "minions": [
            # hp_scale and pl_scale kept gentle so Sector 1-9 is beatable without upgrades
            {"name": "SAIBAMAN",       "base_hp": 280, "hp_scale": 70,  "base_pl": 900,  "pl_scale": 1.08},
            {"name": "FRIEZA SOLDIER", "base_hp": 300, "hp_scale": 75,  "base_pl": 800,  "pl_scale": 1.06},
        ],
        "bosses": {
            10: {"name": "RADITZ", "hp": 1800,  "pl": 1200,  "unlock": "raditz"},
            20: {"name": "NAPPA",  "hp": 5500,  "pl": 3800,  "unlock": "nappa"},
            30: {"name": "VEGETA", "hp": 22000, "pl": 16000, "unlock": "vegeta"},
        },
    },
    "NAMEK": {
        "minions": [
            {"name": "NAMEKIAN WARRIOR", "base_hp": 500, "hp_scale": 160, "base_pl": 2800, "pl_scale": 1.12},
            {"name": "FRIEZA SOLDIER",   "base_hp": 480, "hp_scale": 150, "base_pl": 2600, "pl_scale": 1.10},
        ],
        "bosses": {
            40: {"name": "DODORIA", "hp": 12000,  "pl": 22000,  "unlock": None},
            50: {"name": "ZARBON",  "hp": 20000,  "pl": 23000,  "unlock": None},
            60: {"name": "FRIEZA",  "hp": 100000, "pl": 530000, "unlock": None},
        },
    },
}

ENEMY_MODIFIERS = {
    "NONE":      {"hp_mult": 1.0, "pl_mult": 1.0, "dodge": 0.0,  "dmg_mult": 1.0, "armor": 0},
    "ALPHA":     {"hp_mult": 1.3, "pl_mult": 1.3, "dodge": 0.0,  "dmg_mult": 1.0, "armor": 0},
    "SWIFT":     {"hp_mult": 1.0, "pl_mult": 1.0, "dodge": 0.25, "dmg_mult": 1.0, "armor": 0},
    "ARMORED":   {"hp_mult": 1.2, "pl_mult": 1.0, "dodge": 0.0,  "dmg_mult": 0.9, "armor": 150},
    "BERSERKER": {"hp_mult": 1.0, "pl_mult": 1.2, "dodge": 0.0,  "dmg_mult": 1.4, "armor": 0},
}

_MODIFIER_POOL = (
    ["NONE"] * 40 + ["ALPHA"] * 20 + ["SWIFT"] * 15 +
    ["ARMORED"] * 15 + ["BERSERKER"] * 10
)

ALL_SHOP_ITEMS = {
    "senzu":          {"name": "Senzu Bean",         "desc": "Fully restores HP and clears all debuffs.",        "base_cost": 120},
    "gravity_x10":    {"name": "10x Gravity",        "desc": "Big PL boost, costs 10% of current HP.",          "base_cost": 180},
    "gravity_x100":   {"name": "100x Gravity",       "desc": "Massive PL boost, scales with Sector.",           "base_cost": 450},
    "scouter_v3":     {"name": "Prototype Scouter",  "desc": "+15% Crit chance.",                               "base_cost": 350},
    "ki_overdrive":   {"name": "Ki Overdrive",       "desc": "Doubles Ki gain per action.",                     "base_cost": 250},
    "fruit_tree":     {"name": "Fruit of Might",     "desc": "+15% permanent damage output.",                   "base_cost": 500},
    "tail_regrow":    {"name": "Ancient Ointment",   "desc": "+8% Lifesteal on every hit.",                     "base_cost": 400},
    "alloy_plating":  {"name": "Katchin Armor",      "desc": "Reduces all incoming damage by 150 flat.",        "base_cost": 400},
    "adrenaline":     {"name": "Saiyan Pride",       "desc": "Damage rises the lower your HP falls.",           "base_cost": 300},
    "prophetic_fish": {"name": "Oracle Snack",       "desc": "+12% Dodge chance.",                              "base_cost": 600},
    "dende_blessing": {"name": "Grand Elder's Gift", "desc": "+2500 max HP permanently.",                       "base_cost": 750},
    "z_sword":        {"name": "Z-Sword Fragment",   "desc": "+20% Defense Penetration.",                       "base_cost": 550},
    "spirit_water":   {"name": "Ultra Divine Water", "desc": "Randomly boosts one stat significantly.",         "base_cost": 400},
    "yardrat_manual": {"name": "Yardrat Secret",     "desc": "+20% Dodge and Ki Regen boost.",                  "base_cost": 500},
}


# ─────────────────────────────────────────────────────────────────────────────
#  GAME STATE
# ─────────────────────────────────────────────────────────────────────────────

class GameState:
    def __init__(self):
        self.reset()

    def reset(self, char_type="goku"):
        cdata = CHAR_ROSTER.get(char_type, CHAR_ROSTER["goku"])
        _, self.zenkai_level = get_save_data()
        zm = 1 + self.zenkai_level * 0.1
        self.char = char_type
        self.wave = 1
        self.pl = int(cdata["base_pl"] * zm)
        self.base_max_hp = cdata["base_hp"]
        self.update_stats()
        self.hp = self.max_hp
        self.ki = 100
        self.ki_regen = 8
        self.ki_gain_mult = 1.0
        self.crit_chance = 0.05
        self.dodge_chance = 0.03
        self.def_pen = 0.0
        self.lifesteal = 0.0
        self.flat_reduction = 0
        self.defense_mod = 1.0
        self.outgoing_damage_mult = 1.0
        self.adrenaline_scale = 0.0
        self.is_guarding = False
        self.status_effects = []
        self.zeni = 850
        self.current_shop = []
        self.enemy = self.spawn_enemy()

    def update_stats(self):
        self.max_hp = int(self.base_max_hp + self.pl * 0.06)

    def get_saga(self):
        for s in SAGAS:
            if s["start"] <= self.wave <= s["end"]:
                return s["name"]
        return "UNKNOWN"

    def spawn_enemy(self):
        saga_name = self.get_saga()
        pool = ENEMY_POOLS.get(saga_name, ENEMY_POOLS["SAIYAN"])

        if self.wave % 10 == 0:
            boss = pool["bosses"].get(self.wave)
            if boss:
                return {
                    "name": boss["name"],
                    "hp": boss["hp"], "max_hp": boss["hp"],
                    "pl": boss["pl"], "boss": True,
                    "modifier": None, "dodge": 0.0,
                    "armor": 0, "dmg_mult": 1.0,
                    "unlock": boss.get("unlock"),
                }
            hp = 25000 + self.wave * 2000
            pl = 18000 + self.wave * 500
            return {
                "name": f"ELITE WARRIOR W{self.wave}",
                "hp": hp, "max_hp": hp, "pl": pl, "boss": True,
                "modifier": None, "dodge": 0.0, "armor": 0,
                "dmg_mult": 1.0, "unlock": None,
            }

        template = random.choice(pool["minions"])
        mod_key = random.choice(_MODIFIER_POOL)
        mod = ENEMY_MODIFIERS[mod_key]
        hp = int((template["base_hp"] + self.wave * template["hp_scale"]) * mod["hp_mult"])
        pl = int((template["base_pl"] * (template["pl_scale"] ** (self.wave - 1))) * mod["pl_mult"])
        return {
            "name": template["name"],
            "hp": hp, "max_hp": hp, "pl": pl, "boss": False,
            "modifier": mod_key if mod_key != "NONE" else None,
            "dodge": mod["dodge"], "armor": mod["armor"],
            "dmg_mult": mod["dmg_mult"], "unlock": None,
        }

    def apply_zenkai(self):
        if self.hp < self.max_hp * 0.15:
            self.zenkai_level += 1
            save_zenkai(self.zenkai_level)
            return True
        return False

    def generate_shop(self):
        keys = random.sample(list(ALL_SHOP_ITEMS.keys()), min(6, len(ALL_SHOP_ITEMS)))
        scale = 1 + self.wave * 0.07
        self.current_shop = []
        for k in keys:
            item = ALL_SHOP_ITEMS[k].copy()
            item["id"] = k
            item["cost"] = int(item["base_cost"] * scale)
            self.current_shop.append(item)


def current_state():
    global _shared_state
    if _shared_state is None:
        _shared_state = GameState()
    return _shared_state


init_db()


# ─────────────────────────────────────────────────────────────────────────────
#  COMBAT HELPER
# ─────────────────────────────────────────────────────────────────────────────

def _enemy_attack(state):
    if random.random() < state.dodge_chance:
        return f"{state.enemy['name']} missed!", False
    e_base = state.enemy["pl"] * 0.07
    if state.enemy.get("boss"):
        e_base *= 1.25
    dmg_mult = state.enemy.get("dmg_mult", 1.0)
    e_dmg = int(e_base * dmg_mult * state.defense_mod) - state.flat_reduction
    if state.is_guarding:
        e_dmg = int(e_dmg * 0.25)
    e_dmg = max(20, e_dmg)
    state.hp = max(0, state.hp - e_dmg)
    return f"{state.enemy['name']} counter-attacks for {e_dmg:,}!", state.hp <= 0


# ─────────────────────────────────────────────────────────────────────────────
#  ROUTES
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    resp = make_response(render_template("index.html"))
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


@app.route("/get-roster")
def get_roster():
    unlocked, zenkai = get_save_data()
    roster = []
    for char_id, cdata in CHAR_ROSTER.items():
        roster.append({
            "id":           char_id,
            "base_pl":      cdata["base_pl"],
            "base_hp":      cdata["base_hp"],
            "unlocked":     char_id in unlocked,
            "sprite_ready": cdata["sprite_set"],
            "unlock_by":    cdata["unlock_by"],
            "category":     cdata["category"],
        })
    return jsonify({"roster": roster, "zenkai": zenkai})


@app.route("/select-char", methods=["POST"])
def select_char():
    data = request.get_json()
    char = data.get("character", "goku")
    if char not in CHAR_ROSTER:
        return jsonify({"error": "Unknown character"}), 400
    unlocked, _ = get_save_data()
    if char not in unlocked:
        return jsonify({"error": "Character not unlocked"}), 403
    state = current_state()
    state.reset(char)
    return jsonify({"player": vars(state), "enemy": state.enemy})


@app.route("/battle-action", methods=["POST"])
def battle_action():
    state = current_state()
    data = request.get_json()
    skill = data.get("skill", "jab")

    state.ki = min(100, state.ki + state.ki_regen)

    move = MOVES.get(skill, MOVES["jab"])
    ki_cost = move["ki_cost"]
    if state.ki < ki_cost:
        return jsonify({"error": f"Insufficient Ki — need {ki_cost}, have {int(state.ki)}"}), 400

    state.ki -= ki_cost

    if skill == "guard":
        state.is_guarding = True
        state.ki = min(100, state.ki + int(move["ki_gain"] * state.ki_gain_mult))
        enemy_msg, game_over = _enemy_attack(state)
        return jsonify({
            "message":     "GUARDING — incoming damage reduced by 75%",
            "enemy_msg":   enemy_msg,
            "player":      vars(state),
            "enemy":       state.enemy,
            "enemy_killed": False,
            "game_over":   game_over,
            "zenkai":      False,
            "shop_items":  [],
        })

    state.is_guarding = False
    ki_gain = int(move["ki_gain"] * state.ki_gain_mult)
    if ki_gain:
        state.ki = min(100, state.ki + ki_gain)

    raw_dmg = move["base_dmg"] * (1 + state.pl / 380)
    if state.adrenaline_scale > 0 and state.max_hp > 0:
        raw_dmg *= 1 + state.adrenaline_scale * (1 - state.hp / state.max_hp)
    raw_dmg *= state.outgoing_damage_mult
    final_dmg = int(raw_dmg * (1 + state.def_pen))

    is_crit = random.random() < state.crit_chance
    if is_crit:
        final_dmg = int(final_dmg * 1.6)

    dodged = state.enemy.get("dodge", 0.0) > 0 and random.random() < state.enemy["dodge"]
    if dodged:
        final_dmg = 0

    armor = state.enemy.get("armor", 0)
    if armor and final_dmg > 0:
        final_dmg = max(1, final_dmg - armor)

    state.enemy["hp"] = max(0, state.enemy["hp"] - final_dmg)

    if final_dmg > 0 and state.lifesteal > 0:
        state.hp = min(state.max_hp, state.hp + int(final_dmg * state.lifesteal))

    if dodged:
        player_msg = f"{state.enemy['name']} evaded your attack!"
    elif is_crit:
        player_msg = f"CRITICAL HIT! {final_dmg:,} damage!"
    else:
        player_msg = f"{final_dmg:,} damage dealt!"

    enemy_killed = state.enemy["hp"] <= 0
    enemy_msg = ""
    game_over = False
    zenkai_triggered = False

    if enemy_killed:
        if state.enemy.get("boss") and state.enemy.get("unlock"):
            save_unlock(state.enemy["unlock"])
        state.zeni += 180 + state.wave * 15
        if state.enemy.get("boss"):
            state.zeni += 600
        zenkai_triggered = state.apply_zenkai()
        state.pl += int(state.enemy["pl"] * 0.18)
        state.generate_shop()
    else:
        enemy_msg, game_over = _enemy_attack(state)

    return jsonify({
        "message":      player_msg,
        "enemy_msg":    enemy_msg,
        "player":       vars(state),
        "enemy":        state.enemy,
        "enemy_killed": enemy_killed,
        "game_over":    game_over,
        "zenkai":       zenkai_triggered,
        "shop_items":   state.current_shop,
    })


@app.route("/battle-status")
def battle_status():
    state = current_state()
    p = vars(state)
    p["saga"] = state.get_saga()
    return jsonify({"player": p})


@app.route("/purchase", methods=["POST"])
def purchase():
    state = current_state()
    item_id = request.get_json().get("item_id")
    item = next((i for i in state.current_shop if i["id"] == item_id), None)
    if not item or state.zeni < item["cost"]:
        return jsonify({"error": "Cannot purchase — insufficient Zeni or item unavailable"}), 400

    state.zeni -= item["cost"]
    s = 1 + state.wave * 0.08

    if item_id == "senzu":
        state.hp = state.max_hp
        state.status_effects = []
    elif item_id == "gravity_x10":
        state.pl += int(350 * s)
        state.hp = max(1, int(state.hp * 0.9))
    elif item_id == "gravity_x100":
        state.pl += int(800 * s)
    elif item_id == "dende_blessing":
        state.base_max_hp += 2500
    elif item_id == "z_sword":
        state.def_pen += 0.20
    elif item_id == "prophetic_fish":
        state.dodge_chance = min(0.45, state.dodge_chance + 0.12)
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
        state.ki_regen = min(20, state.ki_regen + 3)
    elif item_id == "spirit_water":
        roll = random.choice(["pl", "pl2", "hp", "crit", "dodge", "def_pen"])
        if roll == "pl":
            state.pl = int(state.pl * 1.15)
        elif roll == "pl2":
            state.pl += int(600 * s)
        elif roll == "hp":
            state.base_max_hp += int(1200 * s)
        elif roll == "crit":
            state.crit_chance = min(0.5, state.crit_chance + 0.1)
        elif roll == "dodge":
            state.dodge_chance = min(0.45, state.dodge_chance + 0.1)
        else:
            state.def_pen += 0.12

    state.update_stats()
    return jsonify({"player": vars(state)})


@app.route("/next-enemy", methods=["POST"])
def next_enemy():
    state = current_state()
    state.wave += 1
    state.is_guarding = False
    state.enemy = state.spawn_enemy()
    return jsonify({"enemy": state.enemy, "player": vars(state)})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
