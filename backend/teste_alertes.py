from app.services.detecteur_alertes import (
    analyser_mesure,
    niveau_global
)

mesure_normale = {
    "temperature_c" : 27.5,
    "ph" : 7.2,
    "oxygene_dissous_mg_l": 6.1
}
mesure_avertissement = {
    "temperature_c" : 31.0,
    "ph" :7.2,
    "oxygene_dissous_mg_l" :4.0 
}
mesure_critique = {
    "temperature_c" : 35.0,
    "ph": 5.2,
    "oxygene_dissous_mg_l" : 2.0
}

def tester(nom, mesure, attendu) : 
    print(f"\n---{nom}---")

    alertes = analyser_mesure(mesure)
    niveau = niveau_global(alertes)

    print("Niveau global:", niveau)

    for alerte in alertes:
        print(
            f"[{alerte.niveau}]"
            f"[{alerte.message}]"
        )
    assert niveau == attendu,(
        f"Attendu : {attendu}, obtenu : {niveau}"
    )

if __name__ == "__main__":
    tester(
        "MESURE NORMALE",
        mesure_normale,
        "NORMAL"

    )
    tester(
        "MESURE AVEC AVERTISSEMENT",
        mesure_avertissement,
        "AVERTISSEMENT"
    )

    tester(
        "MESURE CRITQUE",
        mesure_critique,
        "CRITIQUE"
    )

    print("\n Tous les tests sont réussis !")
