
import { useEffect, useMemo, useState } from "react";

import {
  Activity,
  Radio,
  RadioTower,
  WifiOff,
  Waves,
  AlertTriangle,
  Thermometer,
  Droplets,
  Wind
} from "lucide-react";

import {
  ResponsiveContainer,
  LineChart,
  Line,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  Legend
} from "recharts";

import useSupervisionWebSocket
  from "../hooks/useSupervisionWebSocket";

import "./SupervisionTempsReel.css";

// Nombre maximal de points conservés en mémoire.
const MAX_POINTS = 60;

/**
 * Formater une mesure numérique.
 */
function valeurMesure(valeur, unite = "") {
  if (valeur === null || valeur === undefined) {
    return "—";
  }

  const nombre = Number(valeur);

  if (!Number.isFinite(nombre)) {
    return "—";
  }

  return `${nombre.toFixed(2)} ${unite}`.trim();
}

/**
 * Calculer l'âge d'une mesure en secondes.
 */
function ageMesure(date) {
  if (!date) return null;

  const timestamp = new Date(date).getTime();

  if (!Number.isFinite(timestamp)) {
    return null;
  }

  return Math.max(
    0,
    Math.floor((Date.now() - timestamp) / 1000)
  );
}

/**
 * Carte représentant un bassin.
 */
function CarteBassin({ bassin }) {
  const mesure = bassin.derniere_mesure;

  const age = ageMesure(mesure?.measure_at);

  // Indicateur informatif :
  // il ne remplace pas l'analyse des seuils.
  const sansMesureRecente = (
    age === null || age > 60
  );

  return (
    <article className="pf-temps-bassin">
      <div className="pf-temps-bassin-header">
        <div>
          <strong>{bassin.code}</strong>
          <span>{bassin.nom}</span>
        </div>

        {bassin.alertes_ouvertes > 0 ? (
          <span className="pf-temps-etat danger">
            <AlertTriangle size={14} />
            {bassin.alertes_ouvertes} alerte(s)
          </span>
        ) : (
          <span className="pf-temps-etat normal">
            Aucune alerte ouverte
          </span>
        )}
      </div>

      <div className="pf-temps-mesures">
        <div>
          <Thermometer size={18} />
          <small>Température</small>
          <strong>
            {valeurMesure(
              mesure?.temperature_c,
              "°C"
            )}
          </strong>
        </div>

        <div>
          <Droplets size={18} />
          <small>pH</small>
          <strong>
            {valeurMesure(mesure?.ph)}
          </strong>
        </div>

        <div>
          <Wind size={18} />
          <small>Oxygène dissous</small>
          <strong>
            {valeurMesure(
              mesure?.oxygene_dissous_mg_l,
              "mg/L"
            )}
          </strong>
        </div>
      </div>

      <footer>
        {mesure ? (
          <>
            Dernière mesure :{" "}
            {new Date(
              mesure.measure_at
            ).toLocaleString("fr-FR")}
          </>
        ) : (
          "Aucune mesure disponible"
        )}

        {sansMesureRecente && (
          <span className="pf-temps-retard">
            Mesure absente ou ancienne
          </span>
        )}
      </footer>
    </article>
  );
}

/**
 * PAGE PRINCIPALE — SUPERVISION EN TEMPS RÉEL
 */
