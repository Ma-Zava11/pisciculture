
// Axios est utilisé pour communiquer avec FastAPI.
import axios from "axios";

// Adresse de base de notre API locale.
const api = axios.create({
  baseURL: "http://127.0.0.1:8000/api/v1",
  timeout: 10000,
});

// Fonction qui récupère la liste des bassins.
export async function getBassins() {
  const response = await api.get("/bassins");

  // response.data contient les données JSON retournées.
  return response.data;
}

export default api;


/*
 * JOUR 8 — Supervision de la qualité de l'eau.
 *
 * Ces fonctions utilisent fetch pour éviter de dépendre
 * de la configuration Axios déjà présente dans ton projet.
 *
 * Si tu disposes d'une URL d'API centralisée, tu pourras
 * remplacer cette constante par ta configuration existante.
 */

const SUPERVISION_API_URL =
  "http://127.0.0.1:8000/api/v1";

/**
 * Récupérer les dernières mesures d'un bassin.
 *
 * @param {number} bassinId - Identifiant numérique du bassin.
 * @param {number} limite - Nombre maximal de mesures.
 * @param {AbortSignal} signal - Permet d'annuler une requête.
 */
export async function getMesuresBassin(
  bassinId,
  limite = 100,
  signal
) {
  const url =
    `${SUPERVISION_API_URL}/bassins/${bassinId}/mesures` +
    `?limite=${limite}`;

  const reponse = await fetch(url, { signal });

  if (!reponse.ok) {
    throw new Error(
      `Erreur HTTP ${reponse.status} : chargement des mesures`
    );
  }

  const donnees = await reponse.json();

  if (!Array.isArray(donnees)) {
    throw new Error("Format des mesures invalide.");
  }

  return donnees;
}

/**
 * Récupérer les alertes d'un bassin.
 * Nécessite la route créée au Jour 7.
 */
export async function getAlertesParBassin(
  bassinId,
  signal
) {
  const reponse = await fetch(
    `${SUPERVISION_API_URL}/bassins/${bassinId}/alertes`,
    { signal }
  );

  if (!reponse.ok) {
    throw new Error(
      `Erreur HTTP ${reponse.status} : chargement des alertes`
    );
  }

  const donnees = await reponse.json();

  if (!Array.isArray(donnees)) {
    throw new Error("Format des alertes invalide.");
  }

  return donnees;
}

// Adresse du backend FastAPI.
const API_SEUILS_URL = "http://127.0.0.1:8000/api/v1";


/**
 * Récupérer tous les seuils enregistrés.
 *
 * Endpoint :
 * GET /api/v1/seuils
 */
export async function getSeuils() {

  const response = await fetch(
    `${API_SEUILS_URL}/seuils`
  );

  // Vérifier que le backend a répondu correctement.
  if (!response.ok) {
    throw new Error(
      `Impossible de récupérer les seuils (HTTP ${response.status})`
    );
  }

  // Convertir la réponse JSON en tableau JavaScript.
  const data = await response.json();

  // Vérifier que le backend retourne un tableau.
  if (!Array.isArray(data)) {
    throw new Error(
      "Format de réponse invalide : tableau attendu."
    );
  }

  return data;
}


/**
 * Modifier les seuils existants.
 *
 * Endpoint :
 * PUT /api/v1/seuils/{id}
 *
 * @param {number} seuilId - Identifiant du seuil.
 * @param {object} donnees - Nouvelles limites.
 */
export async function updateSeuil(seuilId, donnees) {

  const response = await fetch(
    `${API_SEUILS_URL}/seuils/${seuilId}`,
    {
      method: "PUT",

      headers: {
        "Content-Type": "application/json"
      },

      body: JSON.stringify(donnees)
    }
  );

  // Traiter les erreurs HTTP.
  if (!response.ok) {

    const erreur = await response.json().catch(
      () => ({})
    );

    throw new Error(
      typeof erreur.detail === "string"
        ? erreur.detail
        : `Erreur lors de la modification (HTTP ${response.status})`
    );
  }

  // Retourner le seuil mis à jour.
  return await response.json();
}

/**
 * JOUR 10 — SERVICES D'HISTORIQUE
 *
 * Toutes les fonctions utilisent les nouvelles routes
 * FastAPI ajoutées dans app/api/routes.py.
 */

const HISTORIQUE_API = "http://127.0.0.1:8000/api/v1";

/**
 * Construire les paramètres de filtrage communs.
 *
 * Les dates sont envoyées au format ISO 8601 UTC.
 */
function creerParametresHistorique(filtres) {
  const params = new URLSearchParams();

  params.set("bassin_id", String(filtres.bassinId));

  if (filtres.dateDebut) {
    params.set("date_debut", filtres.dateDebut);
  }

  if (filtres.dateFin) {
    params.set("date_fin", filtres.dateFin);
  }

  return params;
}

/**
 * Effectuer une requête GET et vérifier le statut HTTP.
 */
async function getHistoriqueJSON(chemin, params, signal) {
  const reponse = await fetch(
    `${HISTORIQUE_API}${chemin}?${params.toString()}`,
    { signal }
  );

  if (!reponse.ok) {
    let detail = `Erreur HTTP ${reponse.status}`;

    try {
      const erreur = await reponse.json();

      if (typeof erreur.detail === "string") {
        detail = erreur.detail;
      }
    } catch {
      // Conserver le message HTTP par défaut.
    }

    throw new Error(detail);
  }

  return reponse.json();
}

/**
 * Charger une page de mesures.
 */
export async function getHistoriqueMesures(
  filtres,
  signal
) {
  const params = creerParametresHistorique(filtres);

  params.set("limite", String(filtres.limite ?? 50));
  params.set("offset", String(filtres.offset ?? 0));

  return getHistoriqueJSON(
    "/historique/mesures",
    params,
    signal
  );
}

