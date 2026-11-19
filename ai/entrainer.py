"""Comparer quatre approches ; choisir sur validation ; tester une seule fois.

Exécution : python -m ai.entrainer
Ne pas utiliser le jeu de test pour ajuster le choix du modèle.
"""
import json
import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import ExtraTreesRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from .config import DATASETS, MODELS, RAPPORTS, HORIZON_MINUTES, SEUIL_ALERTE

NUMERIQUES = [
    'temperature_c', 'ph', 'oxygene_dissous_mg_l',
    'oxygene_retard_1', 'oxygene_retard_6', 'oxygene_retard_30',
    'variation_o2_1min', 'variation_o2_5min',
    'heure_sin', 'heure_cos', 'aeration_active',
]
CATEGORIQUES = ['bassin_id']
FEATURES = NUMERIQUES + CATEGORIQUES


def creer_pipeline(modele, normaliser=False):
    # Tous les traitements sont ajustés UNIQUEMENT sur le jeu d'entraînement.
    etapes = [('imputation', SimpleImputer(strategy='median'))]
    if normaliser:
        etapes.append(('normalisation', StandardScaler()))
    preprocesseur = ColumnTransformer([
        ('num', Pipeline(etapes), NUMERIQUES),
        ('bassin', OneHotEncoder(handle_unknown='ignore'), CATEGORIQUES),
    ])
    return Pipeline([('preparation', preprocesseur), ('modele', modele)])


def mesures(y, predictions):
    return {
        'MAE': float(mean_absolute_error(y, predictions)),
        'RMSE': float(np.sqrt(mean_squared_error(y, predictions))),
        'R2': float(r2_score(y, predictions)),
    }


def predire(nom, modele, df):
    if nom == 'Persistance':
        return df['oxygene_dissous_mg_l'].to_numpy()
    return modele.predict(df[FEATURES])


def main():
    fichier = DATASETS / 'dataset_prediction.csv'
    if not fichier.exists():
        raise SystemExit('Exécute d’abord : python -m ai.preparer_dataset')
    df = pd.read_csv(fichier)
    assert df['source'].eq('SIMULATION_TEMPORELLE').all()
    train = df[df.partition == 'train'].copy()
    validation = df[df.partition == 'validation'].copy()
    test = df[df.partition == 'test'].copy()
    for a, b in ((train, validation), (train, test), (validation, test)):
        assert set(a.run_id).isdisjoint(set(b.run_id)), 'Fuite entre les runs'

    modeles = {
        'Persistance': None,
        'Ridge': creer_pipeline(Ridge(alpha=10), normaliser=True),
        'Random Forest': creer_pipeline(RandomForestRegressor(
            n_estimators=120, max_depth=12, min_samples_leaf=4,
            random_state=42, n_jobs=-1)),
        'Extra Trees': creer_pipeline(ExtraTreesRegressor(
            n_estimators=120, max_depth=12, min_samples_leaf=4,
            random_state=42, n_jobs=-1)),
    }
    resultats = []
    for nom, modele in modeles.items():
        if modele is not None:
            modele.fit(train[FEATURES], train['oxygene_cible'])
        pred = predire(nom, modele, validation)
        resultats.append({'modele': nom, **mesures(validation.oxygene_cible, pred)})
    classement = pd.DataFrame(resultats).sort_values('MAE')
    classement.to_csv(RAPPORTS / 'comparaison_modeles.csv', index=False)
    print('\n=== VALIDATION (choix du modèle) ===')
    print(classement.to_string(index=False))
    gagnant = str(classement.iloc[0]['modele'])
    print(f'\nApproche choisie sur validation : {gagnant}')

    # Réentraînement de l'approche gagnante sur train + validation.
    apprentissage = pd.concat([train, validation], ignore_index=True)
    if gagnant == 'Persistance':
        modele_final = None
    else:
        # Recréer un estimateur vierge pour éviter tout état appris sur validation.
        from sklearn.base import clone
        modele_final = clone(modeles[gagnant])
        modele_final.fit(apprentissage[FEATURES], apprentissage['oxygene_cible'])

    predictions = predire(gagnant, modele_final, test)
    scores_test = mesures(test.oxygene_cible, predictions)
    print('\n=== TEST FINAL (non utilisé pour choisir) ===')
    print(scores_test)
    print('Seuil d’alerte expérimental :', SEUIL_ALERTE, 'mg/L')

    # Une seule sortie finale : soit un pipeline ML, soit la règle de persistance.
    artefact = {
        'approche': gagnant,
        'pipeline': modele_final,
        'features': FEATURES,
        'horizon_minutes': HORIZON_MINUTES,
        'source_entrainement': 'SIMULATION_TEMPORELLE',
        'statut': 'EXPERIMENTAL_NON_VALIDE_SUR_CAPTEURS_REELS',
        'seuil_alerte_experimental': SEUIL_ALERTE,
    }
    joblib.dump(artefact, MODELS / 'modele_oxygene.joblib')
    with open(MODELS / 'metadata.json', 'w', encoding='utf-8') as f:
        json.dump({k: v for k, v in artefact.items() if k not in ('pipeline', 'features')}
                  | {'features': FEATURES, 'scores_test': scores_test}, f, indent=2, ensure_ascii=False)
    pd.DataFrame([{'modele': gagnant, **scores_test}]).to_csv(
        RAPPORTS / 'evaluation_test.csv', index=False)
    sorties = test[['run_id', 'scenario', 'bassin_id', 'measure_at', 'date_cible',
                   'oxygene_dissous_mg_l', 'oxygene_cible']].copy()
    sorties['oxygene_predit'] = predictions
    sorties.to_csv(RAPPORTS / 'predictions_test.csv', index=False)
    print('\n[OK] Modèle final :', MODELS / 'modele_oxygene.joblib')
    print('[OK] Rapports :', RAPPORTS)


if __name__ == '__main__':
    main()
