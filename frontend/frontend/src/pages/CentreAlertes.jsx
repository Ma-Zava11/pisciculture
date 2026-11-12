
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  BellRing,
  AlertTriangle,
  CheckCircle2,
  RefreshCw,
  Volume2,
  VolumeX,
  Bell,
  BellOff,
  ShieldCheck
} from "lucide-react";

import {
  getAlertesSupervision,
  getResumeAlertesSupervision,
  acquitterAlerteSupervision
} from "../services/api";

import "./CentreAlertes.css";

const INTERVALLE_ACTUALISATION = 10000;

/**
 * ============================================================
 * JOUR 11 — CENTRE D'ALERTES
 * ============================================================
 *
 * Fonctionnalités :
 * - Actualisation automatique toutes les 10 secondes.
 * - Statistiques des alertes ouvertes.
 * - Filtrage par statut.
 * - Acquittement des alertes actives.
 * - Notifications du navigateur facultatives.
 * - Signal sonore facultatif.
 *
 * Les alertes sont enregistrées par le backend.
 * Le frontend ne modifie pas les règles métier.
 */

/**
 * Formater une date ISO en date locale.
 */
function formaterDate(date) {
  if (!date) return "Date inconnue";

  const valeur = new Date(date);

  if (Number.isNaN(valeur.getTime())) {
    return "Date inconnue";
  }

  return valeur.toLocaleString("fr-FR");
}

/**
 * Convertir une valeur de statut en texte.
 */
function statutAlerte(alerte) {
  return String(alerte.statut ?? "").toUpperCase();
}

/**
 * Normaliser le niveau d'une alerte.
 */
function niveauAlerte(alerte) {
  return String(alerte.niveau ?? "").toUpperCase();
}

/**
 * Créer un signal sonore bref.
 *
 * Le son est généré localement avec Web Audio.
 * Aucun fichier audio externe n'est nécessaire.
 */
function jouerSignalSonore() {
  const AudioContextClass =
    window.AudioContext || window.webkitAudioContext;

  if (!AudioContextClass) return;

  const contexte = new AudioContextClass();

  const oscillateur = contexte.createOscillator();
  const gain = contexte.createGain();

  oscillateur.type = "sine";
  oscillateur.frequency.value = 880;

  gain.gain.setValueAtTime(
    0.0001,
    contexte.currentTime
  );

  gain.gain.exponentialRampToValueAtTime(
    0.12,
    contexte.currentTime + 0.02
  );

  gain.gain.exponentialRampToValueAtTime(
    0.0001,
    contexte.currentTime + 0.22
  );

  oscillateur.connect(gain);
  gain.connect(contexte.destination);

  oscillateur.start();
  oscillateur.stop(contexte.currentTime + 0.23);

  oscillateur.onended = () => {
    contexte.close().catch(() => {});
  };
}

