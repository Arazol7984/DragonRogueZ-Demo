import sqlite3
import json
import random
import os
from flask import Flask, render_template, jsonify, request, make_response

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dragon_rogue_z_2026_build")

_states = {}   # ip -> GameState (one live run per IP)


# ─────────────────────────────────────────────────────────────────────────────
#  IP HELPER
# ─────────────────────────────────────────────────────────────────────────────

def get_client_ip():
    """Return client IP, honouring common proxy headers."""
    xff = request.headers.get("X-Forwarded-For", "")
    return xff.split(",")[0].strip() if xff else (request.remote_addr or "127.0.0.1")


# ─────────────────────────────────────────────────────────────────────────────
#  DATABASE  (per-IP save records)
# ─────────────────────────────────────────────────────────────────────────────

def init_db():
    conn = sqlite3.connect("save_data.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS player_saves (
            ip           TEXT PRIMARY KEY,
            unlocked_chars TEXT NOT NULL DEFAULT '["goku","goku_namek"]',
            zenkai_level   INTEGER NOT NULL DEFAULT 0,
            best_wave      INTEGER NOT NULL DEFAULT 0,
            total_runs     INTEGER NOT NULL DEFAULT 0
        )
    """)
    # One-time migration of old single-row table if it exists
    try:
        c.execute("SELECT unlocked_chars, zenkai_level FROM progress WHERE id=1")
        row = c.fetchone()
        if row:
            c.execute("""
                INSERT OR IGNORE INTO player_saves (ip, unlocked_chars, zenkai_level)
                VALUES ('migrated_v1', ?, ?)
            """, (row[0], row[1]))
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()


def get_save_data(ip):
    try:
        conn = sqlite3.connect("save_data.db")
        c = conn.cursor()
        c.execute("SELECT unlocked_chars, zenkai_level, best_wave, total_runs "
                  "FROM player_saves WHERE ip=?", (ip,))
        row = c.fetchone()
        conn.close()
        if row:
            return json.loads(row[0]), row[1], row[2], row[3]
    except (sqlite3.Error, json.JSONDecodeError, TypeError):
        pass
    return (["goku", "goku_namek"], 0, 0, 0)


def _upsert_player(ip, chars, zenkai, wave, runs_delta=0):
    conn = sqlite3.connect("save_data.db")
    c = conn.cursor()
    c.execute("""
        INSERT INTO player_saves (ip, unlocked_chars, zenkai_level, best_wave, total_runs)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(ip) DO UPDATE SET
            unlocked_chars = excluded.unlocked_chars,
            zenkai_level   = excluded.zenkai_level,
            best_wave      = MAX(best_wave, excluded.best_wave),
            total_runs     = total_runs + ?
    """, (ip, json.dumps(chars), zenkai, wave, runs_delta, runs_delta))
    conn.commit()
    conn.close()


def save_unlock(ip, char_id):
    if not char_id:
        return
    chars, zenkai, best, runs = get_save_data(ip)
    if char_id not in chars:
        chars.append(char_id)
    _upsert_player(ip, chars, zenkai, best)


def save_run_end(ip, zenkai, wave):
    chars, _, old_best, old_runs = get_save_data(ip)
    _upsert_player(ip, chars, zenkai, wave, runs_delta=1)
    new_best = max(old_best, wave)
    return old_best, new_best, old_runs + 1


# ─────────────────────────────────────────────────────────────────────────────
#  GAME DATA
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

CHAR_ROSTER = {
    "goku":       {"name": "GOKU · SAIYAN", "base_pl": 416,     "base_hp": 800,   "sprite_set": True,  "unlock_by": None,          "category": "Z-WARRIORS", "saga": "SAIYAN"},
    "tien":       {"name": "TIEN",          "base_pl": 180,     "base_hp": 700,   "sprite_set": False, "unlock_by": None,          "category": "Z-WARRIORS", "saga": "SAIYAN"},
    "yamcha":     {"name": "YAMCHA",        "base_pl": 120,     "base_hp": 650,   "sprite_set": False, "unlock_by": None,          "category": "Z-WARRIORS", "saga": "SAIYAN"},
    "piccolo":    {"name": "PICCOLO",       "base_pl": 320,     "base_hp": 750,   "sprite_set": False, "unlock_by": None,          "category": "Z-WARRIORS", "saga": "SAIYAN"},
    "krillin":    {"name": "KRILLIN",       "base_pl": 210,     "base_hp": 700,   "sprite_set": False, "unlock_by": None,          "category": "Z-WARRIORS", "saga": "SAIYAN"},
    "chiaotzu":   {"name": "CHIAOTZU",      "base_pl": 90,      "base_hp": 500,   "sprite_set": False, "unlock_by": None,          "category": "Z-WARRIORS", "saga": "SAIYAN"},
    "raditz":     {"name": "RADITZ",        "base_pl": 1200,    "base_hp": 1500,  "sprite_set": True,  "unlock_by": "RADITZ",      "category": "RIVALS",     "saga": "SAIYAN"},
    "nappa":      {"name": "NAPPA",         "base_pl": 4000,    "base_hp": 3500,  "sprite_set": True,  "unlock_by": "NAPPA",       "category": "RIVALS",     "saga": "SAIYAN"},
    "vegeta":     {"name": "VEGETA",        "base_pl": 18000,   "base_hp": 5000,  "sprite_set": True,  "unlock_by": "VEGETA",      "category": "RIVALS",     "saga": "SAIYAN"},
    "goku_namek": {"name": "GOKU · NAMEK",  "base_pl": 5000,    "base_hp": 1200,  "sprite_set": True,  "unlock_by": None,          "category": "Z-WARRIORS", "saga": "NAMEK"},
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
    "NONE":      {"hp_mult": 1.0, "pl_mult": 1.0, "dodge": 0.0,  "dmg_mult": 1.0,  "armor": 0},
    "ALPHA":     {"hp_mult": 1.3, "pl_mult": 1.3, "dodge": 0.0,  "dmg_mult": 1.0,  "armor": 0},
    "SWIFT":     {"hp_mult": 1.0, "pl_mult": 1.0, "dodge": 0.25, "dmg_mult": 1.0,  "armor": 0},
    "ARMORED":   {"hp_mult": 1.2, "pl_mult": 1.0, "dodge": 0.0,  "dmg_mult": 0.9,  "armor": 150},
    "BERSERKER": {"hp_mult": 1.0, "pl_mult": 1.2, "dodge": 0.0,  "dmg_mult": 1.4,  "armor": 0},
    "FRENZIED":  {"hp_mult": 1.0, "pl_mult": 1.5, "dodge": 0.05, "dmg_mult": 1.35, "armor": 0},
}

# Modifier → (curse_id, application_chance)
MODIFIER_CURSE = {
    "BERSERKER": ("WEAKENED",     0.35),
    "ARMORED":   ("SUPPRESSED",   0.25),
    "SWIFT":     ("RATTLED",      0.30),
    "ALPHA":     ("BLEEDING",     0.20),
    "FRENZIED":  ("DEMORALIZED",  0.40),
}

CURSES = {
    "SUPPRESSED":  {"label": "KI SUPPRESSED", "desc": "Ki Regen halved.",              "duration": 3, "color": "blue"},
    "WEAKENED":    {"label": "WEAKENED",      "desc": "Outgoing damage -20%.",          "duration": 3, "color": "dim"},
    "BLEEDING":    {"label": "BLEEDING",      "desc": "Lose 3% max HP each action.",    "duration": 4, "color": "red"},
    "RATTLED":     {"label": "RATTLED",       "desc": "Crit Chance reduced to 0%.",     "duration": 2, "color": "gold"},
    "DEMORALIZED": {"label": "DEMORALIZED",   "desc": "Damage output -25% for 3 turns.","duration": 3, "color": "dim"},
}

def _get_modifier_pool(wave):
    """Wave-scaled enemy modifier pool — later waves feature more dangerous variants."""
    if wave >= 50:
        return (["NONE"]*10 + ["ALPHA"]*20 + ["SWIFT"]*15 +
                ["ARMORED"]*15 + ["BERSERKER"]*15 + ["FRENZIED"]*25)
    elif wave >= 25:
        return (["NONE"]*25 + ["ALPHA"]*20 + ["SWIFT"]*15 +
                ["ARMORED"]*15 + ["BERSERKER"]*15 + ["FRENZIED"]*10)
    else:
        return (["NONE"]*40 + ["ALPHA"]*20 + ["SWIFT"]*15 +
                ["ARMORED"]*15 + ["BERSERKER"]*10)

ALL_SHOP_ITEMS = {
    # ── Core items ──────────────────────────────────────────────────────────
    "senzu":          {"name": "Senzu Bean",          "desc": "Fully restores HP and clears all debuffs.",              "base_cost": 120},
    "gravity_x10":    {"name": "10x Gravity",         "desc": "+20% of your current PL. Costs 10% HP.",                "base_cost": 180},
    "gravity_x100":   {"name": "100x Gravity",        "desc": "+40% of your current PL. Large spike.",                  "base_cost": 450},
    "scouter_v3":     {"name": "Prototype Scouter",   "desc": "+15% Crit Chance.",                                      "base_cost": 350},
    "ki_overdrive":   {"name": "Ki Overdrive",        "desc": "Doubles Ki gain per action.",                            "base_cost": 250},
    "fruit_tree":     {"name": "Fruit of Might",      "desc": "+15% permanent damage output.",                          "base_cost": 500},
    "tail_regrow":    {"name": "Ancient Ointment",    "desc": "+8% Lifesteal on every hit.",                            "base_cost": 400},
    "alloy_plating":  {"name": "Katchin Armor",       "desc": "Reduces incoming damage by 150 flat.",                   "base_cost": 400},
    "adrenaline":     {"name": "Saiyan Pride",        "desc": "Damage rises the lower your HP falls.",                  "base_cost": 300},
    "prophetic_fish": {"name": "Oracle Snack",        "desc": "+12% Dodge Chance.",                                     "base_cost": 600},
    "dende_blessing": {"name": "Grand Elder's Gift",  "desc": "+2500 Max HP permanently.",                              "base_cost": 750},
    "z_sword":        {"name": "Z-Sword Fragment",    "desc": "+20% Defense Penetration.",                              "base_cost": 550},
    "spirit_water":   {"name": "Ultra Divine Water",  "desc": "Randomly boosts one stat significantly.",                "base_cost": 400},
    "yardrat_manual": {"name": "Yardrat Secret",      "desc": "+20% Dodge and Ki Regen boost.",                         "base_cost": 500},
    # ── Roguelite items (trade-offs) ─────────────────────────────────────────
    "heart_cure":          {"name": "Curse Antidote",          "desc": "Remove ALL active curses and restore 25% HP.",              "base_cost": 300},
    "master_seal":         {"name": "Roshi's Power Seal",      "desc": "+3 Ki Regen and +10% Crit Chance.",                         "base_cost": 420},
    "android_core":        {"name": "Android Power Core",      "desc": "Immune to curses permanently. Ki Regen -3/turn.",            "base_cost": 650},
    "baba_shop":           {"name": "Baba's Mystery Box",      "desc": "Gamble: random rare reward. High risk, high reward.",        "base_cost": 200},
    "weighted_gi":         {"name": "Weighted Training Gi",    "desc": "Ki Regen halved. Kill PL gain doubled for the run.",         "base_cost": 0, "base_cost_calc": True},
    "vitality_surge":      {"name": "Vitality Surge",          "desc": "Restore 40% HP now. Max HP -800 permanently.",              "base_cost": 50},
    # ── New roguelite items ───────────────────────────────────────────────────
    "senzu_fragment":      {"name": "Senzu Fragment",          "desc": "Restore 45% HP and remove 1 curse. Cheap triage.",          "base_cost": 75},
    "hyperbolic_chamber":  {"name": "Hyperbolic Time Chamber", "desc": "Pay 25% current HP now. PL +55% of current. High risk.",    "base_cost": 600},
    "elder_kai_seal":      {"name": "Elder Kai's Awakening",   "desc": "+8% permanent boost to PL, Max HP, and +1 Ki Regen.",       "base_cost": 700},
    "geti_star":           {"name": "Geti Star Crystal",       "desc": "Each kill restores 5% max HP. Stacks up to 25%.",           "base_cost": 500},
    "recovery_module":     {"name": "Katchin Recovery Module", "desc": "Regenerate 2% max HP each turn passively. Stacks.",         "base_cost": 550},
}

ENCOUNTER_POOL = [
    {"id": "roshi",      "title": "MASTER ROSHI ENCOUNTER",   "desc": "Pay 20% of current HP to gain 30% Power Level instantly.",                            "btn": "TRAIN (PAY 20% HP)",  "effect": "roshi_train"},
    {"id": "baba",       "title": "FORTUNETELLER BABA",       "desc": "Gamble 40% of your Zeni. 55% chance to double it, 45% chance to lose it.",           "btn": "PLACE YOUR BET",      "effect": "baba_wager"},
    {"id": "yardrat",    "title": "YARDRAT BODY TECHNIQUE",   "desc": "Lose 500 Max HP permanently. Gain +22% Dodge Chance.",                               "btn": "LEARN TECHNIQUE",     "effect": "yardrat_deal"},
    {"id": "weighted",   "title": "KING KAI'S CHALLENGE",     "desc": "Ki Regen halved for the rest of the run. Kill PL gain doubled.",                     "btn": "ACCEPT CHALLENGE",    "effect": "weighted_training"},
    {"id": "korin",      "title": "KORIN'S SENZU GIFT",       "desc": "Pay 400 Zeni for an immediate 50% HP restore.",                                      "btn": "PAY 400 Z",           "effect": "korin_heal"},
    {"id": "oracle",     "title": "ORACLE'S REVELATION",      "desc": "Free intel: learn the exact wave and power of the next boss.",                        "btn": "VIEW INTEL",          "effect": "reveal_next"},
    {"id": "hyperbolic", "title": "HYPERBOLIC TIME CHAMBER",  "desc": "A full year of training compressed. Lose 30% current HP. Gain 65% PL instantly.",    "btn": "ENTER CHAMBER",       "effect": "hyperbolic_train"},
    {"id": "bubbles",    "title": "KING KAI'S PLANET",        "desc": "Train with Bubbles the monkey. Pay 300 Zeni. Permanently gain +6% Dodge Chance.",    "btn": "TRAIN WITH BUBBLES",  "effect": "bubbles_train"},
]


# ─────────────────────────────────────────────────────────────────────────────
#  GAME STATE
# ─────────────────────────────────────────────────────────────────────────────

class GameState:
    def __init__(self, ip="127.0.0.1"):
        self.ip = ip
        self.reset()

    def reset(self, char_type="goku"):
        cdata = CHAR_ROSTER.get(char_type, CHAR_ROSTER["goku"])
        chars, zenkai, _, _ = get_save_data(self.ip)
        zm = 1 + zenkai * 0.1
        self.zenkai_level   = zenkai
        self.char           = char_type
        self.wave           = 1
        self.pl             = int(cdata["base_pl"] * zm)
        self.base_max_hp    = cdata["base_hp"]
        self.update_stats()
        self.hp             = self.max_hp
        self.ki             = 100
        self.ki_regen       = 8
        self.ki_gain_mult   = 1.0
        self.crit_chance    = 0.05
        self.dodge_chance   = 0.03
        self.def_pen        = 0.0
        self.lifesteal      = 0.0
        self.flat_reduction = 0
        self.defense_mod    = 1.0
        self.outgoing_damage_mult = 1.0
        self.adrenaline_scale     = 0.0
        self.is_guarding    = False
        self.status_effects = []
        self.zeni           = 850
        self.current_shop   = []
        # Transformation
        self.active_transform    = None
        self.transform_mult      = 1.0
        self.transform_hp_drain  = 0.0
        self.transform_ki_drain  = 0.0
        self.transform_def_mult  = 1.0
        self.kaioken_unlocked    = (char_type == "goku_namek")
        self.ssj_unlocked        = False
        # Roguelite systems
        self.curse_list          = []     # [{id, label, waves, color}]
        self.curse_immune        = False
        self.pl_kill_mult        = 1.0   # multiplier on kill PL gain
        self.pending_encounter   = None  # encounter offer dict or None
        self.next_boss_preview   = None  # {wave, name, pl, waves_away} or None
        self.run_stats           = {"kills": 0, "dmg_dealt": 0, "dmg_taken": 0, "items": 0}
        # Streak & passives
        self.kill_streak         = 0     # consecutive kills without being hit
        self.hp_on_kill          = 0.0   # fraction of max HP restored on each kill
        self.hp_regen            = 0.0   # fraction of max HP regenerated each turn
        self.enemy               = self.spawn_enemy()

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
        if self.wave % 10 == 0:
            base = 25000 + self.wave * 2000
            return {
                "name": f"ELITE WARRIOR W{self.wave}",
                "hp": base, "max_hp": base,
                "pl": 10000 + self.wave * 1000,
                "boss": True, "modifier": None,
                "dodge": 0.0, "armor": 0, "dmg_mult": 1.0,
                "unlock": None, "grants": None,
            }
        template = random.choice(pool["minions"])
        mod_key  = random.choice(_get_modifier_pool(self.wave))
        mod      = ENEMY_MODIFIERS[mod_key]
        hp = int((template["base_hp"] + self.wave * template["hp_scale"]) * mod["hp_mult"])
        pl = int((template["base_pl"] * (template["pl_scale"] ** (self.wave - 1))) * mod["pl_mult"])
        return {
            "name":     template["name"],
            "hp": hp, "max_hp": hp, "pl": pl, "boss": False,
            "modifier": mod_key if mod_key != "NONE" else None,
            "dodge":    mod["dodge"],
            "armor":    mod["armor"],
            "dmg_mult": mod["dmg_mult"],
            "unlock": None, "grants": None,
        }

    def _find_next_boss(self):
        """Look ahead up to 8 waves for an approaching boss."""
        saga_name = self.get_saga()
        pool = ENEMY_POOLS.get(saga_name, ENEMY_POOLS["SAIYAN"])
        for ahead in range(1, 9):
            wv = self.wave + ahead
            if wv in pool.get("bosses", {}):
                b = pool["bosses"][wv]
                return {"wave": wv, "name": b["name"], "pl": b["pl"], "waves_away": ahead}
        return None

    def generate_shop(self):
        all_keys = [k for k in ALL_SHOP_ITEMS if not ALL_SHOP_ITEMS[k].get("base_cost_calc")]
        # Pity Senzu: if HP < 20%, guarantee it
        if self.hp < self.max_hp * 0.20 and "senzu" not in [i["id"] for i in self.current_shop]:
            pool_keys = random.sample([k for k in all_keys if k != "senzu"],
                                      min(5, len(all_keys) - 1))
            pool_keys.insert(0, "senzu")
        else:
            pool_keys = random.sample(all_keys, min(6, len(all_keys)))

        scale = 1 + self.wave * 0.07
        self.current_shop = []
        for k in pool_keys:
            item = ALL_SHOP_ITEMS[k].copy()
            item["id"] = k
            item["cost"] = int(item["base_cost"] * scale)
            self.current_shop.append(item)

        # Dynamic-cost items (weighted_gi)
        if "weighted_gi" in ALL_SHOP_ITEMS:
            self.current_shop.append({
                **ALL_SHOP_ITEMS["weighted_gi"],
                "id": "weighted_gi",
                "cost": int(50 + self.wave * 10),
            })

        # 28% chance of a random encounter offer
        self.pending_encounter = random.choice(ENCOUNTER_POOL).copy() if random.random() < 0.28 else None
        # Boss preview
        self.next_boss_preview = self._find_next_boss()

    def apply_zenkai(self):
        if self.hp < self.max_hp * 0.15:
            self.zenkai_level += 1
            conn = sqlite3.connect("save_data.db")
            c = conn.cursor()
            c.execute("""
                INSERT INTO player_saves (ip, unlocked_chars, zenkai_level, best_wave, total_runs)
                VALUES (?, '["goku","goku_namek"]', ?, 0, 0)
                ON CONFLICT(ip) DO UPDATE SET zenkai_level = excluded.zenkai_level
            """, (self.ip, self.zenkai_level))
            conn.commit()
            conn.close()
            return True
        return False

    def drop_transform(self):
        self.active_transform   = None
        self.transform_mult     = 1.0
        self.transform_hp_drain = 0.0
        self.transform_ki_drain = 0.0
        self.transform_def_mult = 1.0

    def _curse_active(self, cid):
        return any(c["id"] == cid for c in self.curse_list)


def current_state():
    ip = get_client_ip()
    if ip not in _states:
        _states[ip] = GameState(ip)
    return _states[ip]


init_db()


# ─────────────────────────────────────────────────────────────────────────────
#  COMBAT HELPER
# ─────────────────────────────────────────────────────────────────────────────

def _enemy_attack(state):
    """Returns (msg, game_over, curse_applied, special_move_name)."""
    if random.random() < state.dodge_chance:
        state.kill_streak += 1  # evaded — streak continues
        return f"{state.enemy['name']} missed!", False, None, None

    is_boss = state.enemy.get("boss", False)
    e_base  = state.enemy["pl"] * 0.07
    if is_boss:
        e_base *= 1.25

    # Boss signature move (22% chance for 1.5× base damage)
    special_move = None
    if is_boss and random.random() < 0.22:
        e_base      *= 1.5
        boss_short   = state.enemy["name"].split()[0]
        special_move = f"{boss_short}'s SIGNATURE MOVE"

    dmg_mult = state.enemy.get("dmg_mult", 1.0)
    e_dmg = int(e_base * dmg_mult * state.defense_mod * state.transform_def_mult) - state.flat_reduction
    if state.is_guarding:
        e_dmg = int(e_dmg * 0.25)
    e_dmg = max(20, e_dmg)
    state.hp = max(0, state.hp - e_dmg)
    state.run_stats["dmg_taken"] = state.run_stats.get("dmg_taken", 0) + e_dmg
    state.kill_streak = 0  # being hit breaks the streak

    # Curse application from enemy modifier
    curse_applied = None
    if not state.curse_immune:
        mod = state.enemy.get("modifier")
        if mod and mod in MODIFIER_CURSE:
            cid, chance = MODIFIER_CURSE[mod]
            if random.random() < chance and not state._curse_active(cid):
                cd = CURSES[cid]
                state.curse_list.append({
                    "id": cid, "label": cd["label"],
                    "waves": cd["duration"], "color": cd["color"],
                })
                curse_applied = cd["label"]

    if special_move:
        msg = f"⚡ {special_move} — {e_dmg:,} damage!"
    else:
        msg = f"{state.enemy['name']} counter-attacks for {e_dmg:,}!"
    return msg, state.hp <= 0, curse_applied, special_move


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
    ip = get_client_ip()
    unlocked, zenkai, best_wave, total_runs = get_save_data(ip)
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
    return jsonify({
        "roster":     roster,
        "zenkai":     zenkai,
        "best_wave":  best_wave,
        "total_runs": total_runs,
    })


@app.route("/select-char", methods=["POST"])
def select_char():
    data = request.get_json()
    char = data.get("character", "goku")
    if char not in CHAR_ROSTER:
        return jsonify({"error": "Unknown character"}), 400
    ip = get_client_ip()
    unlocked, _, _, _ = get_save_data(ip)
    if char not in unlocked:
        return jsonify({"error": "Character not unlocked"}), 403
    state = current_state()
    state.reset(char)
    transforms = list(CHAR_TRANSFORMS.get(char, {}).keys())
    return jsonify({"player": vars(state), "enemy": state.enemy, "transforms": transforms})


@app.route("/battle-action", methods=["POST"])
def battle_action():
    state = current_state()
    data  = request.get_json()
    skill = data.get("skill", "jab")

    # ── Passive HP regen (before everything else) ────────────────────────────
    if state.hp_regen > 0:
        regen_amt = max(1, int(state.max_hp * state.hp_regen))
        state.hp  = min(state.max_hp, state.hp + regen_amt)

    # ── Curse tick ───────────────────────────────────────────────────────────
    curse_tick_msgs = []
    next_curses = []
    for curse in state.curse_list:
        if curse["id"] == "BLEEDING":
            bleed = max(1, int(state.max_hp * 0.03))
            state.hp = max(1, state.hp - bleed)
            curse_tick_msgs.append(f"BLEEDING — {bleed:,} HP drained")
        curse["waves"] -= 1
        if curse["waves"] > 0:
            next_curses.append(curse)
        else:
            curse_tick_msgs.append(f"{curse['label']} EXPIRED")
    state.curse_list = next_curses

    # ── Curse-modified effective stats ────────────────────────────────────────
    eff_ki_regen = state.ki_regen // 2 if state._curse_active("SUPPRESSED") else state.ki_regen
    state.ki = min(100, state.ki + eff_ki_regen)
    # ── Transformation drain ──────────────────────────────────────────────────
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
    if state.ki < move["ki_cost"]:
        return jsonify({"error": f"Insufficient Ki — need {move['ki_cost']}, have {int(state.ki)}"}), 400
    state.ki -= move["ki_cost"]

    if skill == "guard":
        state.is_guarding = True
        state.ki = min(100, state.ki + int(move["ki_gain"] * state.ki_gain_mult))
        enemy_msg, game_over, curse_applied, special_move = _enemy_attack(state)
        return jsonify({
            "message":       "GUARDING — incoming damage reduced 75%",
            "enemy_msg":     enemy_msg,
            "transform_msg": transform_msg,
            "curse_tick":    curse_tick_msgs,
            "curse_applied": curse_applied,
            "special_move":  special_move,
            "player":        vars(state),
            "enemy":         state.enemy,
            "enemy_killed":  False,
            "game_over":     game_over,
            "zenkai":        False,
            "shop_items":    [],
            "encounter":     None,
            "boss_preview":  None,
            "pl_gained":     0,
            "capped":        False,
            "streak_msg":    None,
            "kill_streak":   state.kill_streak,
        })

    state.is_guarding = False
    ki_gain = int(move["ki_gain"] * state.ki_gain_mult)
    if ki_gain:
        state.ki = min(100, state.ki + ki_gain)

    # ── Damage calculation ────────────────────────────────────────────────────
    effective_pl    = state.pl * state.transform_mult
    eff_outgoing    = state.outgoing_damage_mult
    if state._curse_active("WEAKENED"):     eff_outgoing *= 0.80
    if state._curse_active("DEMORALIZED"):  eff_outgoing *= 0.75
    eff_crit        = 0.0 if state._curse_active("RATTLED") else state.crit_chance

    # Kill streak damage bonus: +5% per 3 consecutive kills without being hit (max +15%)
    streak_bonus = min(0.15, (state.kill_streak // 3) * 0.05)

    raw_dmg = move["base_dmg"] * (1 + effective_pl / 380)
    if state.adrenaline_scale > 0 and state.max_hp > 0:
        raw_dmg *= 1 + state.adrenaline_scale * (1 - state.hp / state.max_hp)
    raw_dmg *= eff_outgoing * (1 + streak_bonus)
    final_dmg = int(raw_dmg * (1 + state.def_pen))

    is_crit = random.random() < eff_crit
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
    state.run_stats["dmg_dealt"] = state.run_stats.get("dmg_dealt", 0) + final_dmg

    if final_dmg > 0 and state.lifesteal > 0:
        state.hp = min(state.max_hp, state.hp + int(final_dmg * state.lifesteal))

    if dodged:
        player_msg = f"{state.enemy['name']} evaded your attack!"
    elif is_crit:
        player_msg = f"CRITICAL HIT! {final_dmg:,} damage!"
    else:
        player_msg = f"{final_dmg:,} damage dealt!"

    enemy_killed = state.enemy["hp"] <= 0
    enemy_msg, game_over, curse_applied, special_move = "", False, None, None
    zenkai_triggered = False
    pl_gained = 0
    streak_msg = None

    if enemy_killed:
        old_streak = state.kill_streak
        state.kill_streak += 1
        state.run_stats["kills"] = state.run_stats.get("kills", 0) + 1

        # Kill streak milestone messages
        for milestone in [3, 6, 9, 12]:
            if old_streak < milestone <= state.kill_streak:
                pct = min(15, (state.kill_streak // 3) * 5)
                streak_msg = f"FLAWLESS STREAK ×{state.kill_streak} — +{pct}% damage bonus active!"
                break

        # Bonus Zeni for consecutive kills
        streak_zeni = 0
        if state.kill_streak >= 12:
            streak_zeni = 350
        elif state.kill_streak >= 6:
            streak_zeni = 200
        elif state.kill_streak >= 3:
            streak_zeni = 100

        if state.enemy.get("boss") and state.enemy.get("unlock"):
            save_unlock(state.ip, state.enemy["unlock"])
        grant = state.enemy.get("grants")
        if grant == "kaioken" and state.char == "goku":
            state.kaioken_unlocked = True
        elif grant == "ssj_namek" and state.char == "goku_namek":
            state.ssj_unlocked = True

        # Adjusted Zeni economy (+~30% more than before)
        state.zeni += 220 + state.wave * 20 + streak_zeni
        if state.enemy.get("boss"):
            state.zeni += 800

        zenkai_triggered = state.apply_zenkai()
        # Kill PL gain reduced: 0.12 → 0.07 to keep early progression tighter
        pl_gained = int(state.enemy["pl"] * 0.07 * state.pl_kill_mult)
        state.pl += pl_gained

        # HP on kill passive
        if state.hp_on_kill > 0:
            on_kill_heal = max(1, int(state.max_hp * state.hp_on_kill))
            state.hp = min(state.max_hp, state.hp + on_kill_heal)

        state.generate_shop()
    else:
        enemy_msg, game_over, curse_applied, special_move = _enemy_attack(state)

    return jsonify({
        "message":       player_msg,
        "enemy_msg":     enemy_msg,
        "transform_msg": transform_msg,
        "curse_tick":    curse_tick_msgs,
        "curse_applied": curse_applied,
        "special_move":  special_move,
        "player":        vars(state),
        "enemy":         state.enemy,
        "enemy_killed":  enemy_killed,
        "game_over":     game_over,
        "zenkai":        zenkai_triggered,
        "shop_items":    state.current_shop,
        "encounter":     state.pending_encounter,
        "boss_preview":  state.next_boss_preview,
        "pl_gained":     pl_gained,
        "capped":        hit_cap,
        "streak_msg":    streak_msg,
        "kill_streak":   state.kill_streak,
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
    return jsonify({"player": vars(state), "message": f"{t['label']} ACTIVATED · Drain: {drain_str}"})


@app.route("/purchase", methods=["POST"])
def purchase():
    state  = current_state()
    item_id = request.get_json().get("item_id")
    item   = next((i for i in state.current_shop if i["id"] == item_id), None)
    if not item or state.zeni < item["cost"]:
        return jsonify({"error": "Cannot purchase — insufficient Zeni or item unavailable"}), 400
    state.zeni -= item["cost"]
    state.run_stats["items"] = state.run_stats.get("items", 0) + 1
    detail = ""

    if item_id == "senzu":
        state.hp = state.max_hp
        state.status_effects = []
        state.curse_list = []
        detail = "HP fully restored · Curses cleared"
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
        detail = f"Defense Penetration → {round(state.def_pen*100)}%"
    elif item_id == "prophetic_fish":
        state.dodge_chance = min(0.45, state.dodge_chance + 0.12)
        detail = f"Dodge → {round(state.dodge_chance*100)}%"
    elif item_id == "scouter_v3":
        state.crit_chance = min(0.5, state.crit_chance + 0.15)
        detail = f"Crit → {round(state.crit_chance*100)}%"
    elif item_id == "fruit_tree":
        state.outgoing_damage_mult *= 1.15
        detail = f"Damage Mult → ×{state.outgoing_damage_mult:.2f}"
    elif item_id == "ki_overdrive":
        state.ki_gain_mult = 2.0
        detail = "Ki Gain x2 active"
    elif item_id == "tail_regrow":
        state.lifesteal = min(0.5, state.lifesteal + 0.08)
        detail = f"Lifesteal → {round(state.lifesteal*100)}%"
    elif item_id == "alloy_plating":
        state.flat_reduction += 150
        detail = f"Flat Reduction → {state.flat_reduction}"
    elif item_id == "adrenaline":
        state.adrenaline_scale = max(state.adrenaline_scale, 0.5)
        detail = "Low-HP damage scaling active"
    elif item_id == "yardrat_manual":
        state.dodge_chance = min(0.45, state.dodge_chance + 0.12)
        state.ki_regen = min(20, state.ki_regen + 3)
        detail = f"Dodge → {round(state.dodge_chance*100)}% · Ki Regen +3"
    elif item_id == "spirit_water":
        roll = random.choice(["pl", "pl2", "hp", "crit", "dodge", "def_pen"])
        if roll == "pl":
            gain = int(state.pl * 0.20)
            state.pl += gain
            detail = f"LUCKY — PL +{gain:,} (20%)"
        elif roll == "pl2":
            gain = int(state.pl * 0.12)
            state.pl += gain
            detail = f"PL +{gain:,} (12%)"
        elif roll == "hp":
            gain = int(state.base_max_hp * 0.18)
            state.base_max_hp += gain
            detail = f"Max HP +{gain:,} (18%)"
        elif roll == "crit":
            state.crit_chance = min(0.5, state.crit_chance + 0.1)
            detail = f"Crit → {round(state.crit_chance*100)}%"
        elif roll == "dodge":
            state.dodge_chance = min(0.45, state.dodge_chance + 0.1)
            detail = f"Dodge → {round(state.dodge_chance*100)}%"
        else:
            state.def_pen += 0.12
            detail = f"Def Pen → {round(state.def_pen*100)}%"
    # ── Roguelite items ───────────────────────────────────────────────────────
    elif item_id == "heart_cure":
        removed = len(state.curse_list)
        state.curse_list = []
        heal = int(state.max_hp * 0.25)
        state.hp = min(state.max_hp, state.hp + heal)
        detail = f"{removed} curse(s) cleared · HP +{heal:,}"
    elif item_id == "master_seal":
        state.ki_regen = min(20, state.ki_regen + 3)
        state.crit_chance = min(0.5, state.crit_chance + 0.10)
        detail = f"Ki Regen +3 → {state.ki_regen} · Crit → {round(state.crit_chance*100)}%"
    elif item_id == "android_core":
        state.curse_immune = True
        state.curse_list   = []
        state.ki_regen = max(1, state.ki_regen - 3)
        detail = f"CURSE IMMUNE · Ki Regen -{3} → {state.ki_regen}/turn"
    elif item_id == "baba_shop":
        roll = random.choices(
            ["pl_med", "pl_big", "hp", "crit", "lifesteal"],
            weights=[30, 10, 25, 20, 15]
        )[0]
        if roll == "pl_med":
            gain = int(state.pl * 0.18)
            state.pl += gain
            detail = f"MYSTERY — PL +{gain:,}"
        elif roll == "pl_big":
            gain = int(state.pl * 0.40)
            state.pl += gain
            detail = f"JACKPOT — PL +{gain:,}!"
        elif roll == "hp":
            state.base_max_hp += 1500
            detail = "MYSTERY — Max HP +1,500"
        elif roll == "crit":
            state.crit_chance = min(0.5, state.crit_chance + 0.08)
            detail = f"MYSTERY — Crit → {round(state.crit_chance*100)}%"
        else:
            state.lifesteal = min(0.5, state.lifesteal + 0.06)
            detail = f"MYSTERY — Lifesteal → {round(state.lifesteal*100)}%"
    elif item_id == "weighted_gi":
        state.ki_regen = max(1, state.ki_regen // 2)
        state.pl_kill_mult = min(4.0, state.pl_kill_mult * 2.0)
        detail = f"Ki Regen halved → {state.ki_regen}/turn · Kill PL ×{state.pl_kill_mult:.1f}"
    elif item_id == "vitality_surge":
        heal = int(state.max_hp * 0.40)
        state.base_max_hp = max(200, state.base_max_hp - 800)
        state.hp = min(state.hp + heal, state.max_hp)
        detail = f"HP +{heal:,} · Max HP permanently -800"
    elif item_id == "senzu_fragment":
        heal = int(state.max_hp * 0.45)
        state.hp = min(state.max_hp, state.hp + heal)
        if state.curse_list:
            removed_curse = state.curse_list.pop(0)
            detail = f"HP +{heal:,} · {removed_curse['label']} removed"
        else:
            detail = f"HP +{heal:,} · No curses active"
    elif item_id == "hyperbolic_chamber":
        cost_hp = max(1, int(state.hp * 0.25))
        if state.hp - cost_hp <= 1:
            return jsonify({"error": "HP too low — need more HP to endure the chamber"}), 400
        gain = int(state.pl * 0.55)
        state.hp = max(1, state.hp - cost_hp)
        state.pl += gain
        detail = f"HP -{cost_hp:,} · PL +{gain:,} (55% of current)"
    elif item_id == "elder_kai_seal":
        pl_gain = int(state.pl * 0.08)
        hp_gain = int(state.base_max_hp * 0.08)
        state.pl += pl_gain
        state.base_max_hp += hp_gain
        state.ki_regen = min(20, state.ki_regen + 1)
        detail = f"PL +{pl_gain:,} · Max HP +{hp_gain:,} · Ki Regen +1 → {state.ki_regen}"
    elif item_id == "geti_star":
        state.hp_on_kill = min(0.25, state.hp_on_kill + 0.05)
        detail = f"Kill Heal → {round(state.hp_on_kill*100)}% max HP per kill"
    elif item_id == "recovery_module":
        state.hp_regen = min(0.06, state.hp_regen + 0.02)
        detail = f"HP Regen → {round(state.hp_regen*100)}%/turn"

    state.update_stats()
    return jsonify({"player": vars(state), "detail": detail})


@app.route("/refresh-shop", methods=["POST"])
def refresh_shop():
    state = current_state()
    reroll_cost = 300 + state.wave * 25
    if state.zeni < reroll_cost:
        return jsonify({"error": f"Need {reroll_cost:,} Z to reroll"}), 400
    state.zeni -= reroll_cost
    state.generate_shop()
    return jsonify({
        "shop_items":  state.current_shop,
        "encounter":   state.pending_encounter,
        "boss_preview": state.next_boss_preview,
        "player":      vars(state),
    })


@app.route("/resolve-encounter", methods=["POST"])
def resolve_encounter():
    state  = current_state()
    data   = request.get_json()
    choice = data.get("choice", "decline")
    enc    = state.pending_encounter
    if not enc:
        return jsonify({"error": "No active encounter"}), 400
    state.pending_encounter = None

    if choice == "decline":
        return jsonify({"player": vars(state), "message": "ENCOUNTER DECLINED"})

    effect = enc["effect"]
    msg = ""

    if effect == "roshi_train":
        cost = max(1, int(state.hp * 0.20))
        if state.hp - cost <= 0:
            return jsonify({"error": "HP too low to train safely — need > 1 HP after cost"}), 400
        gain = int(state.pl * 0.30)
        state.hp -= cost
        state.pl += gain
        msg = f"ROSHI TRAINING — PL +{gain:,} · HP -{cost:,}"

    elif effect == "baba_wager":
        bet = max(50, int(state.zeni * 0.40))
        if state.zeni < bet:
            return jsonify({"error": "Insufficient Zeni for the wager"}), 400
        state.zeni -= bet
        if random.random() < 0.55:
            state.zeni += bet * 2
            msg = f"FORTUNE! — Won {bet*2:,} Z"
        else:
            msg = f"BAD LUCK — Lost {bet:,} Z"

    elif effect == "yardrat_deal":
        state.base_max_hp = max(200, state.base_max_hp - 500)
        state.update_stats()
        state.hp = min(state.hp, state.max_hp)
        state.dodge_chance = min(0.55, state.dodge_chance + 0.22)
        msg = f"YARDRAT — Max HP -500 · Dodge → {round(state.dodge_chance*100)}%"

    elif effect == "weighted_training":
        state.ki_regen = max(1, state.ki_regen // 2)
        state.pl_kill_mult = min(4.0, state.pl_kill_mult * 2.0)
        msg = f"KING KAI — Ki Regen halved · Kill PL ×{state.pl_kill_mult:.1f}"

    elif effect == "korin_heal":
        if state.zeni < 400:
            return jsonify({"error": "Need 400 Z for Korin's deal"}), 400
        state.zeni -= 400
        heal = int(state.max_hp * 0.50)
        state.hp = min(state.max_hp, state.hp + heal)
        msg = f"KORIN'S GIFT — HP +{heal:,}"

    elif effect == "reveal_next":
        if state.next_boss_preview:
            b = state.next_boss_preview
            msg = f"ORACLE — {b['name']} · PL {b['pl']:,} · Wave {b['wave']} ({b['waves_away']} away)"
        else:
            msg = "ORACLE — No major boss detected in the next 8 waves."

    elif effect == "hyperbolic_train":
        cost_hp = max(1, int(state.hp * 0.30))
        if state.hp - cost_hp <= 1:
            return jsonify({"error": "HP too low to endure the chamber — need more HP"}), 400
        gain = int(state.pl * 0.65)
        state.hp = max(1, state.hp - cost_hp)
        state.pl += gain
        msg = f"HYPERBOLIC TIME CHAMBER — PL +{gain:,} · HP -{cost_hp:,}"

    elif effect == "bubbles_train":
        if state.zeni < 300:
            return jsonify({"error": "Need 300 Z to train with Bubbles"}), 400
        state.zeni -= 300
        state.dodge_chance = min(0.55, state.dodge_chance + 0.06)
        msg = f"BUBBLES TRAINING — Dodge → {round(state.dodge_chance*100)}% · Cost: 300 Z"

    state.update_stats()
    return jsonify({"player": vars(state), "message": msg})


@app.route("/end-run", methods=["POST"])
def end_run():
    state = current_state()
    old_best, new_best, total = save_run_end(state.ip, state.zenkai_level, state.wave)
    return jsonify({
        "run_stats":    state.run_stats,
        "wave_reached": state.wave,
        "old_best":     old_best,
        "new_best":     new_best,
        "is_new_best":  state.wave > old_best,
        "total_runs":   total,
        "zenkai":       state.zenkai_level,
    })


@app.route("/next-enemy", methods=["POST"])
def next_enemy():
    state = current_state()
    state.wave += 1
    state.is_guarding = False
    state.drop_transform()
    state.kill_streak = 0   # reset per-fight streak at start of each new enemy
    state.enemy = state.spawn_enemy()
    transforms = list(CHAR_TRANSFORMS.get(state.char, {}).keys())
    return jsonify({"enemy": state.enemy, "player": vars(state), "transforms": transforms})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
