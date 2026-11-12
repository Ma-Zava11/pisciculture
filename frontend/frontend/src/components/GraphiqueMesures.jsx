
import { useMemo } from "react";

import {
  ResponsiveContainer,
  LineChart,
  Line,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip
} from "recharts";

// Configuration de chaque graphique.
const GRAPHIQUES = [
  {
    cle: "temperature_c",
    titre: "Température",
    unite: "°C",
    couleur: "#e05b52"
  },
  {
    cle: "ph",
    titre: "Potentiel hydrogène (pH)",
    unite: "",
    couleur: "#3478dc"
  },
  {
    cle: "oxygene_dissous_mg_l",
    titre: "Oxygène dissous",
    unite: "mg/L",
    couleur: "#079b8e"
  }
];

/**
 * Affiche les courbes historiques d'un bassin.
 *
 * Les mesures reçues depuis FastAPI sont normalement
 * triées de la plus récente à la plus ancienne.
 * On les remet ici dans l'ordre chronologique.
 */
export default function GraphiqueMesures({
  mesures = []
}) {
  const donnees = useMemo(() => {
    return [...mesures]
      .filter((mesure) =>
        !Number.isNaN(Date.parse(mesure.measure_at))
      )
      .sort((a, b) => {
        const ecart =
          Date.parse(a.measure_at) -
          Date.parse(b.measure_at);

        return ecart || a.id - b.id;
      })
      .map((mesure) => {
        const date = new Date(mesure.measure_at);

        return {
          ...mesure,

          // Affichage de l'heure locale du navigateur.
          heure: date.toLocaleTimeString("fr-FR", {
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit"
          }),

          // Date complète utilisée dans l'infobulle.
          dateComplete: date.toLocaleString("fr-FR")
        };
      });
  }, [mesures]);

  if (donnees.length === 0) {
    return (
      <div className="dashboard-empty">
        <p>
          Aucune mesure disponible pour les graphiques.
        </p>
      </div>
    );
  }

  return (
    <div className="mesures-graphiques">
      {GRAPHIQUES.map((graphique) => (
        <article
          className="mesures-graphique-card"
          key={graphique.cle}
        >
          <div className="mesures-graphique-heading">
            <h3>{graphique.titre}</h3>
            <span>{graphique.unite}</span>
          </div>

          <div className="mesures-graphique-zone">
            <ResponsiveContainer
              width="100%"
              height="100%"
            >
              <LineChart
                data={donnees}
                margin={{
                  top: 10,
                  right: 12,
                  left: -15,
                  bottom: 5
                }}
              >
                <CartesianGrid
                  stroke="#e8eef5"
                  strokeDasharray="3 3"
                />

                <XAxis
                  dataKey="heure"
                  tick={{ fontSize: 11 }}
                  minTickGap={20}
                />

                <YAxis
                  tick={{ fontSize: 11 }}
                  domain={["auto", "auto"]}
                />

                <Tooltip
                  labelFormatter={(_, payload) =>
                    payload?.[0]?.payload?.dateComplete ??
                    ""
                  }
                  formatter={(valeur) => [
                    `${valeur ?? "—"} ${graphique.unite}`,
                    graphique.titre
                  ]}
                />

                <Line
                  type="monotone"
                  dataKey={graphique.cle}
                  stroke={graphique.couleur}
                  strokeWidth={2.5}
                  dot={false}
                  activeDot={{ r: 5 }}
                  connectNulls={false}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </article>
      ))}
    </div>
  );
}
