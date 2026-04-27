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
                  (json.dumps(["goku", "goku_namek"]), 0))
    conn.commit()
    conn.close()


def get_save_data():
    try:
        conn = sqlite3.connect("save_data.db")
        c = conn.cursor()
        c.execute("SELECT unlocked_chars, zenkai_level FROM progress WHERE id = 1")
        row = c.fetchone()
        conn.close()
        return (json.loads(row[0]), row[1]) if row else (["goku", "goku_namek"], 0)
    except (sqlite3.Error, json.JSONDecodeError, TypeError, ValueError):
        return (["goku", "goku_namek"], 0)


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
#  TRANSFORMATION DATA
#  Per-character transform table: mult, HP drain %/turn, Ki drain/turn, def penalty
# ─────────────────────────────────────────────────────────────────────────────

CHAR_TRANSFORMS = {
    "goku": {
        "kaioken_x2": {"mult": 2.0,  "hp_drain": 0.050, "ki_drain": 0.0,  "def_pen": 1.10, "req": "kaioken", "label": "KAIOKEN x2"},
        "kaioken_x3": {"mult": 3.0,  "hp_drain": 0.075, "ki_drain": 0.0,  "def_pen": 1.15, "req": "kaioken", "label": "KAIOKEN x3"},
        "kaioken_x4": {"mult": 4.0,  "hp_drain": 0.100, "ki_drain": 0.0,  "def_pen": 1.20, "req": "kaioken", "label": "KAIOKEN x4"},
    },
    "goku_namek": {
        "kaioken_x2":   {"mult": 2.0,  "hp_drain": 0.020, "ki_drain": 0.0,  "def_pen": 1.10, "req": None,      "label": "KAIOKEN x2"},
        "kaioken_x5":   {"mult": 5.0,  "hp_drain": 0.050, "ki_drain": 0.0,  "def_pen": 1.20, "req": None,      "label": "KAIOKEN x5"},
        "kaioken_x10":  {"mult": 10.0, "hp_drain": 0.075, "ki_drain": 0.0,  "def_pen": 1.30, "req": None,      "label": "KAIOKEN x10"},
        "kaioken_x20":  {"mult": 20.0, "hp_drain": 0.100, "ki_drain": 0.0,  "def_pen": 1.40, "req": None,      "label": "KAIOKEN x20"},
        "super_saiyan": {"mult": 50.0, "hp_drain": 0.000, "ki_drain": 15.0, "def_pen": 1.00, "req": "ssj",     "label": "SUPER SAIYAN"},
    },
}


# ─────────────────────────────────────────────────────────────────────────────
#  STATIC GAME DATA
# ─────────────────────────────────────────────────────────────────────────────

