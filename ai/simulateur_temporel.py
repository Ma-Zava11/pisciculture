"""Simulation de séries temporelles synthétiques, sans accès à PostgreSQL.

Exécution depuis la racine du projet : python -m ai.simulateur_temporel
Le simulateur n'est PAS un modèle physique validé de l'oxygène dissous.
"""
from datetime import datetime, timedelta, timezone
import numpy as np
import pandas as pd
from .config import DATASETS, PAS_SECONDES


def simuler_run(bassin_id: int, numero_run: int, duree_heures: int = 3) -> list[dict]:
    # Chaque run possède sa propre graine : séries reproductibles et indépendantes.
    graine = 20261119 + bassin_id * 1000 + numero_run * 31
    rng = np.random.default_rng(graine)
    n = duree_heures * 3600 // PAS_SECONDES
    # Les runs ne sont pas assemblés comme une seule continuité temporelle.
    debut = datetime(2026, 11, 1, tzinfo=timezone.utc) + timedelta(days=numero_run, hours=bassin_id)
    run_id = f'B{bassin_id:02d}-R{numero_run:02d}'
    # Diversité de scénarios, présente dans chaque partition.
    scenario = ['normal', 'panne_aeration', 'chaleur', 'faible_oxygene', 'recuperation'][numero_run % 5]
    phase = numero_run * 0.41 + bassin_id * 0.7
    temperature = 27.0 + 0.3 * bassin_id + rng.normal(0, 0.15)
    ph = 7.35 + rng.normal(0, 0.08)
    oxygene = 6.7 + rng.normal(0, 0.25)
    # Déclenchement d'un événement à un instant différent selon le run.
    debut_evt = int(n * rng.uniform(0.25, 0.42))
    fin_evt = int(n * rng.uniform(0.65, 0.80))
    lignes = []

    for i in range(n):
        instant = debut + timedelta(seconds=i * PAS_SECONDES)
        heure = instant.hour + instant.minute / 60 + instant.second / 3600
        cycle = np.sin(2 * np.pi * (heure - 6) / 24 + phase * 0.08)
        evt = debut_evt <= i < fin_evt
        aeration = not (scenario == 'panne_aeration' and evt)
        # Température : inertie et cycle jour/nuit ; chaleur lors d'un événement.
        temp_cible = 27.2 + 0.25 * bassin_id + 1.3 * cycle
        if scenario == 'chaleur' and evt:
            temp_cible += 3.2
        temperature += 0.0025 * (temp_cible - temperature) + rng.normal(0, 0.012)
        # pH : évolution lente avec bruit instrumental.
        ph_cible = 7.3 + 0.15 * cycle + 0.025 * (temperature - 27)
        ph += 0.003 * (ph_cible - ph) + rng.normal(0, 0.003)
        # Oxygène : relaxation vers un équilibre dépendant de T, cycle, aération.
        # Ces coefficients sont des hypothèses de simulation, PAS des lois calibrées.
        equilibre = 7.0 - 0.16 * (temperature - 27) + 0.35 * cycle
        if not aeration:
            equilibre -= 4.5
        if scenario == 'faible_oxygene' and evt:
            equilibre -= 3.2
        if scenario == 'recuperation' and evt:
            equilibre += 1.3
        # Une relaxation plus rapide en panne simule une baisse progressive.
        taux = 0.008 if not aeration else 0.004
        oxygene += taux * (equilibre - oxygene) + rng.normal(0, 0.018)
        oxygene = float(np.clip(oxygene, 0.5, 14.0))
        lignes.append({
            'run_id': run_id,
            'scenario': scenario,
            'source': 'SIMULATION_TEMPORELLE',
            'bassin_id': bassin_id,
            'measure_at': instant.isoformat(),
            'temperature_c': round(float(temperature), 3),
            'ph': round(float(ph), 3),
            'oxygene_dissous_mg_l': round(oxygene, 3),
            'aeration_active': int(aeration),
        })
    return lignes


def main():
    lignes = []
    # 15 runs par bassin : 9 train, 3 validation, 3 test.
    # Chaque partition contient plusieurs occurrences de chaque scénario.
    for bassin_id in (1, 2, 3):
        for numero_run in range(15):
            lignes.extend(simuler_run(bassin_id, numero_run))
    df = pd.DataFrame(lignes)
    chemin = DATASETS / 'mesures_synthetiques.csv'
    df.to_csv(chemin, index=False)
    print(f'[OK] {len(df):,} mesures, {df.run_id.nunique()} runs -> {chemin}')
    print(df.groupby(['scenario', 'bassin_id']).size().to_string())


if __name__ == '__main__':
    main()
