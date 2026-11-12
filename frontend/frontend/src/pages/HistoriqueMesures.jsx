
import { useEffect, useMemo, useState } from "react";

import {
  Activity,
  Download,
  RefreshCw,
  AlertTriangle,
  CalendarDays,
  Database
} from "lucide-react";

import {
  ResponsiveContainer,
  LineChart,
  Line,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip
} from "recharts";

import {
  getBassins,
  getHistoriqueMesures,
  getStatistiquesHistorique,
  getAnomaliesHistorique,
  exporterHistorique
} from "../services/api";

import "./HistoriqueMesures.css";

const TAILLE_PAGE = 50;

/**
 * Convertir une date locale saisie dans un champ
 * datetime-local vers une date ISO UTC.
 */
function versISO(valeur) {
  if (!valeur) return "";

  const date = new Date(valeur);

  if (Number.isNaN(date.getTime())) {
    return "";
  }

  return date.toISOString();
}

/**
 * Produire une valeur initiale pour datetime-local
 * en respectant le fuseau horaire du navigateur.
 */
function dateLocale(date) {
  const d = new Date(date);

  const decalage = d.getTimezoneOffset() * 60000;

  return new Date(d.getTime() - decalage)
    .toISOString()
    .slice(0, 16);
}

/**
 * Afficher un nombre sans provoquer d'erreur
 * lorsqu'aucune mesure n'est disponible.
 */
function nombre(valeur, decimales = 2) {
  if (valeur === null || valeur === undefined) {
    return "—";
  }

  const n = Number(valeur);

  return Number.isFinite(n)
    ? n.toLocaleString("fr-FR", {
        minimumFractionDigits: decimales,
        maximumFractionDigits: decimales
      })
    : "—";
}

/**
 * Afficher les dates dans le fuseau du navigateur.
 */
function afficherDate(valeur) {
  if (!valeur) return "—";

  const d = new Date(valeur);

  return Number.isNaN(d.getTime())
    ? "—"
    : d.toLocaleString("fr-FR");
}

/**
 * Carte de statistiques.
 */
function CarteStatistique({
  titre,
  donnees,
  unite = ""
}) {
  return (
    <article className="historique-stat-card">
      <span>{titre}</span>

      <strong>
        {nombre(donnees?.moyenne)}
        {unite && <small> {unite}</small>}
      </strong>

      <div className="historique-stat-details">
        <span>Min : {nombre(donnees?.min)}</span>
        <span>Max : {nombre(donnees?.max)}</span>
      </div>
    </article>
  );
}

/**
 * Graphique d'un paramètre.
 */
