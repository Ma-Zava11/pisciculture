
import {
  useCallback,
  useEffect,
  useState
} from "react";

import {
  Cpu,
  Wifi,
  WifiOff,
  Plus,
  RefreshCw,
  Power,
  Activity,
  AlertTriangle
} from "lucide-react";

import {
  getBassins,
  getAppareils,
  getResumeAppareils,
  creerAppareil,
  modifierAppareil
} from "../services/api";

import "./GestionAppareils.css";

const INTERVALLE = 10000;

/**
 * Formater une date de communication.
 */
function formaterDate(date) {
  if (!date) return "Jamais";

  const valeur = new Date(date);

  if (Number.isNaN(valeur.getTime())) {
    return "Date invalide";
  }

  return valeur.toLocaleString("fr-FR");
}

/**
 * Afficher un état compréhensible.
 */
function libelleEtat(etat) {
  const valeurs = {
    EN_LIGNE: "En ligne",
    HORS_LIGNE: "Hors ligne",
    SANS_DONNEES: "Sans données",
    DESACTIVE: "Désactivé"
  };

  return valeurs[etat] ?? etat;
}

/**
 * PAGE PRINCIPALE — GESTION DES APPAREILS
 */
export default function GestionAppareils() {

  // --------------------------------------------------------
  // DONNÉES
  // --------------------------------------------------------

  const [appareils, setAppareils] = useState([]);
  const [bassins, setBassins] = useState([]);

  const [resume, setResume] = useState({
    total: 0,
    en_ligne: 0,
    hors_ligne: 0,
    sans_donnees: 0,
    desactives: 0
  });

  // --------------------------------------------------------
  // FORMULAIRE
  // --------------------------------------------------------

  const [identifiant, setIdentifiant] = useState("");
  const [bassinId, setBassinId] = useState("");

  const [filtreBassin, setFiltreBassin] = useState("");

  // --------------------------------------------------------
  // ÉTATS DE L'INTERFACE
  // --------------------------------------------------------

  const [chargement, setChargement] = useState(true);
  const [enregistrement, setEnregistrement] =
    useState(false);

  const [actionEnCours, setActionEnCours] =
    useState(null);

  const [erreur, setErreur] = useState("");
  const [succes, setSucces] = useState("");

  /**
   * Charger les appareils et leurs statistiques.
   */
  const chargerDonnees = useCallback(async () => {
    try {
      const [liste, statistiques] = await Promise.all([
        getAppareils(),
        getResumeAppareils()
      ]);

      setAppareils(liste);
      setResume(statistiques);
      setErreur("");

    } catch (e) {
      setErreur(e.message);
    } finally {
      setChargement(false);
    }
  }, []);

  /**
   * Charger les bassins disponibles.
   */
  useEffect(() => {
    let actif = true;

    async function chargerBassins() {
      try {
        const liste = await getBassins();

        if (!actif) return;

        setBassins(liste);

        if (liste.length > 0) {
          setBassinId(String(liste[0].id));
        }

      } catch (e) {
        if (actif) setErreur(e.message);
      }
    }

    chargerBassins();

    return () => {
      actif = false;
    };
  }, []);

  /**
   * Actualiser les appareils toutes les 10 secondes.
   */
  useEffect(() => {
    chargerDonnees();

    const intervalle = setInterval(
      chargerDonnees,
      INTERVALLE
    );

    return () => clearInterval(intervalle);
  }, [chargerDonnees]);

  /**
   * Enregistrer un nouvel appareil.
   */
  async function ajouterAppareil(event) {
    event.preventDefault();

    setErreur("");
    setSucces("");

    if (!identifiant.trim() || !bassinId) {
      setErreur(
        "Renseigne l'identifiant et le bassin."
      );
      return;
    }

    setEnregistrement(true);

    try {
      await creerAppareil({
        identifiant: identifiant.trim(),
        bassin_id: Number(bassinId)
      });

      setIdentifiant("");

      setSucces(
        "Appareil enregistré avec succès."
      );

      await chargerDonnees();

    } catch (e) {
      setErreur(e.message);
    } finally {
      setEnregistrement(false);
    }
  }

  /**
   * Activer ou désactiver un appareil.
   */
  async function basculerStatut(appareil) {
    const nouveauStatut =
      appareil.statut === "ACTIF"
        ? "INACTIF"
        : "ACTIF";

    setActionEnCours(appareil.id);
    setErreur("");
    setSucces("");

    try {
      await modifierAppareil(appareil.id, {
        statut: nouveauStatut
      });

      setSucces(
        `Appareil ${appareil.identifiant} mis à jour.`
      );

      await chargerDonnees();

    } catch (e) {
      setErreur(e.message);
    } finally {
      setActionEnCours(null);
    }
  }

  /**
   * Modifier l'affectation d'un appareil.
   */
  async function changerBassinAppareil(
    appareil,
    nouveauBassinId
  ) {
    setActionEnCours(appareil.id);
    setErreur("");
    setSucces("");

    try {
      await modifierAppareil(appareil.id, {
        bassin_id: Number(nouveauBassinId)
      });

      setSucces(
        "Affectation du bassin mise à jour."
      );

      await chargerDonnees();

    } catch (e) {
      setErreur(e.message);
    } finally {
      setActionEnCours(null);
    }
  }

  /**
   * Filtrer les appareils localement.
   */
  const appareilsFiltres = appareils.filter(
    (appareil) =>
      !filtreBassin ||
      String(appareil.bassin_id) === filtreBassin
  );

  return (
    <main className="pf-devices-page">

      {/* EN-TÊTE */}

      <header className="pf-devices-header">
        <div>
          <h1>
            <Cpu size={28} />
            Gestion des appareils IoT
          </h1>

          <p>
            Configuration et surveillance des ESP32
            connectés aux bassins.
          </p>
        </div>

        <button
          className="pf-devices-btn"
          type="button"
          onClick={chargerDonnees}
        >
          <RefreshCw size={16} />
          Actualiser
        </button>
      </header>

      {/* STATISTIQUES */}

      <section className="pf-devices-stats">
        {[
          ["Total appareils", resume.total],
          ["En ligne", resume.en_ligne],
          ["Hors ligne", resume.hors_ligne],
          ["Désactivés", resume.desactives]
        ].map(([titre, valeur]) => (
          <article key={titre}>
            <span>{titre}</span>
            <strong>{valeur}</strong>
          </article>
        ))}
      </section>

      {/* MESSAGES */}

      {erreur && (
        <div className="pf-devices-message erreur">
          <AlertTriangle size={17} />
          {erreur}
        </div>
      )}

      {succes && (
        <div className="pf-devices-message succes">
          {succes}
        </div>
      )}

      {/* FORMULAIRE DE CRÉATION */}

      <section className="pf-devices-panel">
        <h2>
          <Plus size={20} />
          Ajouter un appareil
        </h2>

        <form
          className="pf-devices-form"
          onSubmit={ajouterAppareil}
        >
          <div>
            <label htmlFor="device-id">
              Identifiant
            </label>

            <input
              id="device-id"
              type="text"
              placeholder="ESP32-004"
              value={identifiant}
              onChange={(e) =>
                setIdentifiant(e.target.value)
              }
              minLength={3}
              maxLength={100}
              required
            />
          </div>

          <div>
            <label htmlFor="device-bassin">
              Bassin
            </label>

            <select
              id="device-bassin"
              value={bassinId}
              onChange={(e) =>
                setBassinId(e.target.value)
              }
              required
            >
              {bassins.map((bassin) => (
                <option
                  key={bassin.id}
                  value={bassin.id}
                >
                  {bassin.code} — {bassin.nom}
                </option>
              ))}
            </select>
          </div>

          <button
            type="submit"
            className="pf-devices-btn primaire"
            disabled={enregistrement || !bassinId}
          >
            <Plus size={16} />
            {enregistrement
              ? "Enregistrement..."
              : "Ajouter"}
          </button>
        </form>
      </section>

      {/* LISTE DES APPAREILS */}

      <section className="pf-devices-panel">
        <div className="pf-devices-section-header">
          <h2>
            <Activity size={20} />
            Appareils enregistrés
          </h2>

          <select
            value={filtreBassin}
            onChange={(e) =>
              setFiltreBassin(e.target.value)
            }
            aria-label="Filtrer par bassin"
          >
            <option value="">
              Tous les bassins
            </option>

            {bassins.map((bassin) => (
              <option
                key={bassin.id}
                value={bassin.id}
              >
                {bassin.code}
              </option>
            ))}
          </select>
        </div>

        {chargement && (
          <p>Chargement des appareils...</p>
        )}

        <div className="pf-devices-grid">
          {appareilsFiltres.map((appareil) => (
            <article
              className="pf-device-card"
              key={appareil.id}
            >
              <div className="pf-device-card-header">
                <div className="pf-device-identite">
                  <div className="pf-device-icon">
                    <Cpu size={22} />
                  </div>

                  <div>
                    <strong>
                      {appareil.identifiant}
                    </strong>

                    <small>
                      {appareil.bassin_code ?? "Sans bassin"}
                    </small>
                  </div>
                </div>

                <span
                  className={
                    "pf-device-badge " +
                    appareil.etat_connexion.toLowerCase()
                  }
                >
                  {appareil.etat_connexion === "EN_LIGNE" ? (
                    <Wifi size={13} />
                  ) : (
                    <WifiOff size={13} />
                  )}

                  {libelleEtat(
                    appareil.etat_connexion
                  )}
                </span>
              </div>

              <div className="pf-device-details">
                <div>
                  <span>Dernière communication</span>
                  <strong>
                    {formaterDate(
                      appareil.derniere_communication
                    )}
                  </strong>
                </div>

                <div>
                  <span>Statut administratif</span>
                  <strong>{appareil.statut}</strong>
                </div>
              </div>

              {/* MODIFICATION DU BASSIN */}

              <div className="pf-device-affectation">
                <label
                  htmlFor={`bassin-${appareil.id}`}
                >
                  Affectation
                </label>

                <select
                  id={`bassin-${appareil.id}`}
                  value={appareil.bassin_id ?? ""}
                  disabled={
                    actionEnCours === appareil.id
                  }
                  onChange={(e) =>
                    changerBassinAppareil(
                      appareil,
                      e.target.value
                    )
                  }
                >
                  {bassins.map((bassin) => (
                    <option
                      key={bassin.id}
                      value={bassin.id}
                    >
                      {bassin.code} — {bassin.nom}
                    </option>
                  ))}
                </select>
              </div>

              {/* ACTIVATION / DÉSACTIVATION */}

              <button
                type="button"
                className="pf-devices-btn"
                disabled={
                  actionEnCours === appareil.id
                }
                onClick={() =>
                  basculerStatut(appareil)
                }
              >
                <Power size={16} />

                {appareil.statut === "ACTIF"
                  ? "Désactiver"
                  : "Activer"}
              </button>
            </article>
          ))}
        </div>

        {!chargement &&
          appareilsFiltres.length === 0 && (
            <p>
              Aucun appareil trouvé pour ce filtre.
            </p>
          )}
      </section>
    </main>
  );
}
