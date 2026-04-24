import random

class Fighter:
    def __init__(self, name, strike, ki, hp, moves, race="Saiyan"):
        self.name = name
        self.race = race
        self.orig_strike = strike
        self.orig_ki = ki
        self.orig_hp = hp 
        self.current_hp = hp
        self.current_ki = 100 
        self.moves = moves
        self.internal_level = 1
        self.xp = 0
        self.xp_to_next = 100
        self.cooldowns = {}
        self.statuses = {}
        self.transformation_mult = 1.0
        self.kaioken_unlocked = False
        self.defend_streak = 0
        self.inventory = [] 

    @property
    def passive_description(self):
        """Returns the specific mechanics of the race passive."""
        descriptions = {
            "Saiyan": "ZENKAI: Attack power increases up to 25% as HP drops.",
            "Namekian": "REGEN: Restores 3% Max HP every turn and +10% Ki Stat. [+1 aura]",
            "Earthling": "MASTERY: +5% boost to both Strike and Ki Stats.",
            "Saibaman": "SWARM: Gains 5% extra damage for every wave cleared (Max 50%).",
            "Boss": "INTIMIDATE: Naturally reduces incoming damage by 15%."
        }
        return descriptions.get(self.race, "None")

    @property
    def max_hp(self):
        _, _, b_hp, _ = self.get_item_bonuses()
        guru_mult = 1.15 if "Guru's Blessing" in self.inventory else 1.0
        return int((self.orig_hp + b_hp) * guru_mult)

    @property
    def max_ki(self):
        _, _, _, b_max_ki = self.get_item_bonuses()
        return 100 + min(25, b_max_ki)

    @property
    def power_level(self):
        b_str, b_ki, _, _ = self.get_item_bonuses()
        r_str, r_ki = self.apply_race_passives()
        total_str = (self.orig_strike + b_str) * r_str
        total_ki = (self.orig_ki + b_ki) * r_ki
        base = (total_str + total_ki)
        level_weight = 1 + (self.internal_level * 0.1)
        return int(base * level_weight * self.transformation_mult)

    def apply_race_passives(self, wave_context=1):
        str_mult, ki_mult = 1.0, 1.0
        if self.race == "Saiyan":
            hp_percent = self.current_hp / self.max_hp
            zenkai = 0.25 * (1.0 - hp_percent)
            str_mult += zenkai; ki_mult += zenkai
        elif self.race == "Namekian":
            ki_mult = 1.10
        elif self.race == "Earthling":
            str_mult, ki_mult = 1.05, 1.05
        elif self.race == "Saibaman":
            swarm_bonus = min(0.50, (wave_context * 0.05))
            str_mult += swarm_bonus
        return str_mult, ki_mult

    def get_item_bonuses(self):
        b_str, b_ki, b_hp, b_max_ki = 0, 0, 0, 0
        for item in self.inventory:
            if "Gravity Room" in item: b_str += 50
            elif "Meditation Mat" in item: b_ki += 50
            elif "Power Pole" in item: b_str += 25; b_ki += 25
            elif "Weights" in item: b_str += 30
            elif "Focus Lens" in item: b_ki += 15
            elif "Hero Cloak" in item: b_hp += 100
            elif "Lead Armor" in item: b_hp += 200
            elif "Energy Drink" in item: b_max_ki += 20 
            elif "Vitamin Water" in item: b_max_ki += 5  
        return b_str, b_ki, b_hp, b_max_ki

    def add_xp(self, amount):
        self.xp += amount
        while self.xp >= self.xp_to_next:
            self.xp -= self.xp_to_next
            self.power_surge()

    def power_surge(self):
        self.internal_level += 1
        self.xp_to_next = int(self.xp_to_next * 1.3)
        self.orig_strike *= 1.12
        self.orig_ki *= 1.12
        self.orig_hp = int(self.orig_hp * 1.1)
        self.current_hp = self.max_hp
        print(f"\n✨ {self.name}'s power is surging! New Power Level: {self.power_level:,}")