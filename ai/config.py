from pathlib import Path

RACINE = Path(__file__).resolve().parent
DATASETS = RACINE / 'datasets'
MODELS = RACINE / 'models'
RAPPORTS = RACINE / 'rapports'
PAS_SECONDES = 10
HORIZON_MINUTES = 10
HORIZON_PAS = HORIZON_MINUTES * 60 // PAS_SECONDES
SEUIL_ALERTE = 4.0  # Seuil expérimental, à adapter à l'espèce

for dossier in (DATASETS, MODELS, RAPPORTS):
    dossier.mkdir(parents=True, exist_ok=True)