/**
 * Calculer les statistiques sur toute la période.
 */
export async function getStatistiquesHistorique(
  filtres,
  signal
) {
  return getHistoriqueJSON(
    "/historique/statistiques",
    creerParametresHistorique(filtres),
    signal
  );
}

/**
 * Récupérer les périodes de dépassement.
 */
export async function getAnomaliesHistorique(
  filtres,
  signal
) {
  return getHistoriqueJSON(
    "/historique/anomalies",
    creerParametresHistorique(filtres),
    signal
  );
}

/**
 * Télécharger un export CSV ou XLSX.
 *
 * Le téléchargement passe par fetch pour permettre
 * l'affichage d'une erreur si le serveur refuse l'export.
 */
export async function exporterHistorique(
  filtres,
  format
) {
  const params = creerParametresHistorique(filtres);
  params.set("format", format);

  const reponse = await fetch(
    `${HISTORIQUE_API}/historique/export?${params.toString()}`
  );

  if (!reponse.ok) {
    let detail = `Export impossible (HTTP ${reponse.status})`;

    try {
      const erreur = await reponse.json();

      if (typeof erreur.detail === "string") {
        detail = erreur.detail;
      }
    } catch {
      // Garder le message générique.
    }

    throw new Error(detail);
  }

  const fichier = await reponse.blob();

  // Créer temporairement un lien de téléchargement.
  const url = URL.createObjectURL(fichier);
  const lien = document.createElement("a");

  lien.href = url;
  lien.download = (
    `historique_bassin_${filtres.bassinId}.${format}`
  );

  document.body.appendChild(lien);
  lien.click();
  lien.remove();

  URL.revokeObjectURL(url);
}

/**
 * ============================================================
 * JOUR 11 — SERVICES DE SUPERVISION DES ALERTES
 * ============================================================
 *
 * Réutilise les routes FastAPI existantes.
 * Les requêtes peuvent être annulées avec AbortController.
 */

const ALERTES_API_URL = "http://127.0.0.1:8000/api/v1";

/**
 * Exécuter une requête HTTP et retourner du JSON.
 */
async function requeteAlertes(
  chemin,
  options = {}
) {
  const reponse = await fetch(
    `${ALERTES_API_URL}${chemin}`,
    options
  );

  if (!reponse.ok) {
    let message = `Erreur HTTP ${reponse.status}`;

    try {
      const erreur = await reponse.json();

      if (typeof erreur.detail === "string") {
        message = erreur.detail;
      }
    } catch {
      // Garder le message HTTP générique.
    }

    throw new Error(message);
  }

  return reponse.json();
}

/**
 * Récupérer les dernières alertes.
 *
 * @param {number} limite - Nombre maximum d'alertes.
 * @param {AbortSignal} signal - Annulation facultative.
 */
export async function getAlertesSupervision(
  limite = 100,
  signal
) {
  return requeteAlertes(
    `/alertes?limite=${limite}`,
    { signal }
  );
}

/**
 * Récupérer le résumé des alertes non résolues.
 */
export async function getResumeAlertesSupervision(signal) {
  return requeteAlertes(
    "/alertes/resume",
    { signal }
  );
}

/**
 * Récupérer toutes les alertes encore ouvertes.
 */
export async function getAlertesOuvertesSupervision(signal) {
  return requeteAlertes(
    "/alertes/actives",
    { signal }
  );
}

/**
 * Acquitter une alerte active.
 *
 * Une alerte acquittée reste ouverte tant que
 * la situation anormale n'est pas résolue.
 */
export async function acquitterAlerteSupervision(alerteId) {
  return requeteAlertes(
    `/alertes/${alerteId}/acquitter`,
    {
      method: "PATCH"
    }
  );
}

/**
 * ============================================================
 * JOUR 13 — SERVICES DES APPAREILS IOT
 * ============================================================
 */

const APPAREILS_API_URL = "http://127.0.0.1:8000/api/v1";

/**
 * Exécuter une requête vers le backend.
 */
async function requeteAppareils(
  chemin,
  options = {}
) {
  const reponse = await fetch(
    `${APPAREILS_API_URL}${chemin}`,
    options
  );

  if (!reponse.ok) {
    let message = `Erreur HTTP ${reponse.status}`;

    try {
      const erreur = await reponse.json();

      if (typeof erreur.detail === "string") {
        message = erreur.detail;
      }
    } catch {
      // Conserver le message générique.
    }

    throw new Error(message);
  }

  return reponse.json();
}

/**
 * Récupérer la liste des appareils.
 */
export async function getAppareils(bassinId = null) {
  const params = new URLSearchParams();

  if (bassinId !== null && bassinId !== "") {
    params.set("bassin_id", bassinId);
  }

  const query = params.toString();

  return requeteAppareils(
    `/appareils${query ? `?${query}` : ""}`
  );
}

/**
 * Récupérer les indicateurs des appareils.
 */
export async function getResumeAppareils() {
  return requeteAppareils(
    "/appareils-supervision/resume"
  );
}

/**
 * Créer un nouvel appareil.
 */
export async function creerAppareil(donnees) {
  return requeteAppareils("/appareils", {
    method: "POST",

    headers: {
      "Content-Type": "application/json"
    },

    body: JSON.stringify(donnees)
  });
}

/**
 * Modifier un appareil existant.
 */
export async function modifierAppareil(id, donnees) {
  return requeteAppareils(`/appareils/${id}`, {
    method: "PATCH",

    headers: {
      "Content-Type": "application/json"
    },

    body: JSON.stringify(donnees)
  });
}

