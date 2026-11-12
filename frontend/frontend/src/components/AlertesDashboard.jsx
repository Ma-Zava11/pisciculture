
import { useCallback, useEffect, useState } from "react";
import "./AlertesDashboard.css";

// Adresse de ton API FastAPI.
// Si tu utilises déjà une instance Axios centralisée,
// nous pourrons ensuite remplacer ces appels fetch.
const API_BASE = "http://127.0.0.1:8000/api/v1";

export default function AlertesDashboard() {
  // Liste des alertes non résolues.
  const [alertes, setAlertes] = useState([]);

  // Statistiques renvoyées par le backend.
  const [resume, setResume] = useState(null);

  // État de chargement et messages d'erreur.
  const [chargement, setChargement] = useState(true);
  const [erreur, setErreur] = useState("");

  // Identifiant de l'alerte en cours d'acquittement.
  const [traitementId, setTraitementId] = useState(null);

  // Charger les alertes et leurs statistiques.
  const chargerAlertes = useCallback(async (signal) => {
    try {
      const [repAlertes, repResume] = await Promise.all([
        fetch(`${API_BASE}/alertes/actives`, { signal }),
        fetch(`${API_BASE}/alertes/resume`, { signal }),
      ]);

      if (!repAlertes.ok || !repResume.ok) {
        throw new Error("Impossible de récupérer les alertes.");
      }

      const [donneesAlertes, donneesResume] =
        await Promise.all([
          repAlertes.json(),
          repResume.json(),
        ]);

      if (signal?.aborted) return;

      setAlertes(donneesAlertes);
      setResume(donneesResume);
      setErreur("");
    } catch (error) {
      if (error.name === "AbortError") return;

      setErreur(error.message);
    } finally {
      if (!signal?.aborted) {
        setChargement(false);
      }
    }
  }, []);

  // Chargement initial et actualisation périodique.
  useEffect(() => {
    const controller = new AbortController();

    chargerAlertes(controller.signal);

    // Rafraîchir toutes les 10 secondes.
    const intervalle = setInterval(() => {
      chargerAlertes(controller.signal);
    }, 10000);

    return () => {
      clearInterval(intervalle);
      controller.abort();
    };
  }, [chargerAlertes]);

  // Acquitter une alerte sélectionnée.
  async function acquitterAlerte(id) {
    try {
      setTraitementId(id);

      const reponse = await fetch(
        `${API_BASE}/alertes/${id}/acquitter`,
        { method: "PATCH" }
      );

      if (!reponse.ok) {
        throw new Error("Acquittement impossible.");
      }

      // Actualiser immédiatement les informations.
      await chargerAlertes();
    } catch (error) {
      setErreur(error.message);
    } finally {
      setTraitementId(null);
    }
  }

  // Formater les dates pour l'affichage.
  function formaterDate(date) {
    if (!date) return "—";

    return new Date(date).toLocaleString("fr-FR");
  }

  return (
    <section className="alertes-dashboard">
      <header className="alertes-header">
        <div>
          <h2>Surveillance de la qualité d'eau</h2>
          <p>Alertes actives et anomalies détectées</p>
        </div>

        <button
          type="button"
          onClick={() => chargerAlertes()}
        >
          Actualiser
        </button>
      </header>

      {erreur && (
        <div className="alertes-erreur" role="alert">
          {erreur}
        </div>
      )}

      <div className="alertes-statistiques">
        <article>
          <span>Alertes non résolues</span>
          <strong>{resume?.total ?? "—"}</strong>
        </article>

        <article>
          <span>Critiques</span>
          <strong className="texte-critique">
            {resume?.critiques ?? "—"}
          </strong>
        </article>

        <article>
          <span>Avertissements</span>
          <strong className="texte-avertissement">
            {resume?.avertissements ?? "—"}
          </strong>
        </article>

        <article>
          <span>Acquittées</span>
          <strong>{resume?.acquittees ?? "—"}</strong>
        </article>
      </div>

      {chargement ? (
        <p>Chargement des alertes...</p>
      ) : alertes.length === 0 ? (
        <div className="alertes-vide">
          Aucune alerte non résolue.
        </div>
      ) : (
        <div className="alertes-table-wrapper">
          <table className="alertes-table">
            <thead>
              <tr>
                <th>Bassin</th>
                <th>Paramètre</th>
                <th>Valeur</th>
                <th>Niveau</th>
                <th>Statut</th>
                <th>Dernière détection</th>
                <th>Action</th>
              </tr>
            </thead>

            <tbody>
              {alertes.map((alerte) => (
                <tr key={alerte.id}>
                  <td>{alerte.bassin_id}</td>
                  <td>{alerte.parametre}</td>
                  <td>{alerte.valeur}</td>

                  <td>
                    <span
                      className={
                        alerte.niveau === "CRITIQUE"
                          ? "alerte-badge critique"
                          : "alerte-badge avertissement"
                      }
                    >
                      {alerte.niveau}
                    </span>
                  </td>

                  <td>{alerte.statut}</td>

                  <td>
                    {formaterDate(alerte.last_seen_at)}
                  </td>

                  <td>
                    {alerte.statut === "ACTIVE" ? (
                      <button
                        type="button"
                        disabled={traitementId === alerte.id}
                        onClick={() =>
                          acquitterAlerte(alerte.id)
                        }
                      >
                        {traitementId === alerte.id
                          ? "Traitement..."
                          : "Acquitter"}
                      </button>
                    ) : (
                      <span>Prise en compte</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