CHAR_ROSTER = {
    # ── SAIYAN SAGA Z-WARRIORS ──────────────────────────────────────────────
    "goku":       {"name": "GOKU · SAIYAN", "base_pl": 416,     "base_hp": 800,   "sprite_set": True,  "unlock_by": None,          "category": "Z-WARRIORS", "saga": "SAIYAN"},
    "tien":       {"name": "TIEN",          "base_pl": 180,     "base_hp": 700,   "sprite_set": False, "unlock_by": None,          "category": "Z-WARRIORS", "saga": "SAIYAN"},
    "yamcha":     {"name": "YAMCHA",        "base_pl": 120,     "base_hp": 650,   "sprite_set": False, "unlock_by": None,          "category": "Z-WARRIORS", "saga": "SAIYAN"},
    "piccolo":    {"name": "PICCOLO",       "base_pl": 320,     "base_hp": 750,   "sprite_set": False, "unlock_by": None,          "category": "Z-WARRIORS", "saga": "SAIYAN"},
    "krillin":    {"name": "KRILLIN",       "base_pl": 210,     "base_hp": 700,   "sprite_set": False, "unlock_by": None,          "category": "Z-WARRIORS", "saga": "SAIYAN"},
    "chiaotzu":   {"name": "CHIAOTZU",      "base_pl": 90,      "base_hp": 500,   "sprite_set": False, "unlock_by": None,          "category": "Z-WARRIORS", "saga": "SAIYAN"},
    # ── SAIYAN SAGA RIVALS ──────────────────────────────────────────────────
    "raditz":     {"name": "RADITZ",        "base_pl": 1200,    "base_hp": 1500,  "sprite_set": True,  "unlock_by": "RADITZ",      "category": "RIVALS",     "saga": "SAIYAN"},
    "nappa":      {"name": "NAPPA",         "base_pl": 4000,    "base_hp": 3500,  "sprite_set": True,  "unlock_by": "NAPPA",       "category": "RIVALS",     "saga": "SAIYAN"},
    "vegeta":     {"name": "VEGETA",        "base_pl": 18000,   "base_hp": 5000,  "sprite_set": True,  "unlock_by": "VEGETA",      "category": "RIVALS",     "saga": "SAIYAN"},
    # ── NAMEK SAGA Z-WARRIORS ───────────────────────────────────────────────
    "goku_namek": {"name": "GOKU · NAMEK",  "base_pl": 5000,    "base_hp": 1200,  "sprite_set": True,  "unlock_by": None,          "category": "Z-WARRIORS", "saga": "NAMEK"},
    # ── NAMEK SAGA RIVALS ───────────────────────────────────────────────────
    "dodoria":    {"name": "DODORIA",       "base_pl": 22000,   "base_hp": 4000,  "sprite_set": False, "unlock_by": "DODORIA",     "category": "RIVALS",     "saga": "NAMEK"},
    "zarbon":     {"name": "ZARBON",        "base_pl": 23000,   "base_hp": 4500,  "sprite_set": False, "unlock_by": "ZARBON",      "category": "RIVALS",     "saga": "NAMEK"},
    "guldo":      {"name": "GULDO",         "base_pl": 11000,   "base_hp": 3000,  "sprite_set": False, "unlock_by": "GULDO",       "category": "RIVALS",     "saga": "NAMEK"},
    "recoome":    {"name": "RECOOME",       "base_pl": 71000,   "base_hp": 8000,  "sprite_set": False, "unlock_by": "RECOOME",     "category": "RIVALS",     "saga": "NAMEK"},
    "burter":     {"name": "BURTER",        "base_pl": 67000,   "base_hp": 7000,  "sprite_set": False, "unlock_by": "BURTER",      "category": "RIVALS",     "saga": "NAMEK"},
    "jeice":      {"name": "JEICE",         "base_pl": 67000,   "base_hp": 7000,  "sprite_set": False, "unlock_by": "JEICE",       "category": "RIVALS",     "saga": "NAMEK"},
    "ginyu":      {"name": "CAPTAIN GINYU", "base_pl": 120000,  "base_hp": 9000,  "sprite_set": False, "unlock_by": "GINYU",       "category": "RIVALS",     "saga": "NAMEK"},
    "frieza":     {"name": "FRIEZA",        "base_pl": 6000000, "base_hp": 15000, "sprite_set": False, "unlock_by": "FRIEZA 100%", "category": "RIVALS",     "saga": "NAMEK"},
}

MOVES = {
    "jab":            {"base_dmg": 60,  "ki_cost": 0,  "ki_gain": 10, "hp_cap": None},
    "slam":           {"base_dmg": 160, "ki_cost": 15, "ki_gain": 0,  "hp_cap": None},
    "kamehameha":     {"base_dmg": 320, "ki_cost": 30, "ki_gain": 0,  "hp_cap": None},
    "double_sunday":  {"base_dmg": 280, "ki_cost": 30, "ki_gain": 0,  "hp_cap": None},
    "bomber_dx":      {"base_dmg": 340, "ki_cost": 30, "ki_gain": 0,  "hp_cap": None},
    "galick_gun":     {"base_dmg": 360, "ki_cost": 30, "ki_gain": 0,  "hp_cap": None},
    "spirit_bomb":    {"base_dmg": 850, "ki_cost": 80, "ki_gain": 0,  "hp_cap": 0.68},
    "saturday_crash": {"base_dmg": 700, "ki_cost": 80, "ki_gain": 0,  "hp_cap": 0.68},
    "mouth_beam":     {"base_dmg": 800, "ki_cost": 80, "ki_gain": 0,  "hp_cap": 0.68},
    "final_flash":    {"base_dmg": 900, "ki_cost": 80, "ki_gain": 0,  "hp_cap": 0.72},
    "guard":          {"base_dmg": 0,   "ki_cost": 0,  "ki_gain": 5,  "hp_cap": None},
}

SAGAS = [
    {"name": "SAIYAN",  "start": 1,   "end": 30},
    {"name": "NAMEK",   "start": 31,  "end": 70},
    {"name": "FRIEZA",  "start": 71,  "end": 100},
    {"name": "ANDROID", "start": 101, "end": 130},
    {"name": "CELL",    "start": 131, "end": 160},
    {"name": "BUU",     "start": 161, "end": 999},
]

