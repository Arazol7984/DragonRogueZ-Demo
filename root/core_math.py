import random

class GameEngine:
    @staticmethod
    def get_modifier(attacker_race, defender_race):
        advantages = {
            "Saiyan": ["Frieza Race", "Minion"],
            "Frieza Race": ["Namekian", "Human"],
            "Namekian": ["Android", "Saiyan"],
            "Android": ["Saiyan", "Human"],
            "Human": ["Android", "Namekian"],
            "Minion": ["Frieza Race", "Android"]
        }
        if defender_race in advantages.get(attacker_race, []): return 2.0
        for race, targets in advantages.items():
            if race == defender_race and attacker_race in targets: return 0.5
        return 1.0

    @staticmethod
    def calculate_damage(attacker, defender, move_type, is_defending=False):
        stat = attacker.strike if move_type == "Strike" else attacker.ki
        
        # PL DIFFERENCE RATIO
        # If your PL is 2000 and enemy is 1000, you do 2x damage.
        pl_ratio = attacker.power_level / defender.power_level
        
        margin = random.uniform(0.9, 1.1)
        base_dmg = stat * margin * pl_ratio # PL ratio applied here
        
        if move_type == attacker.style: base_dmg *= 1.2
        
        # Crit Logic
        if random.random() < 0.15:
            base_dmg *= 2
            print(f"⭐ CRITICAL HIT! ({attacker.name})")

        mod = GameEngine.get_modifier(attacker.race, defender.race)
        final_dmg = int(base_dmg * mod)
        
        return int(final_dmg * 0.5) if is_defending else final_dmg