function GraphiqueHistorique({
  titre,
  donnees,
  champ,
  unite,
  couleur
}) {
  return (
    <article className="historique-chart-card">
      <h3>{titre}</h3>

      {donnees.length === 0 ? (
        <p>Aucune mesure pour cette période.</p>
      ) : (
        <div className="historique-chart">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={donnees}>
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="#e5e7eb"
              />

              <XAxis
                dataKey="heure"
                minTickGap={35}
                tick={{ fontSize: 11 }}
              />

              <YAxis
                width={45}
                tick={{ fontSize: 11 }}
                domain={["auto", "auto"]}
              />

              <Tooltip
                labelFormatter={(_, elements) =>
                  elements?.[0]?.payload?.dateComplete ?? ""
                }
                formatter={(valeur) => [
                  `${nombre(valeur)} ${unite}`,
                  titre
                ]}
              />

              <Line
                type="monotone"
                dataKey={champ}
                stroke={couleur}
                strokeWidth={2}
                dot={false}
                connectNulls={false}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </article>
  );
}

/**
 * Page principale du Jour 10.
 */
export default function HistoriqueMesures() {
  // --------------------------------------------------------
  // BASSINS ET FILTRES
  // --------------------------------------------------------

  const [bassins, setBassins] = useState([]);
  const [bassinId, setBassinId] = useState("");

  const [dateDebut, setDateDebut] = useState(() =>
    dateLocale(Date.now() - 24 * 60 * 60 * 1000)
  );

  const [dateFin, setDateFin] = useState(() =>
    dateLocale(new Date())
  );

  const [page, setPage] = useState(0);

  // --------------------------------------------------------
  // DONNÉES DE L'HISTORIQUE
  // --------------------------------------------------------

  const [historique, setHistorique] = useState({
    total: 0,
    mesures: []
  });

  const [statistiques, setStatistiques] = useState(null);
  const [anomalies, setAnomalies] = useState(null);

  const [chargement, setChargement] = useState(false);
  const [exportEnCours, setExportEnCours] = useState("");
  const [erreur, setErreur] = useState("");

  const [actualisation, setActualisation] = useState(0);

  // --------------------------------------------------------
  // CHARGER LES BASSINS UNE SEULE FOIS
  // --------------------------------------------------------

  useEffect(() => {
    let actif = true;

    async function charger() {
      try {
        const liste = await getBassins();

        if (!actif) return;

        setBassins(Array.isArray(liste) ? liste : []);

        if (Array.isArray(liste) && liste.length > 0) {
          setBassinId(String(liste[0].id));
        }
      } catch (e) {
        if (actif) {
          setErreur(e.message);
        }
      }
    }

    charger();

    return () => {
      actif = false;
    };
  }, []);

  // --------------------------------------------------------
  // CONSTRUIRE LES FILTRES UTILISÉS PAR FASTAPI
  // --------------------------------------------------------

  const filtres = useMemo(() => ({
    bassinId: Number(bassinId),
    dateDebut: versISO(dateDebut),
    dateFin: versISO(dateFin),
    limite: TAILLE_PAGE,
    offset: page * TAILLE_PAGE
  }), [bassinId, dateDebut, dateFin, page]);

  // --------------------------------------------------------
  // CHARGER LES DONNÉES
  // --------------------------------------------------------

  useEffect(() => {
    if (!bassinId) return;

    const controller = new AbortController();

    async function chargerHistorique() {
      setChargement(true);
      setErreur("");

      try {
        if (
          !filtres.dateDebut ||
          !filtres.dateFin ||
          new Date(filtres.dateDebut) >=
            new Date(filtres.dateFin)
        ) {
          throw new Error(
            "Sélectionne une période valide."
          );
        }

        const [mesures, stats, depassements] =
          await Promise.all([
            getHistoriqueMesures(
              filtres,
              controller.signal
            ),
            getStatistiquesHistorique(
              filtres,
              controller.signal
            ),
            getAnomaliesHistorique(
              filtres,
              controller.signal
            )
          ]);

        if (controller.signal.aborted) return;

        setHistorique(mesures);
        setStatistiques(stats);
        setAnomalies(depassements);

      } catch (e) {
        if (!controller.signal.aborted) {
          setErreur(e.message);
        }
      } finally {
        if (!controller.signal.aborted) {
          setChargement(false);
        }
      }
    }

    chargerHistorique();

    return () => controller.abort();

  }, [bassinId, filtres, actualisation]);

  // --------------------------------------------------------
  // PRÉPARER LES MESURES POUR LES GRAPHIQUES
  // --------------------------------------------------------

  const donneesGraphiques = useMemo(() => {
    const mesures = historique.mesures ?? [];

    return [...mesures]
      .sort(
        (a, b) =>
          new Date(a.measure_at) -
          new Date(b.measure_at)
      )
      .map((m) => ({
        heure: new Date(m.measure_at)
          .toLocaleTimeString("fr-FR", {
            hour: "2-digit",
            minute: "2-digit"
          }),

        dateComplete: afficherDate(m.measure_at),

        temperature:
          m.temperature_c === null
            ? null
            : Number(m.temperature_c),

        ph:
          m.ph === null
            ? null
            : Number(m.ph),

        oxygene:
          m.oxygene_dissous_mg_l === null
            ? null
            : Number(m.oxygene_dissous_mg_l)
      }));

  }, [historique.mesures]);

  // --------------------------------------------------------
  // CHANGER DE BASSIN OU DE PÉRIODE
  // --------------------------------------------------------

  function changerBassin(valeur) {
    setBassinId(valeur);
    setPage(0);
  }

  function changerDebut(valeur) {
    setDateDebut(valeur);
    setPage(0);
  }

  function changerFin(valeur) {
    setDateFin(valeur);
    setPage(0);
  }

  // --------------------------------------------------------
  // TÉLÉCHARGER LE CSV OU LE XLSX
  // --------------------------------------------------------

  async function telecharger(format) {
    setExportEnCours(format);
    setErreur("");

    try {
      await exporterHistorique(filtres, format);
    } catch (e) {
      setErreur(e.message);
    } finally {
      setExportEnCours("");
    }
  }

  const nombrePages = Math.ceil(
    (historique.total ?? 0) / TAILLE_PAGE
  );

  // --------------------------------------------------------
  // AFFICHAGE DE LA PAGE
  // --------------------------------------------------------

  return (
    <main className="historique-page">

      <header className="historique-header">
        <div>
          <h1>
            <Activity size={27} />
            Historique des mesures
          </h1>

          <p>
            Analyse de la qualité de l'eau par bassin
            et par période.
          </p>
        </div>

        <button
          type="button"
          className="historique-btn"
          onClick={() =>
            setActualisation((valeur) => valeur + 1)
          }
          disabled={chargement}
        >
          <RefreshCw size={16} />
          Actualiser
        </button>
      </header>

      {/* FILTRES */}

      <section className="historique-filtres">
        <div className="historique-filtre">
          <label htmlFor="historique-bassin">
            Bassin
          </label>

          <select
            id="historique-bassin"
            value={bassinId}
            onChange={(e) =>
              changerBassin(e.target.value)
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

        <div className="historique-filtre">
          <label htmlFor="historique-debut">
            <CalendarDays size={14} />
            Date de début
          </label>

          <input
            id="historique-debut"
            type="datetime-local"
            value={dateDebut}
            onChange={(e) =>
              changerDebut(e.target.value)
            }
          />
        </div>

        <div className="historique-filtre">
          <label htmlFor="historique-fin">
            <CalendarDays size={14} />
            Date de fin
          </label>

          <input
            id="historique-fin"
            type="datetime-local"
            value={dateFin}
            onChange={(e) =>
              changerFin(e.target.value)
            }
          />
        </div>
      </section>

      {/* ERREURS ET CHARGEMENT */}

      {erreur && (
        <div className="historique-erreur">
          <AlertTriangle size={18} />
          {erreur}
        </div>
      )}

      {chargement && (
        <p className="historique-chargement">
          Chargement des données...
        </p>
      )}

      {/* STATISTIQUES */}

      <section className="historique-stats">
        <article className="historique-stat-card">
          <span>Nombre de mesures</span>

          <strong>
            {statistiques?.nombre_mesures ?? 0}
          </strong>

          <div className="historique-stat-details">
            <span>
              <Database size={14} />
              PostgreSQL
            </span>
          </div>
        </article>

        <CarteStatistique
          titre="Température moyenne"
          donnees={statistiques?.temperature}
          unite="°C"
        />

        <CarteStatistique
          titre="pH moyen"
          donnees={statistiques?.ph}
        />

        <CarteStatistique
          titre="Oxygène moyen"
          donnees={statistiques?.oxygene}
          unite="mg/L"
        />
      </section>

      {/* GRAPHIQUES */}

      <section className="historique-section">
        <h2>Évolution des paramètres</h2>

        <p className="historique-note">
          Les graphiques présentent les mesures de
          la page courante. Les statistiques portent
          sur toute la période sélectionnée.
        </p>

        <div className="historique-graphiques">
          <GraphiqueHistorique
            titre="Température"
            donnees={donneesGraphiques}
            champ="temperature"
            unite="°C"
            couleur="#e67e22"
          />

          <GraphiqueHistorique
            titre="pH"
            donnees={donneesGraphiques}
            champ="ph"
            unite=""
            couleur="#2563eb"
          />

          <GraphiqueHistorique
            titre="Oxygène dissous"
            donnees={donneesGraphiques}
            champ="oxygene"
            unite="mg/L"
            couleur="#16a34a"
          />
        </div>
      </section>

      {/* ANOMALIES */}

      <section className="historique-section">
        <div className="historique-section-header">
          <h2>
            <AlertTriangle size={20} />
            Périodes anormales
          </h2>

          <span className="historique-compteur">
            {anomalies?.nombre_periodes ?? 0} périodes
          </span>
        </div>

        <p className="historique-note">
          Mesures anormales :
          {" "}
          {anomalies?.nombre_mesures_anormales ?? 0}
        </p>

        <div className="historique-table-wrapper">
          <table className="historique-table">
            <thead>
              <tr>
                <th>Paramètre</th>
                <th>Niveau</th>
                <th>Début</th>
                <th>Fin</th>
                <th>Mesures</th>
              </tr>
            </thead>

            <tbody>
              {(anomalies?.periodes ?? []).map(
                (periode, index) => (
                  <tr key={index}>
                    <td>{periode.parametre}</td>

                    <td>
                      <span
                        className={
                          "historique-niveau " +
                          (periode.niveau === "CRITIQUE"
                            ? "critique"
                            : "avertissement")
                        }
                      >
                        {periode.niveau}
                      </span>
                    </td>

                    <td>
                      {afficherDate(periode.debut)}
                    </td>

                    <td>
                      {afficherDate(periode.fin)}
                    </td>

                    <td>{periode.nombre_mesures}</td>
                  </tr>
                )
              )}

              {(anomalies?.periodes ?? []).length === 0 && (
                <tr>
                  <td colSpan={5}>
                    Aucune période anormale détectée.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* TABLEAU DES MESURES */}

      <section className="historique-section">
        <div className="historique-section-header">
          <h2>Mesures enregistrées</h2>

          <div className="historique-actions">
            <button
              type="button"
              className="historique-btn"
              disabled={!bassinId || !!exportEnCours}
              onClick={() => telecharger("csv")}
            >
              <Download size={16} />
              {exportEnCours === "csv"
                ? "Export..."
                : "CSV"}
            </button>

            <button
              type="button"
              className="historique-btn primaire"
              disabled={!bassinId || !!exportEnCours}
              onClick={() => telecharger("xlsx")}
            >
              <Download size={16} />
              {exportEnCours === "xlsx"
                ? "Export..."
                : "Excel (.xlsx)"}
            </button>
          </div>
        </div>

        <div className="historique-table-wrapper">
          <table className="historique-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Température</th>
                <th>pH</th>
                <th>Oxygène</th>
                <th>Source</th>
              </tr>
            </thead>

            <tbody>
              {(historique.mesures ?? []).map(
                (mesure) => (
                  <tr key={mesure.id}>
                    <td>
                      {afficherDate(mesure.measure_at)}
                    </td>

                    <td>
                      {nombre(mesure.temperature_c)} °C
                    </td>

                    <td>{nombre(mesure.ph)}</td>

                    <td>
                      {nombre(
                        mesure.oxygene_dissous_mg_l
                      )} mg/L
                    </td>

                    <td>{mesure.source}</td>
                  </tr>
                )
              )}

              {(historique.mesures ?? []).length === 0 && (
                <tr>
                  <td colSpan={5}>
                    Aucune mesure disponible.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* PAGINATION */}

        <footer className="historique-pagination">
          <span>
            Page {page + 1} sur{" "}
            {Math.max(nombrePages, 1)}
            {" — "}
            {historique.total ?? 0} mesures
          </span>

          <div>
            <button
              type="button"
              disabled={page === 0 || chargement}
              onClick={() =>
                setPage((p) => Math.max(0, p - 1))
              }
            >
              Précédent
            </button>

            <button
              type="button"
              disabled={
                chargement ||
                page + 1 >= nombrePages
              }
              onClick={() =>
                setPage((p) => p + 1)
              }
            >
              Suivant
            </button>
          </div>
        </footer>
      </section>

    </main>
  );
}
