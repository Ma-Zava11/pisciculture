
import {
  useCallback,
  useEffect,
  useMemo,
  useState
} from "react";

import {
  Waves,
  Droplets,
  RefreshCw,
  AlertCircle,
  Fish,
  Activity,
  ArrowUpRight,
  Database,
  Thermometer,
  Clock3,
  CheckCircle2
} from "lucide-react";

// Composants déjà présents et nouveau graphique.
import AlertesDashboard from "../components/AlertesDashboard";
import GraphiqueMesures from "../components/GraphiqueMesures";

// Services de communication avec FastAPI.
import {
  getBassins,
  getMesuresBassin,
  getAlertesParBassin
} from "../services/api";

import "./Dashboard.css";

// ============================================================
// CONFIGURATION DE LA SUPERVISION
// ============================================================

// Intervalle entre deux récupérations des mesures.
const INTERVALLE_ACTUALISATION = 5000;

// Une mesure de plus de 60 secondes est considérée
// comme ancienne pour cette démonstration.
// Cette durée devra être adaptée à la fréquence ESP32.
const DELAI_MESURE_ANCIENNE = 60000;

// Seuils provisoires de démonstration.
// À terme, ils seront chargés depuis PostgreSQL
// et adaptés aux espèces et aux bassins.
const SEUILS = {
  temperature_c: {
    normalMin: 26,
    normalMax: 30,
    critiqueMin: 23,
    critiqueMax: 33
  },
  ph: {
    normalMin: 6.5,
    normalMax: 8.5,
    critiqueMin: 6,
    critiqueMax: 9
  },
  oxygene_dissous_mg_l: {
    normalMin: 5,
    normalMax: null,
    critiqueMin: 3,
    critiqueMax: null
  }
};

/**
 * Déterminer le niveau de risque d'une valeur.
 *
 * Cette classification sert à l'affichage.
 * La détection officielle reste côté FastAPI.
 */
function classifierMesure(parametre, valeur) {
  if (valeur === null || valeur === undefined) {
    return "INDISPONIBLE";
  }

  const seuil = SEUILS[parametre];

  if (!seuil) return "INDISPONIBLE";

  const nombre = Number(valeur);

  if (!Number.isFinite(nombre)) {
    return "INDISPONIBLE";
  }

  if (
    nombre <= seuil.critiqueMin ||
    (
      seuil.critiqueMax !== null &&
      nombre >= seuil.critiqueMax
    )
  ) {
    return "CRITIQUE";
  }

  if (
    nombre < seuil.normalMin ||
    (
      seuil.normalMax !== null &&
      nombre > seuil.normalMax
    )
  ) {
    return "AVERTISSEMENT";
  }

  return "NORMAL";
}

/**
 * Formater un volume en litres.
 */
function formaterVolume(volume) {
  return new Intl.NumberFormat("fr-FR").format(volume);
}

/**
 * Formater une date.
 */
function formaterDate(date) {
  if (!date) return "—";

  return new Date(date).toLocaleString("fr-FR");
}

/**
 * Carte affichant un paramètre de qualité d'eau.
 */
function CarteParametre({
  titre,
  valeur,
  unite,
  parametre,
  Icone
}) {
  const niveau = classifierMesure(parametre, valeur);

  return (
    <article className="mesure-card">
      <div className="mesure-card-top">
        <span className="mesure-card-icon">
          <Icone size={21} />
        </span>

        <span
          className={`mesure-niveau ${niveau.toLowerCase()}`}
        >
          {niveau}
        </span>
      </div>

      <span className="mesure-card-label">
        {titre}
      </span>

      <strong className="mesure-card-valeur">
        {valeur == null
          ? "—"
          : Number(valeur).toLocaleString("fr-FR", {
              maximumFractionDigits: 2
            })}

        {valeur != null && unite && (
          <small> {unite}</small>
        )}
      </strong>
    </article>
  );
}

// ============================================================
// DASHBOARD PRINCIPAL
// ============================================================

