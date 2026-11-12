import { useEffect, useState } from "react";

import {
  Settings2,
  Save,
  RefreshCw,
  AlertCircle,
  CheckCircle2
} from "lucide-react";

import {
  getSeuils,
  updateSeuil
} from "../services/api";

import "./ParametrageSeuils.css";

// Libellés des paramètres.
const LIBELLES = {
  temperature_c: "Température (°C)",
  ph: "pH de l'eau",
  oxygene_dissous_mg_l: "Oxygène dissous (mg/L)"
};

// Champs modifiables.
const CHAMPS = [
  { nom: "critique_min", titre: "Critique min" },
  { nom: "normal_min", titre: "Normal min" },
  { nom: "normal_max", titre: "Normal max" },
  { nom: "critique_max", titre: "Critique max" }
];

/**
 * Affiche un formulaire de modification des seuils.
 *
 * Chaque ligne possède son propre bouton Enregistrer.
 */
export default function ParametrageSeuils() {
  const [seuils, setSeuils] = useState([]);
  const [chargement, setChargement] = useState(true);
  const [enregistrement, setEnregistrement] = useState(null);
  const [erreur, setErreur] = useState("");
  const [succes, setSucces] = useState("");

  // Charger les configurations depuis PostgreSQL.
  async function chargerSeuils() {
    try {
      setChargement(true);
      setErreur("");

      const donnees = await getSeuils();

      if (!Array.isArray(donnees)) {
        throw new Error("Réponse API invalide.");
      }

      // Convertir les valeurs numériques en chaînes
      // pour les champs de saisie.
      setSeuils(
        donnees.map((seuil) => ({
          ...seuil,
          critique_min: seuil.critique_min ?? "",
          normal_min: seuil.normal_min ?? "",
          normal_max: seuil.normal_max ?? "",
          critique_max: seuil.critique_max ?? ""
        }))
      );

    } catch (error) {
      setErreur(error.message);
    } finally {
      setChargement(false);
    }
  }

  useEffect(() => {
    chargerSeuils();
  }, []);

  // Modifier localement une valeur.
  function modifierChamp(id, champ, valeur) {
    setSeuils((anciens) =>
      anciens.map((seuil) =>
        seuil.id === id
          ? { ...seuil, [champ]: valeur }
          : seuil
      )
    );

    setSucces("");
  }

  // Convertir un champ vide en NULL PostgreSQL.
  function convertirNombre(valeur) {
    if (valeur === "" || valeur === null) {
      return null;
    }

    const nombre = Number(valeur);

    if (!Number.isFinite(nombre)) {
      throw new Error("Valeur numérique invalide.");
    }

    return nombre;
  }

  // Enregistrer une configuration dans FastAPI.
  async function enregistrer(seuil) {
    try {
      setEnregistrement(seuil.id);
      setErreur("");
      setSucces("");

      const donnees = {
        critique_min: convertirNombre(seuil.critique_min),
        normal_min: convertirNombre(seuil.normal_min),
        normal_max: convertirNombre(seuil.normal_max),
        critique_max: convertirNombre(seuil.critique_max),
        actif: seuil.actif
      };

      await updateSeuil(seuil.id, donnees);

      setSucces(
        `Configuration ${seuil.id} enregistrée avec succès.`
      );

      // Recharger les valeurs réellement enregistrées.
      await chargerSeuils();

    } catch (error) {
      setErreur(error.message);
    } finally {
      setEnregistrement(null);
    }
  }

  return (
    <main className="seuils-page">

      <header className="seuils-header">
        <div>
          <span className="seuils-eyebrow">
            <Settings2 size={16} />
            PARAMÉTRAGE
          </span>

          <h1>Seuils de qualité de l'eau</h1>

          <p>
            Configure les limites normales et critiques
            utilisées par le système de surveillance.
          </p>
        </div>

        <button
          className="seuils-refresh"
          type="button"
          onClick={chargerSeuils}
          disabled={chargement}
        >
          <RefreshCw size={17} />
          Actualiser
        </button>
      </header>

      {erreur && (
        <div className="seuils-message erreur" role="alert">
          <AlertCircle size={18} />
          {erreur}
        </div>
      )}

      {succes && (
        <div className="seuils-message succes" role="status">
          <CheckCircle2 size={18} />
          {succes}
        </div>
      )}

      {chargement && seuils.length === 0 && (
        <p>Chargement des configurations...</p>
      )}

      {!chargement && seuils.length === 0 && (
        <p>
          Aucun seuil enregistré dans PostgreSQL.
        </p>
      )}

      <div className="seuils-liste">
        {seuils.map((seuil) => (
          <article
            className="seuils-card"
            key={seuil.id}
          >
            <div className="seuils-card-header">
              <div>
                <h2>
                  {LIBELLES[seuil.parametre] ??
                    seuil.parametre}
                </h2>

                <p>
                  {seuil.bassin_id !== null
                    ? `Bassin ${seuil.bassin_id}`
                    : seuil.espece_id !== null
                      ? `Espèce ${seuil.espece_id}`
                      : "Configuration globale"}
                </p>
              </div>

              <label className="seuils-actif">
                <input
                  type="checkbox"
                  checked={seuil.actif}
                  onChange={(event) =>
                    modifierChamp(
                      seuil.id,
                      "actif",
                      event.target.checked
                    )
                  }
                />
                Actif
              </label>
            </div>

            <div className="seuils-champs">
              {CHAMPS.map((champ) => (
                <label key={champ.nom}>
                  <span>{champ.titre}</span>

                  <input
                    type="number"
                    step="0.01"
                    value={seuil[champ.nom]}
                    onChange={(event) =>
                      modifierChamp(
                        seuil.id,
                        champ.nom,
                        event.target.value
                      )
                    }
                    placeholder="Non défini"
                  />
                </label>
              ))}
            </div>

            <div className="seuils-card-footer">
              <small>
                Dernière modification :
                {" "}
                {new Date(
                  seuil.updated_at
                ).toLocaleString("fr-FR")}
              </small>

              <button
                type="button"
                onClick={() => enregistrer(seuil)}
                disabled={enregistrement !== null}
              >
                <Save size={17} />

                {enregistrement === seuil.id
                  ? "Enregistrement..."
                  : "Enregistrer"}
              </button>
            </div>
          </article>
        ))}
      </div>
    </main>
  );
}
