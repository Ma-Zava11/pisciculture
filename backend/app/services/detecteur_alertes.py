from dataclasses import dataclass, asdict

@dataclass
class AlerteDetectee:
    parametre: str
    valeur: float
    niveau: str
    message: str
    unite: str

    def vers_dict(self):
        return asdict(self)

SEUILS = {
    "temperature_c" :{
        "normal_min" : 26.0,
        "normal_max" : 30.0,
        "critique_min" :23.0,
        "critique_max" : 33.0,
        "unite" : "°C",
        "libelle" : "Température"
    },
    "ph" : {
        "normal_min" : 6.5,
        "normal_max" : 8.5,
        "critique_min" : 6.0,
        "critique_max" : 9.0,
        "unite" :"",
        "libelle":"pH"
    },
    "oxygene_dissous_mg_l" : {
        "normal_min": 5.0,
        "normal_max" : None,
        "critique_min" : 3.0,
        "critique_max" : None,
        "unite": "mg/L",
        "libelle" : "Oxygène dissous"
    }
}
def classifier_valeur(valeur, seuil):
    if valeur <= seuil["critique_min"]:
        return "CRITIQUE"

    if (seuil["critique_max"] is not None and valeur >=  seuil["critique_max"]):
        return "CRITIQUE"

    if valeur < seuil["normal_min"]:
        return "AVERTISSEMENT"

    if(seuil["normal_max"] is not None and valeur > seuil["normal_max"] ):
        return "AVERTISSEMENT"
    return "NORMAL"

def analyser_mesure(mesure):
    alerte = []
    for parametre, seuil in SEUILS.items():
        valeur = mesure.get(parametre)

        if valeur is None:
            continue

        niveau = classifier_valeur(
            valeur, seuil 
        )

        if niveau == "NORMAL":
            continue

        message = (
            f"{seuil['libelle']} anormale :"
            f"{valeur}{seuil['unite']}"
            f"(niveau : {niveau})"
        )

        alerte.append(
            AlerteDetectee(
                parametre=parametre,
                valeur=valeur,
                niveau=niveau,
                message=message,
                unite=seuil["unite"]
            )
        )

    return alerte
def niveau_global(alertes) : 
    if any(a.niveau == "CRITIQUE" for a in alertes) :
        return "CRITIQUE"
    if any(a.niveau == "AVERTISSEMENT" for a in alertes):
        return "AVERTISSEMENT"
    return "NORMAL"
