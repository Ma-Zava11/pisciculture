"""Construire une cible à +10 min sans mélanger les runs ni les sources."""
import numpy as np
import pandas as pd
from .config import DATASETS, HORIZON_PAS, PAS_SECONDES


def main():
    entree = DATASETS / 'mesures_synthetiques.csv'
    if not entree.exists():
        raise SystemExit('Exécute d’abord : python -m ai.simulateur_temporel')
    df = pd.read_csv(entree, parse_dates=['measure_at'])
    df = df[df['source'] == 'SIMULATION_TEMPORELLE'].copy()
    df = df.sort_values(['run_id', 'measure_at']).reset_index(drop=True)
    g = df.groupby('run_id', sort=False)
    # Les décalages sont strictement internes à chaque run.
    for decalage in (1, 6, 30):
        df[f'oxygene_retard_{decalage}'] = g['oxygene_dissous_mg_l'].shift(decalage)
    df['variation_o2_1min'] = df['oxygene_dissous_mg_l'] - df['oxygene_retard_6']
    df['variation_o2_5min'] = df['oxygene_dissous_mg_l'] - df['oxygene_retard_30']
    df['oxygene_cible'] = g['oxygene_dissous_mg_l'].shift(-HORIZON_PAS)
    df['date_cible'] = g['measure_at'].shift(-HORIZON_PAS)
    # Variables cycliques connues au moment de la mesure.
    heures = df['measure_at'].dt.hour + df['measure_at'].dt.minute / 60
    df['heure_sin'] = np.sin(2 * np.pi * heures / 24)
    df['heure_cos'] = np.cos(2 * np.pi * heures / 24)
    df = df.dropna(subset=['oxygene_retard_30', 'oxygene_cible', 'date_cible']).copy()
    horizon = (df['date_cible'] - df['measure_at']).dt.total_seconds()
    assert horizon.eq(HORIZON_PAS * PAS_SECONDES).all(), 'Horizon non conforme'
    # Partitions par RUN ENTIER : aucune fenêtre d'un run ne traverse une partition.
    # 0..8 train ; 9..11 validation ; 12..14 test.
    df['numero_run'] = df['run_id'].str.extract(r'-R(\d+)$')[0].astype(int)
    df['partition'] = np.select(
        [df['numero_run'] < 9, df['numero_run'] < 12],
        ['train', 'validation'], default='test'
    )
    assert df.groupby('run_id')['partition'].nunique().eq(1).all()
    sortie = DATASETS / 'dataset_prediction.csv'
    df.to_csv(sortie, index=False)
    print(f'[OK] {len(df):,} exemples -> {sortie}')
    print(df.groupby(['partition', 'scenario']).size().to_string())


if __name__ == '__main__':
    main()
