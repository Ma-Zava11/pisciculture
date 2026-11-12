import argparse
import random 
import time

from datetime import datetime,timezone

import requests

API_URL = "http://127.0.0.1:8000/api/v1/mesures"

TIMEOUT_HTTP = 10

APPAREIL = [
    {
        "device_id": "ESP32-001",
        "bassin_id": "BAS-001"
    }
    # {
#     "device_id": "ESP32-002",
#     "bassin_id": "BAS-002"
# }

]

def generer_mesure(appareil, mode= "normal") : 
    temperature  = round(
        random.uniform(26.0, 29.0), 2
    )

    ph = round(
        random.uniform(6.8,8.0), 2
    )

    oxygene = round(
        random.uniform(5.0,7.0), 2
    )
    if mode == "anomalie" :
        type_anomalie = random.choice([
            "temperature",
            "ph",
            "oxygene"
        ])
        if type_anomalie == "temperature" :
            temperature = round(
                random.uniform(33.0,36.0), 2 
            )

        elif type_anomalie == "ph" :
            ph = round(
                random.uniform(4.5,5.5),2
            )
        elif type_anomalie == "oxygene" : 
            oxygene = round(
                random.uniform(1.0,2.5),2
            )
    mesure = {
        "device_id" : appareil["device_id"],
        "bassin_id" : appareil["bassin_id"],
        "temperature_c" : temperature,
        "ph" : ph,
        "oxygene_dissous_mg_l" : oxygene,
        "measure_at": datetime.now(timezone.utc).isoformat(),
        "source" : "SIMULATION"
    }
    return mesure

def envoyer_mesure(mesure) :
    try: 
        response = requests.post(
            API_URL,
            json=mesure,
            timeout=TIMEOUT_HTTP
        )
        if response.status_code == 201:
            print(
                "[SUCCES] Mesure enregistrée"
                f"pour {mesure['bassin_id']}"
            )
            return True

        print(
            f"[ERREUR HTTP {response.status_code}]"
            f"{response.text[:500]}"
        )

        return False

    except requests.exceptions.ConnectionError:
        print(
            "[ERREUR] Connection impossible à FastApi."
            "Vérifie que le serveur fonctionne sur"
            "le port 8000."
        )
        return False
    except requests.exceptions.Timeout : 
        print(
            "[ERREUR] Le serveur FastApi"
            "ne répond pas dans le délai prévu."
        )
        return False
    except requests.exceptions.RequestException as erreur: 
        print(
            f"[ERREUR HTTP] {erreur}"
        )
        return False

def lancer_simulation(intervalle, cycles, mode):
    compteur = 0
    succes = 0
    echecs = 0

    print("=" * 55)
    print("SIMULATEUR IOT - PISCICULTURE INTELLIGENTE")
    print("=" * 55)

    print(f"API : {API_URL}")
    print(f"Mode : {mode}")
    print(f"Intervalle : {intervalle} seconde(s)")
    print(f"Appareils : {len(APPAREIL)}")
    print(
        "Cycles : "
        + ("illimités" if cycles == 0 else str(cycles))
    )
    print("Appuyer sur CTRL + C pour arrêter")
    print("=" * 55)

    try:
        while cycles == 0 or compteur < cycles:
            compteur += 1
            print(f"\n --- CYCLE {compteur} ---")
            for appareil in APPAREIL:
                mesure = generer_mesure(
                    appareil,
                    mode=mode
                )
                print(
                    f"Appareil : {mesure['device_id']}"
                )
                print(
                    f"bassin : {mesure['bassin_id']}"
                )
                print(
                    f"Température : "
                    f"{mesure['temperature_c']} °C"
                )

                print(
                    f"pH : {mesure['ph']}"
                )

                print(
                    f"Oxygène dissous : "
                    f"{mesure['oxygene_dissous_mg_l']} mg/L"
                )

                resultat = envoyer_mesure(mesure)
                if resultat:
                    succes += 1
                else:
                    echecs += 1

            if cycles == 0 or compteur < cycles:
                time.sleep(intervalle)
    except KeyboardInterrupt:
        print("\nSimmulation arrêtée par l'utilisateur.")

    finally:
         print("----BILAN----- ")
         print(f"cycles effectués : {compteur}")
         print(f"Mesures acceptés : {succes}")
         print(f"Mesure refusé : {echecs}")

if __name__ == "__main__" : 
    parser = argparse.ArgumentParser(
        description="Simulateur Iot pour la pisciculture"
    )
    parser.add_argument(
        "--intervalle",
        type=float,
        default=10,
        help="Seconde entre les cycles (default : 10)"
    )

    parser.add_argument(
        "--cycles",
        type=int,
        default=0,
        help= "Nombre de cycle (0 = continu)"
    )
    parser.add_argument(
        "--mode",
        choices=["normal", "anomalie"],
        default="normal",
        help="Mode de similation"
    )

    args = parser.parse_args()

    if args.intervalle <= 0:
        parser.error(
            "L'intervalle doit ête supérieur à zéro."
        )
    if args.cycles < 0:
        parser.error(
            "Le nombre de cycles ne peut pas être négatif."
        )
    lancer_simulation(
        intervalle=args.intervalle,
        cycles=args.cycles,
        mode=args.mode
    )