function Dashboard() {
  // ----------------------------------------------------------
  // 1. ÉTATS GÉNÉRAUX
  // ----------------------------------------------------------

  const [bassins, setBassins] = useState([]);

  const [chargement, setChargement] = useState(true);

  const [erreur, setErreur] = useState("");

  const [derniereMaj, setDerniereMaj] = useState(null);

  // ----------------------------------------------------------
  // 2. ÉTATS DE SUPERVISION
  // ----------------------------------------------------------

  // Identifiant du bassin sélectionné.
  const [bassinSelectionneId, setBassinSelectionneId] =
    useState(null);

  // Historique des mesures du bassin.
  const [mesures, setMesures] = useState([]);

  // Alertes non résolues du bassin.
  const [alertesBassin, setAlertesBassin] = useState([]);

  // Indicateurs de chargement et d'erreur.
  const [chargementMesures, setChargementMesures] =
    useState(false);

  const [erreurMesures, setErreurMesures] = useState("");

  const [derniereMajMesures, setDerniereMajMesures] =
    useState(null);

  // Heure courante, utilisée pour calculer l'ancienneté.
  const [maintenant, setMaintenant] =
    useState(Date.now());

  // ----------------------------------------------------------
  // 3. CHARGER LES BASSINS
  // ----------------------------------------------------------

  const chargerBassins = useCallback(async () => {
    try {
      setChargement(true);
      setErreur("");

      const donnees = await getBassins();

      if (!Array.isArray(donnees)) {
        throw new Error("Format de réponse invalide.");
      }

      setBassins(donnees);
      setDerniereMaj(new Date());

      // Garder le bassin sélectionné s'il existe.
      // Sinon, sélectionner automatiquement le premier.
      setBassinSelectionneId((ancienId) => {
        if (
          ancienId !== null &&
          donnees.some((b) => b.id === ancienId)
        ) {
          return ancienId;
        }

        return donnees.length > 0
          ? donnees[0].id
          : null;
      });

    } catch (error) {
      console.error(
        "Erreur de chargement des bassins :",
        error
      );

      setErreur(
        "Impossible de charger les bassins."
      );

    } finally {
      setChargement(false);
    }
  }, []);

  // Charger les bassins à l'ouverture.
  useEffect(() => {
    chargerBassins();
  }, [chargerBassins]);

  // ----------------------------------------------------------
  // 4. CHARGER LES MESURES ET ALERTES
  // ----------------------------------------------------------

  useEffect(() => {
    if (bassinSelectionneId === null) {
      setMesures([]);
      setAlertesBassin([]);
      return;
    }

    // Permet d'annuler les requêtes au changement de bassin.
    const controller = new AbortController();

    // Empêcher deux actualisations simultanées.
    let actualisationEnCours = false;

    // Vider les anciennes données immédiatement.
    setMesures([]);
    setAlertesBassin([]);
    setDerniereMajMesures(null);
    setErreurMesures("");
    setChargementMesures(true);

    async function actualiserSupervision() {
      if (actualisationEnCours) return;

      actualisationEnCours = true;

      try {
        const [nouvellesMesures, nouvellesAlertes] =
          await Promise.all([
            getMesuresBassin(
              bassinSelectionneId,
              100,
              controller.signal
            ),
            getAlertesParBassin(
              bassinSelectionneId,
              controller.signal
            )
          ]);

        if (controller.signal.aborted) return;

        setMesures(nouvellesMesures);

        // Afficher uniquement les alertes non résolues.
        setAlertesBassin(
          nouvellesAlertes.filter(
            (alerte) =>
              alerte.statut === "ACTIVE" ||
              alerte.statut === "ACQUITTEE"
          )
        );

        setDerniereMajMesures(new Date());
        setMaintenant(Date.now());
        setErreurMesures("");

      } catch (error) {
        if (controller.signal.aborted) return;

        console.error(
          "Erreur de supervision :",
          error
        );

        setErreurMesures(
          "Impossible d'actualiser les mesures " +
          "ou les alertes de ce bassin."
        );

      } finally {
        actualisationEnCours = false;

        if (!controller.signal.aborted) {
          setChargementMesures(false);
        }
      }
    }

    // Premier chargement immédiat.
    actualiserSupervision();

    // Rafraîchissement automatique toutes les 5 secondes.
    const intervalle = setInterval(
      actualiserSupervision,
      INTERVALLE_ACTUALISATION
    );

    return () => {
      clearInterval(intervalle);
      controller.abort();
    };
  }, [bassinSelectionneId]);

  // Actualiser l'ancienneté même si aucune mesure
  // nouvelle n'arrive depuis le backend.
  useEffect(() => {
    const intervalle = setInterval(() => {
      setMaintenant(Date.now());
    }, 5000);

    return () => clearInterval(intervalle);
  }, []);

  // ----------------------------------------------------------
  // 5. STATISTIQUES GÉNÉRALES
  // ----------------------------------------------------------

  const statistiques = useMemo(() => {
    const capaciteTotale = bassins.reduce(
      (total, bassin) =>
        total + (Number(bassin.capacite_litres) || 0),
      0
    );

    return {
      totalBassins: bassins.length,
      capaciteTotale
    };
  }, [bassins]);

  // ----------------------------------------------------------
  // 6. BASSIN SÉLECTIONNÉ
  // ----------------------------------------------------------

  const bassinSelectionne = useMemo(() => {
    return bassins.find(
      (bassin) =>
        bassin.id === bassinSelectionneId
    );
  }, [bassins, bassinSelectionneId]);

  // ----------------------------------------------------------
  // 7. DERNIÈRE MESURE
  // ----------------------------------------------------------

  const derniereMesure = useMemo(() => {
    if (mesures.length === 0) return null;

    // Trier par date, puis par identifiant.
    return [...mesures].sort((a, b) => {
      const ecart =
        Date.parse(b.measure_at) -
        Date.parse(a.measure_at);

      return ecart || b.id - a.id;
    })[0];
  }, [mesures]);

  // Calculer l'âge de la dernière mesure.
  const ageDerniereMesure = derniereMesure
    ? maintenant -
      Date.parse(derniereMesure.measure_at)
    : null;

  // Ne pas considérer comme récente une mesure ancienne.
  const mesureAncienne =
    ageDerniereMesure !== null &&
    Number.isFinite(ageDerniereMesure) &&
    ageDerniereMesure > DELAI_MESURE_ANCIENNE;

  // ----------------------------------------------------------
  // 8. RAFRAÎCHISSEMENT MANUEL
  // ----------------------------------------------------------

  function actualiserDashboard() {
    // Recharger les bassins.
    chargerBassins();

    // Déclencher également le rechargement des mesures
    // via l'événement de changement de bassin n'est pas
    // nécessaire : elles sont déjà actualisées toutes
    // les 5 secondes.
  }

  // ----------------------------------------------------------
  // 9. AFFICHAGE
  // ----------------------------------------------------------

  return (
    <main className="dashboard">

      {/* EN-TÊTE PRINCIPAL */}
      <header className="dashboard-header">
        <div>
          <div className="dashboard-eyebrow">
            <Activity size={15} />
            Plateforme de supervision IoT
          </div>

          <h1>Pisciculture intelligente</h1>

          <p>
            Supervision des bassins, suivi des installations
            et surveillance de la qualité de l'eau.
          </p>
        </div>

        <button
          type="button"
          className="dashboard-refresh"
          onClick={actualiserDashboard}
          disabled={chargement}
        >
          <RefreshCw
            size={17}
            className={chargement ? "rotation" : ""}
          />

          {chargement
            ? "Chargement..."
            : "Actualiser"}
        </button>
      </header>

      {/* STATISTIQUES EXISTANTES */}
      <section className="dashboard-stats">

        <article className="stat-card">
          <div className="stat-icon blue">
            <Waves size={23} />
          </div>

          <span className="stat-label">
            Bassins enregistrés
          </span>

          <strong className="stat-value">
            {statistiques.totalBassins}
          </strong>

          <span className="stat-detail">
            Nombre total dans le système
          </span>
        </article>

        <article className="stat-card">
          <div className="stat-icon teal">
            <Droplets size={23} />
          </div>

          <span className="stat-label">
            Capacité totale
          </span>

          <strong className="stat-value">
            {formaterVolume(
              statistiques.capaciteTotale
            )}
            <small> L</small>
          </strong>

          <span className="stat-detail">
            Capacité déclarée des bassins
          </span>
        </article>

        <article className="stat-card">
          <div className="stat-icon purple">
            <Fish size={23} />
          </div>

          <span className="stat-label">
            Suivi de production
          </span>

          <strong className="stat-value stat-text">
            À connecter
          </strong>

          <span className="stat-detail">
            Lots, espèces et effectifs
          </span>
        </article>

        <article className="stat-card">
          <div className="stat-icon orange">
            <Database size={23} />
          </div>

          <span className="stat-label">
            Synchronisation
          </span>

          <strong className="stat-value stat-text">
            {derniereMaj
              ? derniereMaj.toLocaleTimeString(
                  "fr-FR",
                  {
                    hour: "2-digit",
                    minute: "2-digit"
                  }
                )
              : "En attente"}
          </strong>

          <span className="stat-detail">
            Dernière récupération des bassins
          </span>
        </article>

      </section>

      {/* ERREURS GÉNÉRALES */}
      {erreur && (
        <div
          className="dashboard-error"
          role="alert"
        >
          <AlertCircle size={20} />
          <span>{erreur}</span>

          <button
            type="button"
            onClick={chargerBassins}
          >
            Réessayer
          </button>
        </div>
      )}

      {/* LISTE DES BASSINS */}
      <section className="dashboard-section">
        <div className="section-heading">
          <div>
            <span className="section-eyebrow">
              INFRASTRUCTURE
            </span>

            <h2>Mes bassins</h2>

            <p>
              Sélectionne un bassin pour afficher
              ses mesures en temps réel.
            </p>
          </div>

          <span className="section-count">
            {bassins.length} bassin(s)
          </span>
        </div>

        {chargement && bassins.length === 0 ? (
          <div className="dashboard-empty">
            <RefreshCw
              size={25}
              className="rotation"
            />
            <p>Chargement des bassins...</p>
          </div>
        ) : bassins.length === 0 ? (
          <div className="dashboard-empty">
            <Waves size={36} />
            <h3>Aucun bassin enregistré</h3>
            <p>
              Les bassins ajoutés à PostgreSQL
              apparaîtront ici.
            </p>
          </div>
        ) : (
          <div className="bassins-grid">
            {bassins.map((bassin) => {
              const selectionne =
                bassin.id === bassinSelectionneId;

              return (
                <button
                  type="button"
                  key={bassin.id}
                  className={
                    `bassin-card bassin-card-button ` +
                    (selectionne
                      ? "bassin-card-selectionne"
                      : "")
                  }
                  aria-pressed={selectionne}
                  onClick={() =>
                    setBassinSelectionneId(bassin.id)
                  }
                >
                  <div className="bassin-card-top">
                    <div className="bassin-icon">
                      <Waves size={24} />
                    </div>

                    <span className="bassin-code">
                      {bassin.code}
                    </span>
                  </div>

                  <h3>
                    {bassin.nom || "Bassin sans nom"}
                  </h3>

                  <p className="bassin-description">
                    Installation aquacole
                  </p>

                  <div className="bassin-info">
                    <div className="bassin-info-icon">
                      <Droplets size={19} />
                    </div>

                    <div>
                      <span>Capacité du bassin</span>

                      <strong>
                        {bassin.capacite_litres == null
                          ? "Non renseignée"
                          : `${formaterVolume(
                              Number(
                                bassin.capacite_litres
                              )
                            )} litres`}
                      </strong>
                    </div>

                    <ArrowUpRight
                      size={17}
                      className="bassin-arrow"
                    />
                  </div>

                  {selectionne && (
                    <div className="bassin-selection-indicateur">
                      <CheckCircle2 size={15} />
                      Bassin sélectionné
                    </div>
                  )}
                </button>
              );
            })}
          </div>
        )}
      </section>

      {/* SUPERVISION DES MESURES — JOUR 8 */}
      {bassinSelectionne && (
        <section className="dashboard-section">

          <div className="section-heading">
            <div>
              <span className="section-eyebrow">
                QUALITÉ DE L'EAU
              </span>

              <h2>
                Supervision — {bassinSelectionne.nom}
              </h2>

              <p>
                Bassin {bassinSelectionne.code}
                {" • "}
                Actualisation toutes les 5 secondes
              </p>
            </div>

            <span className="section-count">
              <Activity size={14} />
              Supervision IoT
            </span>
          </div>

          {erreurMesures && (
            <div
              className="dashboard-error"
              role="alert"
            >
              <AlertCircle size={20} />
              <span>{erreurMesures}</span>
            </div>
          )}

          {chargementMesures && (
            <p className="supervision-message">
              Chargement de la supervision...
            </p>
          )}

          {!chargementMesures &&
            !derniereMesure &&
            !erreurMesures && (
              <div className="dashboard-empty">
                <Database size={30} />

                <h3>Aucune mesure reçue</h3>

                <p>
                  Démarre le simulateur ou connecte
                  ton ESP32 pour alimenter ce bassin.
                </p>
              </div>
            )}

          {derniereMesure && (
            <>
              {/* FRAÎCHEUR DES DONNÉES */}
              <div
                className={
                  `supervision-fraicheur ` +
                  (mesureAncienne
                    ? "ancienne"
                    : "recente")
                }
              >
                <Clock3 size={18} />

                <span>
                  Dernière mesure :
                  {" "}
                  {formaterDate(
                    derniereMesure.measure_at
                  )}

                  {mesureAncienne
                    ? " — Données anciennes"
                    : " — Données récentes"}
                </span>
              </div>

              {/* CARTES DES PARAMÈTRES */}
              <div className="mesures-grid">
                <CarteParametre
                  titre="Température"
                  valeur={
                    derniereMesure.temperature_c
                  }
                  unite="°C"
                  parametre="temperature_c"
                  Icone={Thermometer}
                />

                <CarteParametre
                  titre="pH de l'eau"
                  valeur={derniereMesure.ph}
                  unite=""
                  parametre="ph"
                  Icone={Droplets}
                />

                <CarteParametre
                  titre="Oxygène dissous"
                  valeur={
                    derniereMesure
                      .oxygene_dissous_mg_l
                  }
                  unite="mg/L"
                  parametre="oxygene_dissous_mg_l"
                  Icone={Waves}
                />
              </div>

              {/* HISTORIQUE GRAPHIQUE */}
              <div className="supervision-panel">
                <div className="supervision-panel-heading">
                  <div>
                    <h3>Évolution des paramètres</h3>
                    <p>
                      Historique des
                      {" "}
                      {mesures.length}
                      {" "}
                      dernières mesures disponibles
                    </p>
                  </div>
                </div>

                <GraphiqueMesures
                  mesures={mesures}
                />
              </div>
            </>
          )}

          {/* ALERTES DU BASSIN SÉLECTIONNÉ */}
          <div className="supervision-panel">
            <div className="supervision-panel-heading">
              <div>
                <h3>
                  Alertes du bassin
                </h3>

                <p>
                  {alertesBassin.length}
                  {" "}
                  alerte(s) non résolue(s)
                </p>
              </div>
            </div>

            {alertesBassin.length === 0 ? (
              <p className="supervision-message">
                Aucune alerte non résolue à afficher.
              </p>
            ) : (
              <div className="supervision-alertes-liste">
                {alertesBassin.map((alerte) => (
                  <div
                    className="supervision-alerte"
                    key={alerte.id}
                  >
                    <AlertCircle size={19} />

                    <div>
                      <strong>
                        {alerte.niveau}
                        {" — "}
                        {alerte.parametre}
                      </strong>

                      <p>{alerte.message}</p>

                      <small>
                        Statut : {alerte.statut}
                      </small>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {derniereMajMesures && (
            <p className="supervision-actualisation">
              Dernière synchronisation :
              {" "}
              {formaterDate(
                derniereMajMesures
              )}
            </p>
          )}
        </section>
      )}

      {/* ALERTES GÉNÉRALES EXISTANTES */}
      <section className="dashboard-section alertes-section">
        <div className="section-heading">
          <div>
            <span className="section-eyebrow">
              SURVEILLANCE
            </span>

            <h2>Alertes et anomalies</h2>

            <p>
              Vue globale des anomalies de
              qualité de l'eau.
            </p>
          </div>
        </div>

        <div className="alertes-container">
          <AlertesDashboard />
        </div>
      </section>

    </main>
  );
}

export default Dashboard;