export default function SupervisionTempsReel() {
  const {
    connecte,
    connexionEnCours,
    erreur,
    donnees,
    derniereReception
  } = useSupervisionWebSocket();

  // Bassin sélectionné pour les graphiques.
  const [bassinSelectionne, setBassinSelectionne] =
    useState("");

  // Historique temporaire des données reçues.
  const [historiqueLive, setHistoriqueLive] =
    useState({});

  /**
   * Sélectionner automatiquement le premier bassin.
   */
  useEffect(() => {
    if (
      !bassinSelectionne &&
      donnees.bassins.length > 0
    ) {
      setBassinSelectionne(
        String(donnees.bassins[0].id)
      );
    }
  }, [donnees.bassins, bassinSelectionne]);

  /**
   * Ajouter les mesures reçues dans l'historique.
   *
   * Les mesures identiques ne sont pas dupliquées.
   */
  useEffect(() => {
    if (!derniereReception) return;

    setHistoriqueLive((ancien) => {
      const nouveau = { ...ancien };
      let changement = false;

      for (const bassin of donnees.bassins) {
        const mesure = bassin.derniere_mesure;

        if (!mesure) continue;

        const cle = String(bassin.id);
        const points = nouveau[cle] ?? [];

        // Éviter d'ajouter plusieurs fois
        // la même mesure à chaque réception WebSocket.
        const dernierPoint = points.at(-1);

        if (dernierPoint?.id === mesure.id) {
          continue;
        }

        const point = {
          id: mesure.id,

          heure: new Date(
            mesure.measure_at
          ).toLocaleTimeString("fr-FR"),

          temperature:
            mesure.temperature_c === null
              ? null
              : Number(mesure.temperature_c),

          ph:
            mesure.ph === null
              ? null
              : Number(mesure.ph),

          oxygene:
            mesure.oxygene_dissous_mg_l === null
              ? null
              : Number(
                  mesure.oxygene_dissous_mg_l
                )
        };

        nouveau[cle] = [
          ...points,
          point
        ].slice(-MAX_POINTS);

        changement = true;
      }

      return changement ? nouveau : ancien;
    });
  }, [donnees, derniereReception]);

  /**
   * Extraire les données du bassin sélectionné.
   */
  const graphique = useMemo(() => {
    return (
      historiqueLive[String(bassinSelectionne)] ?? []
    );
  }, [historiqueLive, bassinSelectionne]);

  return (
    <div className="pf-temps-page">

      {/* EN-TÊTE */}

      <header className="pf-temps-header">
        <div>
          <h1>
            <RadioTower size={28} />
            Supervision en temps réel
          </h1>

          <p>
            Surveillance automatique de tous les bassins
            connectés.
          </p>
        </div>

        <span
          className={
            "pf-temps-connexion " +
            (connecte ? "connecte" : "deconnecte")
          }
        >
          {connecte ? (
            <Radio size={17} />
          ) : (
            <WifiOff size={17} />
          )}

          {connecte
            ? "WebSocket connecté"
            : connexionEnCours
              ? "Connexion..."
              : "Déconnecté"}
        </span>
      </header>

      {/* ERREURS */}

      {erreur && (
        <div className="pf-temps-erreur">
          <AlertTriangle size={18} />
          {erreur}
        </div>
      )}

      {/* INDICATEURS */}

      <section className="pf-temps-indicateurs">
        <article>
          <Waves size={23} />
          <span>Bassins</span>
          <strong>{donnees.nombre_bassins}</strong>
        </article>

        <article>
          <AlertTriangle size={23} />
          <span>Alertes ouvertes</span>
          <strong>
            {donnees.nombre_alertes_ouvertes}
          </strong>
        </article>

        <article>
          <Activity size={23} />
          <span>Dernière réception</span>
          <strong className="pf-temps-heure">
            {derniereReception
              ? derniereReception.toLocaleTimeString("fr-FR")
              : "En attente"}
          </strong>
        </article>
      </section>

      {/* LISTE DES BASSINS */}

      <section className="pf-temps-section">
        <h2>État des bassins</h2>

        <div className="pf-temps-grille">
          {donnees.bassins.map((bassin) => (
            <CarteBassin
              key={bassin.id}
              bassin={bassin}
            />
          ))}
        </div>

        {donnees.bassins.length === 0 && (
          <p>Aucun bassin disponible.</p>
        )}
      </section>

      {/* GRAPHIQUES */}

      <section className="pf-temps-section">
        <div className="pf-temps-section-header">
          <div>
            <h2>Évolution en direct</h2>
            <p>
              Les 60 dernières mesures reçues
              pendant cette session.
            </p>
          </div>

          <select
            value={bassinSelectionne}
            onChange={(e) =>
              setBassinSelectionne(e.target.value)
            }
          >
            {donnees.bassins.map((bassin) => (
              <option
                key={bassin.id}
                value={bassin.id}
              >
                {bassin.code} — {bassin.nom}
              </option>
            ))}
          </select>
        </div>

        <div className="pf-temps-graphique">
          {graphique.length === 0 ? (
            <p>
              En attente de nouvelles mesures...
            </p>
          ) : (
            <ResponsiveContainer
              width="100%"
              height="100%"
            >
              <LineChart data={graphique}>
                <CartesianGrid
                  strokeDasharray="3 3"
                />

                <XAxis
                  dataKey="heure"
                  minTickGap={30}
                />

                <YAxis
                  domain={["auto", "auto"]}
                />

                <Tooltip />
                <Legend />

                <Line
                  dataKey="temperature"
                  name="Température (°C)"
                  stroke="#e67e22"
                  dot={false}
                  isAnimationActive={false}
                  connectNulls={false}
                />

                <Line
                  dataKey="ph"
                  name="pH"
                  stroke="#2563eb"
                  dot={false}
                  isAnimationActive={false}
                  connectNulls={false}
                />

                <Line
                  dataKey="oxygene"
                  name="Oxygène (mg/L)"
                  stroke="#16a34a"
                  dot={false}
                  isAnimationActive={false}
                  connectNulls={false}
                />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>

        <p className="pf-temps-note">
          Les valeurs des trois paramètres sont affichées
          sur une échelle commune pour ce prototype.
          L'historique permanent reste disponible
          dans le module Historique des mesures.
        </p>
      </section>
    </div>
  );
}
