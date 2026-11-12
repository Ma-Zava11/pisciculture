
"""
SIMULATEUR MULTI-BASSINS — PISCICULTURE INTELLIGENTE

Fonctionnalités :
- Simuler plusieurs bassins simultanément.
- Envoyer des mesures toutes les 10 secondes.
- Générer des températures, pH et oxygène variables.
- Simuler occasionnellement des anomalies.
- Envoyer les données vers FastAPI.
- Continuer jusqu'à l'arrêt manuel (CTRL+C).

Dépendance :
    pip install requests
"""

import argparse
import random
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import requests


# ============================================================
# CONFIGURATION
# ============================================================

API_URL = "http://127.0.0.1:8000/api/v1/mesures"

INTERVALLE = 10

# IMPORTANT :
# bassin_id correspond au CODE du bassin dans PostgreSQL,
# et non à son identifiant numérique.
#
# device_id doit correspondre à appareils.identifiant.
#
# Chaque appareil doit être associé au bon bassin.
BASSINS = [
    {
        "id": 1,
        "bassin_id": "BAS-001",
        "device_id": "ESP32-001",
    },
    {
        "id": 2,
        "bassin_id": "BAS-002",
        "device_id": "ESP32-002",
    },
    {
        "id": 3,
        "bassin_id": "BAS-003",
        "device_id": "ESP32-003",
    },
]


# ============================================================
# GÉNÉRATION DES MESURES
# ============================================================

def generer_mesure(bassin, mode="mixte"):
    """
    Générer une mesure pour un bassin.

    Modes :
    - normal : paramètres dans les plages normales.
    - anomalie : au moins un paramètre anormal.
    - mixte : alternance aléatoire entre normal et anomalie.

    Les valeurs sont fictives et destinées aux tests.
    """

    # Valeurs de base différentes pour chaque bassin.
    numero = bassin["id"]

    temperature = random.uniform(
        26.0 + numero * 0.1,
        29.0 + numero * 0.1
    )

    ph = random.uniform(6.8, 8.2)

    oxygene = random.uniform(5.5, 8.0)

    # En mode mixte, 25 % des cycles environ
    # contiennent une anomalie.
    anomalie = (
        mode == "anomalie"
        or (
            mode == "mixte"
            and random.random() < 0.25
        )
    )

    if anomalie:
        parametre = random.choice([
            "temperature",
            "ph",
            "oxygene"
        ])

        if parametre == "temperature":
            temperature = random.choice([
                random.uniform(20.0, 22.5),
                random.uniform(33.5, 36.0)
            ])

        elif parametre == "ph":
            ph = random.choice([
                random.uniform(4.5, 5.8),
                random.uniform(9.2, 10.0)
            ])

        elif parametre == "oxygene":
            oxygene = random.uniform(1.0, 2.8)

    return {
        "device_id": bassin["device_id"],
        "bassin_id": bassin["bassin_id"],

        "temperature_c": round(temperature, 2),
        "ph": round(ph, 2),
        "oxygene_dissous_mg_l": round(oxygene, 2),

        "measure_at": datetime.now(
            timezone.utc
        ).isoformat(),

        "source": "SIMULATION"
    }


# ============================================================
# ENVOI VERS FASTAPI
# ============================================================

def envoyer_mesure(bassin, mode):
    """
    Envoyer une mesure à FastAPI.

    Une erreur sur un bassin n'arrête pas les autres.
    """

    mesure = generer_mesure(bassin, mode)

    try:
        reponse = requests.post(
            API_URL,
            json=mesure,
            timeout=5
        )

        reponse.raise_for_status()

        print(
            f"[OK] {bassin['bassin_id']} | "
            f"T={mesure['temperature_c']} °C | "
            f"pH={mesure['ph']} | "
            f"O2={mesure['oxygene_dissous_mg_l']} mg/L | "
            f"HTTP {reponse.status_code}",
            flush=True
        )

    except requests.RequestException as erreur:
        print(
            f"[ERREUR] {bassin['bassin_id']} : "
            f"{erreur}",
            flush=True
        )


# ============================================================
# BOUCLE DE SIMULATION
# ============================================================

def demarrer_simulation(bassins, intervalle, mode):
    """
    Simuler tous les bassins à chaque cycle.

    ThreadPoolExecutor permet d'envoyer les requêtes
    en parallèle, plutôt que d'attendre chaque bassin.

    Les cycles démarrent à intervalle régulier.
    """

    print("=" * 60)
    print("SIMULATEUR MULTI-BASSINS")
    print("=" * 60)

    print(f"Bassins : {len(bassins)}")
    print(f"Intervalle : {intervalle} secondes")
    print(f"Mode : {mode}")
    print("Arrêt : CTRL+C")
    print("=" * 60)

    compteur = 0

    with ThreadPoolExecutor(
        max_workers=min(len(bassins), 20)
    ) as executor:

        try:
            while True:
                debut_cycle = time.monotonic()
                compteur += 1

                print(
                    f"\n--- CYCLE {compteur} ---",
                    flush=True
                )

                # Soumettre une requête pour chaque bassin.
                futures = [
                    executor.submit(
                        envoyer_mesure,
                        bassin,
                        mode
                    )
                    for bassin in bassins
                ]

                # Attendre la fin de tous les envois.
                for future in futures:
                    future.result()

                # Garder un intervalle de 10 secondes
                # entre les débuts de deux cycles.
                duree_cycle = (
                    time.monotonic() - debut_cycle
                )

                attente = max(
                    0,
                    intervalle - duree_cycle
                )

                time.sleep(attente)

        except KeyboardInterrupt:
            print("\nSimulation arrêtée.")


# ============================================================
# PARAMÈTRES EN LIGNE DE COMMANDE
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Simulateur IoT multi-bassins"
    )

    parser.add_argument(
        "--bassins",
        nargs="+",
        type=int,
        default=[1, 2, 3],
        help="Numéros des bassins à simuler"
    )

    parser.add_argument(
        "--intervalle",
        type=float,
        default=INTERVALLE,
        help="Intervalle entre les cycles en secondes"
    )

    parser.add_argument(
        "--mode",
        choices=["normal", "anomalie", "mixte"],
        default="mixte",
        help="Mode de simulation"
    )

    args = parser.parse_args()

    if args.intervalle <= 0:
        parser.error(
            "L'intervalle doit être supérieur à zéro."
        )

    # Sélectionner uniquement les bassins demandés.
    selection = [
        bassin
        for bassin in BASSINS
        if bassin["id"] in args.bassins
    ]

    # Vérifier que tous les bassins demandés existent
    # dans la configuration du simulateur.
    disponibles = {b["id"] for b in BASSINS}
    inconnus = set(args.bassins) - disponibles

    if inconnus:
        parser.error(
            f"Bassins non configurés : {sorted(inconnus)}"
        )

    demarrer_simulation(
        selection,
        args.intervalle,
        args.mode
    )


if __name__ == "__main__":
    main()