ENEMY_POOLS = {
    "SAIYAN": {
        "minions": [
            {"name": "SAIBAMAN",       "base_hp": 280, "hp_scale": 70,  "base_pl": 900,  "pl_scale": 1.08},
            {"name": "FRIEZA SOLDIER", "base_hp": 300, "hp_scale": 75,  "base_pl": 800,  "pl_scale": 1.06},
        ],
        "bosses": {
            10: {"name": "RADITZ", "hp": 1800,  "pl": 1200,  "unlock": "raditz", "grants": None},
            20: {"name": "NAPPA",  "hp": 5500,  "pl": 3800,  "unlock": "nappa",  "grants": "kaioken"},
            30: {"name": "VEGETA", "hp": 22000, "pl": 16000, "unlock": "vegeta", "grants": None},
        },
    },
    "NAMEK": {
        "minions": [
            {"name": "NAMEKIAN WARRIOR", "base_hp": 600, "hp_scale": 200, "base_pl": 5000, "pl_scale": 1.06},
            {"name": "FRIEZA SOLDIER",   "base_hp": 550, "hp_scale": 180, "base_pl": 4500, "pl_scale": 1.05},
        ],
        "bosses": {
            35: {"name": "DODORIA",      "hp": 25000,  "pl": 22000,  "unlock": "dodoria",  "grants": None},
            40: {"name": "ZARBON",       "hp": 35000,  "pl": 23000,  "unlock": "zarbon",   "grants": None},
            50: {"name": "GULDO",        "hp": 30000,  "pl": 11000,  "unlock": "guldo",    "grants": None},
            53: {"name": "RECOOME",      "hp": 80000,  "pl": 71000,  "unlock": "recoome",  "grants": None},
            55: {"name": "BURTER",       "hp": 65000,  "pl": 67000,  "unlock": "burter",   "grants": None},
            58: {"name": "JEICE",        "hp": 65000,  "pl": 67000,  "unlock": "jeice",    "grants": None},
            60: {"name": "GINYU",        "hp": 90000,  "pl": 120000, "unlock": "ginyu",    "grants": None},
            70: {"name": "FRIEZA FORM 1","hp": 220000, "pl": 180000, "unlock": None,       "grants": None},
        },
    },
    "FRIEZA": {
        "minions": [
            {"name": "ELITE SOLDIER", "base_hp": 800, "hp_scale": 200, "base_pl": 60000, "pl_scale": 1.04},
        ],
        "bosses": {
            80:  {"name": "FRIEZA FORM 2", "hp": 380000,  "pl": 500000,   "unlock": None,    "grants": None},
            90:  {"name": "FRIEZA FORM 3", "hp": 600000,  "pl": 900000,   "unlock": None,    "grants": None},
            95:  {"name": "FRIEZA 50%",    "hp": 900000,  "pl": 3000000,  "unlock": None,    "grants": "ssj_namek"},
            100: {"name": "FRIEZA 100%",   "hp": 1200000, "pl": 6000000,  "unlock": "frieza","grants": None},
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
    "senzu":          {"name": "Senzu Bean",         "desc": "Fully restores HP and clears all debuffs.",               "base_cost": 120},
    "gravity_x10":    {"name": "10x Gravity",        "desc": "+20% of your current Power Level. Costs 10% HP.",         "base_cost": 180},
    "gravity_x100":   {"name": "100x Gravity",       "desc": "+40% of your current Power Level. Large PL spike.",       "base_cost": 450},
    "scouter_v3":     {"name": "Prototype Scouter",  "desc": "+15% Crit chance.",                                       "base_cost": 350},
    "ki_overdrive":   {"name": "Ki Overdrive",       "desc": "Doubles Ki gain per action.",                             "base_cost": 250},
    "fruit_tree":     {"name": "Fruit of Might",     "desc": "+15% permanent damage output.",                           "base_cost": 500},
    "tail_regrow":    {"name": "Ancient Ointment",   "desc": "+8% Lifesteal on every hit.",                             "base_cost": 400},
    "alloy_plating":  {"name": "Katchin Armor",      "desc": "Reduces all incoming damage by 150 flat.",                "base_cost": 400},
    "adrenaline":     {"name": "Saiyan Pride",       "desc": "Damage rises the lower your HP falls.",                   "base_cost": 300},
    "prophetic_fish": {"name": "Oracle Snack",       "desc": "+12% Dodge chance.",                                      "base_cost": 600},
    "dende_blessing": {"name": "Grand Elder's Gift", "desc": "+2500 max HP permanently.",                               "base_cost": 750},
    "z_sword":        {"name": "Z-Sword Fragment",   "desc": "+20% Defense Penetration.",                               "base_cost": 550},
    "spirit_water":   {"name": "Ultra Divine Water", "desc": "Randomly boosts one stat significantly.",                  "base_cost": 400},
    "yardrat_manual": {"name": "Yardrat Secret",     "desc": "+20% Dodge and Ki Regen boost.",                          "base_cost": 500},
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
        # Transformation state
        self.active_transform = None
        self.transform_mult = 1.0
        self.transform_hp_drain = 0.0
        self.transform_ki_drain = 0.0
        self.transform_def_mult = 1.0
        self.kaioken_unlocked = (char_type == "goku_namek")
        self.ssj_unlocked = False
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

        # Check if current wave is a defined boss wave
        if self.wave in pool["bosses"]:
            boss = pool["bosses"][self.wave]
            return {
                "name":     boss["name"],
                "hp":       boss["hp"],
                "max_hp":   boss["hp"],
                "pl":       boss["pl"],
                "boss":     True,
                "modifier": None,
                "dodge":    0.0,
                "armor":    0,
                "dmg_mult": 1.0,
                "unlock":   boss.get("unlock"),
                "grants":   boss.get("grants"),
            }

        # Fallback elite encounter every 10 non-boss waves divisible by 10
        if self.wave % 10 == 0:
            base = 25000 + self.wave * 2000
            return {
                "name":     f"ELITE WARRIOR W{self.wave}",
                "hp":       base, "max_hp": base,
                "pl":       10000 + self.wave * 1000,
                "boss":     True, "modifier": None,
                "dodge": 0.0, "armor": 0, "dmg_mult": 1.0,
                "unlock": None, "grants": None,
            }

        template = random.choice(pool["minions"])
        mod_key = random.choice(_MODIFIER_POOL)
        mod = ENEMY_MODIFIERS[mod_key]
        hp = int((template["base_hp"] + self.wave * template["hp_scale"]) * mod["hp_mult"])
        pl = int((template["base_pl"] * (template["pl_scale"] ** (self.wave - 1))) * mod["pl_mult"])
        return {
            "name":     template["name"],
            "hp":       hp, "max_hp": hp, "pl": pl, "boss": False,
            "modifier": mod_key if mod_key != "NONE" else None,
            "dodge":    mod["dodge"], "armor": mod["armor"],
            "dmg_mult": mod["dmg_mult"], "unlock": None, "grants": None,
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

    def drop_transform(self):
        self.active_transform = None
        self.transform_mult = 1.0
        self.transform_hp_drain = 0.0
        self.transform_ki_drain = 0.0
        self.transform_def_mult = 1.0


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
    # Kaioken strains the body — player takes proportionally more damage while transformed
    e_dmg = int(e_base * dmg_mult * state.defense_mod * state.transform_def_mult) - state.flat_reduction
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
            "name":         cdata["name"],
            "base_pl":      cdata["base_pl"],
            "base_hp":      cdata["base_hp"],
            "unlocked":     char_id in unlocked,
            "sprite_ready": cdata["sprite_set"],
            "unlock_by":    cdata.get("unlock_by"),
            "category":     cdata["category"],
            "saga":         cdata.get("saga", "SAIYAN"),
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
    transforms = list(CHAR_TRANSFORMS.get(char, {}).keys())
    return jsonify({"player": vars(state), "enemy": state.enemy, "transforms": transforms})


@app.route("/battle-action", methods=["POST"])
def battle_action():
    state = current_state()
    data = request.get_json()
    skill = data.get("skill", "jab")

    state.ki = min(100, state.ki + state.ki_regen)

    # ── Transformation drain (applied each action) ──────────────────────────
    transform_msg = None
    if state.active_transform:
        if state.transform_hp_drain > 0:
            drain = max(1, int(state.max_hp * state.transform_hp_drain))
            state.hp = max(1, state.hp - drain)
            transform_msg = f"{state.active_transform.upper()} — {drain:,} HP drained"
            if state.hp <= 1:
                state.drop_transform()
                transform_msg += " · FORM DROPPED (HP critical)"
        elif state.transform_ki_drain > 0:
            state.ki = max(0, state.ki - state.transform_ki_drain)
            transform_msg = f"SUPER SAIYAN — {int(state.transform_ki_drain)} Ki burned"
            if state.ki <= 0:
                state.drop_transform()
                transform_msg += " · SUPER SAIYAN DROPPED (Ki exhausted)"

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
            "message":       "GUARDING — incoming damage reduced by 75%",
            "enemy_msg":     enemy_msg,
            "transform_msg": transform_msg,
            "player":        vars(state),
            "enemy":         state.enemy,
            "enemy_killed":  False,
            "game_over":     game_over,
            "zenkai":        False,
            "shop_items":    [],
            "pl_gained":     0,
            "capped":        False,
        })

    state.is_guarding = False
    ki_gain = int(move["ki_gain"] * state.ki_gain_mult)
    if ki_gain:
        state.ki = min(100, state.ki + ki_gain)

    # ── Damage calculation using effective (transformed) PL ─────────────────
    effective_pl = state.pl * state.transform_mult
    raw_dmg = move["base_dmg"] * (1 + effective_pl / 380)
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

    cap = move.get("hp_cap")
    hit_cap = False
    if cap and state.enemy["max_hp"] > 0:
        ceiling = int(state.enemy["max_hp"] * cap)
        if final_dmg > ceiling:
            final_dmg = ceiling
            hit_cap = True

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
    pl_gained = 0

    if enemy_killed:
        boss = state.enemy.get("boss")
        if boss and state.enemy.get("unlock"):
            save_unlock(state.enemy["unlock"])
        # Handle transformation grants from boss kills
        grant = state.enemy.get("grants")
        if grant == "kaioken" and state.char == "goku":
            state.kaioken_unlocked = True
        elif grant == "ssj_namek" and state.char == "goku_namek":
            state.ssj_unlocked = True
        state.zeni += 180 + state.wave * 15
        if boss:
            state.zeni += 600
        zenkai_triggered = state.apply_zenkai()
        pl_gained = int(state.enemy["pl"] * 0.12)
        state.pl += pl_gained
        state.generate_shop()
    else:
        enemy_msg, game_over = _enemy_attack(state)

    return jsonify({
        "message":       player_msg,
        "enemy_msg":     enemy_msg,
        "transform_msg": transform_msg,
        "player":        vars(state),
        "enemy":         state.enemy,
        "enemy_killed":  enemy_killed,
        "game_over":     game_over,
        "zenkai":        zenkai_triggered,
        "shop_items":    state.current_shop,
        "pl_gained":     pl_gained,
        "capped":        hit_cap,
    })


@app.route("/battle-status")
def battle_status():
    state = current_state()
    p = vars(state)
    p["saga"] = state.get_saga()
    return jsonify({"player": p})


@app.route("/transform", methods=["POST"])
def transform():
    state = current_state()
    mode = request.get_json().get("mode", "none")

    if mode == "none":
        state.drop_transform()
        return jsonify({"player": vars(state), "message": "TRANSFORMATION RELEASED"})

    char_table = CHAR_TRANSFORMS.get(state.char, {})
    t = char_table.get(mode)
    if not t:
        return jsonify({"error": "Transform not available for this character"}), 400

    req = t.get("req")
    if req == "kaioken" and not state.kaioken_unlocked:
        return jsonify({"error": "KAIOKEN NOT UNLOCKED — defeat NAPPA first"}), 403
    if req == "ssj" and not state.ssj_unlocked:
        return jsonify({"error": "SUPER SAIYAN LOCKED — defeat FRIEZA 50% to awaken"}), 403

    state.active_transform   = mode
    state.transform_mult     = t["mult"]
    state.transform_hp_drain = t["hp_drain"]
    state.transform_ki_drain = t["ki_drain"]
    state.transform_def_mult = t["def_pen"]

    drain_str = (f"{int(t['hp_drain']*100)}% HP/turn" if t["hp_drain"] > 0
                 else f"{int(t['ki_drain'])} Ki/turn")
    return jsonify({
        "player":  vars(state),
        "message": f"{t['label']} ACTIVATED · Drain: {drain_str}",
    })


@app.route("/purchase", methods=["POST"])
def purchase():
    state = current_state()
    item_id = request.get_json().get("item_id")
    item = next((i for i in state.current_shop if i["id"] == item_id), None)
    if not item or state.zeni < item["cost"]:
        return jsonify({"error": "Cannot purchase — insufficient Zeni or item unavailable"}), 400

    state.zeni -= item["cost"]
    s = 1 + state.wave * 0.08
    detail = ""

    if item_id == "senzu":
        state.hp = state.max_hp
        state.status_effects = []
        detail = "HP fully restored"
    elif item_id == "gravity_x10":
        gain = int(state.pl * 0.20)
        state.pl += gain
        state.hp = max(1, int(state.hp * 0.9))
        detail = f"PL +{gain:,} (20% of current · HP cost -10%)"
    elif item_id == "gravity_x100":
        gain = int(state.pl * 0.40)
        state.pl += gain
        detail = f"PL +{gain:,} (40% of current)"
    elif item_id == "dende_blessing":
        state.base_max_hp += 2500
        detail = "Max HP +2,500"
    elif item_id == "z_sword":
        state.def_pen += 0.20
        detail = "Defense Penetration +20%"
    elif item_id == "prophetic_fish":
        state.dodge_chance = min(0.45, state.dodge_chance + 0.12)
        detail = f"Dodge → {round(state.dodge_chance * 100)}%"
    elif item_id == "scouter_v3":
        state.crit_chance = min(0.5, state.crit_chance + 0.15)
        detail = f"Crit Chance → {round(state.crit_chance * 100)}%"
    elif item_id == "fruit_tree":
        state.outgoing_damage_mult *= 1.15
        detail = f"Damage Output → x{state.outgoing_damage_mult:.2f}"
    elif item_id == "ki_overdrive":
        state.ki_gain_mult = 2.0
        detail = "Ki Gain x2 active"
    elif item_id == "tail_regrow":
        state.lifesteal = min(0.5, state.lifesteal + 0.08)
        detail = f"Lifesteal → {round(state.lifesteal * 100)}%"
    elif item_id == "alloy_plating":
        state.flat_reduction += 150
        detail = f"Flat Damage Reduction → {state.flat_reduction}"
    elif item_id == "adrenaline":
        state.adrenaline_scale = max(state.adrenaline_scale, 0.5)
        detail = "Low-HP damage scaling active"
    elif item_id == "yardrat_manual":
        state.dodge_chance = min(0.45, state.dodge_chance + 0.12)
        state.ki_regen = min(20, state.ki_regen + 3)
        detail = f"Dodge → {round(state.dodge_chance * 100)}%  ·  Ki Regen → +{state.ki_regen}/turn"
    elif item_id == "spirit_water":
        roll = random.choice(["pl", "pl2", "hp", "crit", "dodge", "def_pen"])
        if roll == "pl":
            gain = int(state.pl * 0.20)
            state.pl += gain
            detail = f"LUCKY — Power Level +{gain:,} (20% of current)"
        elif roll == "pl2":
            gain = int(state.pl * 0.12)
            state.pl += gain
            detail = f"Power Level +{gain:,} (12% of current)"
        elif roll == "hp":
            gain = int(state.base_max_hp * 0.18)
            state.base_max_hp += gain
            detail = f"Max HP +{gain:,} (18% of current)"
        elif roll == "crit":
            state.crit_chance = min(0.5, state.crit_chance + 0.1)
            detail = f"Crit Chance → {round(state.crit_chance * 100)}%"
        elif roll == "dodge":
            state.dodge_chance = min(0.45, state.dodge_chance + 0.1)
            detail = f"Dodge → {round(state.dodge_chance * 100)}%"
        else:
            state.def_pen += 0.12
            detail = "Defense Penetration +12%"

    state.update_stats()
    return jsonify({"player": vars(state), "detail": detail})


@app.route("/refresh-shop", methods=["POST"])
def refresh_shop():
    state = current_state()
    reroll_cost = 300 + state.wave * 25
    if state.zeni < reroll_cost:
        return jsonify({"error": f"Need {reroll_cost:,} Z to reroll the shop"}), 400
    state.zeni -= reroll_cost
    state.generate_shop()
    return jsonify({"shop_items": state.current_shop, "player": vars(state)})


@app.route("/next-enemy", methods=["POST"])
def next_enemy():
    state = current_state()
    state.wave += 1
    state.is_guarding = False
    state.drop_transform()
    state.enemy = state.spawn_enemy()
    transforms = list(CHAR_TRANSFORMS.get(state.char, {}).keys())
    return jsonify({"enemy": state.enemy, "player": vars(state), "transforms": transforms})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
