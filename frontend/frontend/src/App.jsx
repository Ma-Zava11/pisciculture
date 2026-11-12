
import { useState } from "react";

import {
  BrowserRouter,
  Routes,
  Route,
  Navigate
} from "react-router-dom";

// Pages existantes du projet.
import Dashboard from "./pages/Dashbord";
import HistoriqueMesures from "./pages/HistoriqueMesures";
import ParametrageSeuils from "./pages/ParametrageSeuils";

// Nouveau composant de navigation.
import Sidebar from "./components/Sidebar";

// Styles isolés de la Sidebar et de la mise en page.
import "./components/Sidebar.css";
import CentreAlertes from "./pages/CentreAlertes";
import SupervisionTempsReel from "./pages/SupervisionTempsReel";
import GestionAppareils from "./pages/GestionAppareils";

/**
 * Application principale de pisciculture intelligente.
 *
 * React Router affiche une seule page à la fois.
 * La Sidebar reste visible pendant la navigation.
 */
function App() {
  /**
   * Charger la préférence de réduction sauvegardée.
   *
   * Si aucune préférence n'existe,
   * le menu est agrandi par défaut.
   */
  const [sidebarReduite, setSidebarReduite] = useState(
    () => {
      try {
        return (
          localStorage.getItem("pf-sidebar-reduite") ===
          "true"
        );
      } catch {
        return false;
      }
    }
  );

  /**
   * Mettre à jour la Sidebar et mémoriser son état.
   */
  function modifierSidebar(valeur) {
    setSidebarReduite((ancienneValeur) => {
      const nouvelleValeur =
        typeof valeur === "function"
          ? valeur(ancienneValeur)
          : valeur;

      try {
        localStorage.setItem(
          "pf-sidebar-reduite",
          String(nouvelleValeur)
        );
      } catch {
        // L'application reste utilisable même si
        // le navigateur bloque localStorage.
      }

      return nouvelleValeur;
    });
  }

  return (
    <BrowserRouter>
      <div
        className={[
          "pf-app-layout",
          sidebarReduite
            ? "pf-app-layout--collapsed"
            : ""
        ].filter(Boolean).join(" ")}
      >
        {/* MENU LATÉRAL PERMANENT */}

        <Sidebar
          reduit={sidebarReduite}
          setReduit={modifierSidebar}
        />

        {/* CONTENU PRINCIPAL */}

        <main className="pf-app-content">
          <div className="pf-app-page">
            <Routes>

              {/* TABLEAU DE BORD */}

              <Route
                path="/"
                element={<Dashboard />}
              />
              <Route
                path="/supervision"
                element={<SupervisionTempsReel />}
              />

              {/* PARAMÉTRAGE DES SEUILS */}

              <Route
                path="/seuils"
                element={<ParametrageSeuils />}
              />

              {/* HISTORIQUE DES MESURES */}

              <Route
                path="/historique"
                element={<HistoriqueMesures />}
              />

              {/* ROUTE INCONNUE */}

              <Route
                path="*"
                element={<Navigate to="/" replace />}
              />
              <Route
                path="/alertes"
                element={<CentreAlertes />}
              />
              <Route
                path="/appareils"
                element={<GestionAppareils />}
              />

            </Routes>
          </div>
        </main>
      </div>
    </BrowserRouter>
  );
}

export default App;