export default function CentreAlertes() {
  // ----------------------------------------------------------
  // ÉTATS DE LA PAGE
  // ----------------------------------------------------------

  const [alertes, setAlertes] = useState([]);

  const [resume, setResume] = useState({
    total: 0,
    avertissements: 0,
    critiques: 0,
    actives: 0,
    acquittees: 0
  });

  const [filtre, setFiltre] = useState("OUVERTES");

  const [chargement, setChargement] = useState(true);
  const [erreur, setErreur] = useState("");

  const [derniereActualisation, setDerniereActualisation] =
    useState(null);

  const [alerteEnCours, setAlerteEnCours] = useState(null);

  const [sonActif, setSonActif] = useState(false);
  const [notificationsActives, setNotificationsActives] =
    useState(false);

  // Ensemble des alertes déjà rencontrées.
  const alertesConnues = useRef(new Set());

  // Indique si la première récupération a eu lieu.
  const initialisationTerminee = useRef(false);

  // Éviter plusieurs requêtes simultanées.
  const requeteEnCours = useRef(false);

  // Conserver les préférences courantes pour le polling.
  const preferencesRef = useRef({
    sonActif: false,
    notificationsActives: false
  });

  useEffect(() => {
    preferencesRef.current = {
      sonActif,
      notificationsActives
    };
  }, [sonActif, notificationsActives]);

  /**
   * Charger les alertes et le résumé.
   */
  const chargerAlertes = useCallback(async () => {
    if (requeteEnCours.current) return;

    requeteEnCours.current = true;

    try {
      const [liste, statistiques] = await Promise.all([
        getAlertesSupervision(100),
        getResumeAlertesSupervision()
      ]);

      const nouvellesAlertes = [];

      // Détecter uniquement les alertes inconnues.
      for (const alerte of liste) {
        const id = String(alerte.id);

        if (
          initialisationTerminee.current &&
          !alertesConnues.current.has(id) &&
          statutAlerte(alerte) === "ACTIVE"
        ) {
          nouvellesAlertes.push(alerte);
        }

        alertesConnues.current.add(id);
      }

      // Ne pas déclencher de notification pour
      // les alertes déjà présentes au premier chargement.
      initialisationTerminee.current = true;

      setAlertes(liste);
      setResume(statistiques);
      setDerniereActualisation(new Date());
      setErreur("");

      // Notifications facultatives.
      if (nouvellesAlertes.length > 0) {
        const preferences = preferencesRef.current;

        if (preferences.sonActif) {
          try {
            jouerSignalSonore();
          } catch {
            // Ne pas bloquer la surveillance.
          }
        }

        if (
          preferences.notificationsActives &&
          "Notification" in window &&
          Notification.permission === "granted"
        ) {
          const premiere = nouvellesAlertes[0];

          new Notification(
            "Nouvelle alerte — AquaSmart",
            {
              body:
                `${nouvellesAlertes.length} nouvelle(s) alerte(s). ` +
                `Niveau : ${premiere.niveau}.`
            }
          );
        }
      }

    } catch (e) {
      setErreur(e.message);
    } finally {
      setChargement(false);
      requeteEnCours.current = false;
    }
  }, []);

  /**
   * Démarrer le polling automatique.
   *
   * Nettoyer l'intervalle lorsque la page est quittée.
   */
  useEffect(() => {
    chargerAlertes();

    const intervalle = setInterval(() => {
      chargerAlertes();
    }, INTERVALLE_ACTUALISATION);

    return () => {
      clearInterval(intervalle);
    };
  }, [chargerAlertes]);

  /**
   * Demander l'autorisation pour les notifications.
   *
   * Cette opération doit être déclenchée
   * par une interaction utilisateur.
   */
  async function activerNotifications() {
    if (!("Notification" in window)) {
      setErreur(
        "Ce navigateur ne prend pas en charge les notifications."
      );
      return;
    }

    if (!window.isSecureContext) {
      setErreur(
        "Les notifications nécessitent HTTPS ou localhost."
      );
      return;
    }

    if (Notification.permission === "denied") {
      setErreur(
        "Les notifications sont bloquées dans les paramètres du navigateur."
      );
      return;
    }

    const autorisation =
      await Notification.requestPermission();

    setNotificationsActives(
      autorisation === "granted"
    );
  }

  /**
   * Acquitter une alerte.
   */
  async function acquitter(alerteId) {
    setAlerteEnCours(alerteId);
    setErreur("");

    try {
      await acquitterAlerteSupervision(alerteId);

      // Recharger immédiatement les données.
      await chargerAlertes();

    } catch (e) {
      setErreur(e.message);
    } finally {
      setAlerteEnCours(null);
    }
  }

  /**
   * Filtrer les alertes selon leur statut.
   */
  const alertesFiltrees = useMemo(() => {
    if (filtre === "TOUTES") {
      return alertes;
    }

    if (filtre === "OUVERTES") {
      return alertes.filter((alerte) =>
        ["ACTIVE", "ACQUITTEE"].includes(
          statutAlerte(alerte)
        )
      );
    }

    return alertes.filter(
      (alerte) => statutAlerte(alerte) === filtre
    );
  }, [alertes, filtre]);

  return (
    <div className="pf-alertes-page">

      {/* EN-TÊTE */}

      <header className="pf-alertes-header">
        <div>
          <h1>
            <BellRing size={27} />
            Centre d'alertes
          </h1>

          <p>
            Surveillance des anomalies de qualité de l'eau
            dans les bassins.
          </p>
        </div>

        <button
          type="button"
          className="pf-alertes-btn"
          onClick={chargerAlertes}
        >
          <RefreshCw size={17} />
          Actualiser
        </button>
      </header>

      {/* INDICATEURS */}

      <section className="pf-alertes-stats">
        <article className="pf-alertes-stat">
          <span>Alertes ouvertes</span>
          <strong>{resume.total}</strong>
          <small>Actives et acquittées</small>
        </article>

        <article className="pf-alertes-stat critique">
          <span>Critiques</span>
          <strong>{resume.critiques}</strong>
          <small>Attention prioritaire</small>
        </article>

        <article className="pf-alertes-stat avertissement">
          <span>Avertissements</span>
          <strong>{resume.avertissements}</strong>
          <small>Surveillance nécessaire</small>
        </article>

        <article className="pf-alertes-stat">
          <span>Acquittées</span>
          <strong>{resume.acquittees}</strong>
          <small>Prises en compte</small>
        </article>
      </section>

      {/* PARAMÈTRES DES NOTIFICATIONS */}

      <section className="pf-alertes-panel">
        <div className="pf-alertes-panel-heading">
          <div>
            <h2>Notifications</h2>
            <p>
              Actualisation automatique toutes les 10 secondes.
            </p>
          </div>

          <span className="pf-alertes-live">
            <span />
            Surveillance active
          </span>
        </div>

        <div className="pf-alertes-options">
          <button
            type="button"
            className="pf-alertes-btn"
            onClick={() => {
              if (!sonActif) {
                // Le clic utilisateur autorise
                // généralement l'initialisation audio.
                try {
                  jouerSignalSonore();
                } catch {}
              }

              setSonActif(!sonActif);
            }}
          >
            {sonActif ? (
              <Volume2 size={17} />
            ) : (
              <VolumeX size={17} />
            )}

            {sonActif
              ? "Désactiver le son"
              : "Activer le son"}
          </button>

          <button
            type="button"
            className="pf-alertes-btn"
            onClick={() => {
              if (notificationsActives) {
                setNotificationsActives(false);
              } else {
                activerNotifications();
              }
            }}
          >
            {notificationsActives ? (
              <Bell size={17} />
            ) : (
              <BellOff size={17} />
            )}

            {notificationsActives
              ? "Désactiver les notifications"
              : "Activer les notifications"}
          </button>
        </div>

        <small>
          Dernière actualisation :{" "}
          {derniereActualisation
            ? derniereActualisation.toLocaleTimeString("fr-FR")
            : "En attente"}
        </small>
      </section>

      {/* AFFICHER LES ERREURS */}

      {erreur && (
        <div className="pf-alertes-erreur">
          <AlertTriangle size={18} />
          {erreur}
        </div>
      )}

      {/* LISTE DES ALERTES */}

      <section className="pf-alertes-panel">
        <div className="pf-alertes-panel-heading">
          <div>
            <h2>Historique des alertes</h2>
            <p>
              Consulter les alertes et acquitter celles
              nécessitant une intervention.
            </p>
          </div>

          <select
            className="pf-alertes-select"
            value={filtre}
            onChange={(e) => setFiltre(e.target.value)}
          >
            <option value="OUVERTES">Ouvertes</option>
            <option value="TOUTES">Toutes</option>
            <option value="ACTIVE">Actives</option>
            <option value="ACQUITTEE">Acquittées</option>
            <option value="RESOLUE">Résolues</option>
          </select>
        </div>

        {chargement && (
          <p>Chargement des alertes...</p>
        )}

        {!chargement && alertesFiltrees.length === 0 && (
          <div className="pf-alertes-vide">
            <ShieldCheck size={36} />
            <strong>Aucune alerte à afficher</strong>
            <p>
              Aucune alerte ne correspond au filtre sélectionné.
            </p>
          </div>
        )}

        <div className="pf-alertes-liste">
          {alertesFiltrees.map((alerte) => {
            const niveau = niveauAlerte(alerte);
            const statut = statutAlerte(alerte);

            return (
              <article
                key={alerte.id}
                className={`pf-alerte-item ${
                  niveau === "CRITIQUE"
                    ? "pf-alerte-item--critique"
                    : "pf-alerte-item--avertissement"
                }`}
              >
                <div className="pf-alerte-icone">
                  {niveau === "CRITIQUE" ? (
                    <AlertTriangle size={22} />
                  ) : (
                    <BellRing size={22} />
                  )}
                </div>

                <div className="pf-alerte-contenu">
                  <div className="pf-alerte-titre">
                    <strong>
                      {alerte.parametre ??
                        alerte.type_alerte ??
                        "Anomalie détectée"}
                    </strong>

                    <span className={`pf-alerte-badge ${
                      niveau === "CRITIQUE"
                        ? "critique"
                        : "avertissement"
                    }`}>
                      {niveau || "INCONNU"}
                    </span>
                  </div>

                  <p>
                    {alerte.message ??
                      alerte.description ??
                      "Un paramètre de qualité de l'eau nécessite une vérification."}
                  </p>

                  <div className="pf-alerte-meta">
                    <span>
                      Bassin ID : {alerte.bassin_id ?? "—"}
                    </span>

                    <span>
                      {formaterDate(
                        alerte.created_at ??
                        alerte.detected_at
                      )}
                    </span>

                    <span>
                      Statut : {statut || "INCONNU"}
                    </span>
                  </div>
                </div>

                <div className="pf-alerte-actions">
                  {statut === "ACTIVE" ? (
                    <button
                      type="button"
                      className="pf-alertes-btn primaire"
                      disabled={alerteEnCours === alerte.id}
                      onClick={() => acquitter(alerte.id)}
                    >
                      <CheckCircle2 size={16} />
                      {alerteEnCours === alerte.id
                        ? "Traitement..."
                        : "Acquitter"}
                    </button>
                  ) : (
                    <span className="pf-alerte-statut">
                      {statut}
                    </span>
                  )}
                </div>
              </article>
            );
          })}
        </div>
      </section>
    </div>
  );
}
