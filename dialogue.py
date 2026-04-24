class Dialogue:
    @staticmethod
    def get_boss_intro(boss_name):
        intros = {
            "Nappa (Boss)": "Nappa: 'Look Vegeta, another bug to squash! I'll break you in half!'",
            "Vegeta (Boss)": "Vegeta: 'I am the Prince of all Saiyans! You are nothing!'"
        }
        return intros.get(boss_name, "A powerful foe appears!")