# IA pisciculture — reconstruction propre (Jour 17)

## Installation
Copier le dossier `ai` fourni à la racine de `pisciculture`, sans toucher à `backend`, `frontend`, ni `data/raw/WQD.xlsx`.

Depuis `C:\Users\Mazava\Desktop\pisciculture` (PowerShell), dans le venv Python du projet :

```powershell
python -m pip install numpy pandas scikit-learn joblib
python -m ai.simulateur_temporel
python -m ai.preparer_dataset
python -m ai.entrainer
```

## Protocole
- 3 bassins × 15 runs de 3 heures ; intervalle 10 secondes.
- Les runs sont indépendants et divisés en train (9), validation (3), test (3) par bassin.
- Cible : oxygène dissous à +60 pas, soit +10 minutes.
- La source est uniquement `SIMULATION_TEMPORELLE`. Les mesures `SIMULATION`, `WQD_EXCEL` et `CAPTEUR_REEL` en base ne sont ni modifiées ni utilisées.
- Quatre approches : Persistance, Ridge, Random Forest, Extra Trees.
- Sélection sur validation, évaluation finale sur test indépendant par run.
- Les scénarios simulés sont simplifiés, non calibrés et ne constituent PAS une validation sur bassin réel.

## Fichiers générés
- `ai/datasets/mesures_synthetiques.csv`
- `ai/datasets/dataset_prediction.csv`
- `ai/models/modele_oxygene.joblib`
- `ai/models/metadata.json`
- `ai/rapports/comparaison_modeles.csv`
- `ai/rapports/evaluation_test.csv`
- `ai/rapports/predictions_test.csv`

## Jour 18 — intégration API
Charger l'artefact avec `joblib.load` uniquement depuis un fichier local de confiance. Si `approche == 'Persistance'`, prédire la valeur courante d'oxygène. Sinon, fournir au pipeline les `features` dans le même format que l'entraînement. Les retards et variations doivent être calculés à partir de l'historique réel du bassin (au moins 5 minutes), sans valeurs futures. Retourner `statut` et `horizon_minutes` dans la réponse API.
