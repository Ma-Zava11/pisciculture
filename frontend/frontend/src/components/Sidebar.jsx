
import { useEffect, useState } from "react";

import {
  NavLink,
  useLocation
} from "react-router-dom";

import {
  Waves,
  LayoutDashboard,
  SlidersHorizontal,
  ChartNoAxesCombined,
  PanelLeftClose,
  PanelLeftOpen,
  Menu,
  X,
  Fish,
  ChevronRight,
  BellRing,
  RadioTower,
  Cpu 
} from "lucide-react";

import "./Sidebar.css";

/**
 * ==========================================================
 * SIDEBAR — PISCICULTURE INTELLIGENTE
 * ==========================================================
 *
 * Fonctionnalités :
 * - Navigation React Router.
 * - Réduction / agrandissement du menu.
 * - Sauvegarde de la préférence dans localStorage.
 * - Menu mobile avec fond superposé.
 * - Fermeture automatique après navigation mobile.
 *
 * Les classes CSS commencent toutes par pf-.
 */

// Définir les liens de navigation.
const MENU_ITEMS = [
  {
    nom: "Tableau de bord",
    chemin: "/",
    icone: LayoutDashboard,
    fin: true
  },
  {
    nom: "Supervision en direct",
    chemin: "/supervision",
    icone: RadioTower
  },
  {
    nom: "Gestion des appareils",
    chemin: "/appareils",
    icone: Cpu
  },
  {
    nom: "Paramétrage des seuils",
    chemin: "/seuils",
    icone: SlidersHorizontal
  },
  {
    nom: "Historique des mesures",
    chemin: "/historique",
    icone: ChartNoAxesCombined
  },
  {
    nom: "Centre d'alertes",
    chemin: "/alertes",
    icone: BellRing
  },
];

export default function Sidebar({
  reduit,
  setReduit
}) {
  // État du menu sur les petits écrans.
  const [mobileOuvert, setMobileOuvert] = useState(false);

  // Permet de détecter un changement de page.
  const location = useLocation();

  /**
   * Fermer automatiquement le menu mobile
   * lorsqu'on change de page.
   */
  useEffect(() => {
    setMobileOuvert(false);
  }, [location.pathname]);

  /**
   * Empêcher le défilement de la page en arrière-plan
   * lorsque le menu mobile est ouvert.
   */
  useEffect(() => {
    if (!mobileOuvert) return;

    const ancienOverflow = document.body.style.overflow;

    document.body.style.overflow = "hidden";

    return () => {
      document.body.style.overflow = ancienOverflow;
    };
  }, [mobileOuvert]);

  /**
   * Permettre de fermer le menu mobile avec Échap.
   */
  useEffect(() => {
    function fermerAvecEchap(event) {
      if (event.key === "Escape") {
        setMobileOuvert(false);
      }
    }

    window.addEventListener("keydown", fermerAvecEchap);

    return () => {
      window.removeEventListener(
        "keydown",
        fermerAvecEchap
      );
    };
  }, []);

  /**
   * Réduire ou agrandir le menu sur ordinateur.
   */
  function basculerSidebar() {
    setReduit((valeur) => !valeur);
  }

  return (
    <>
      {/* BARRE SUPÉRIEURE SUR MOBILE */}

      <header className="pf-mobile-header">
        <button
          type="button"
          className="pf-mobile-menu-btn"
          onClick={() => setMobileOuvert(true)}
          aria-label="Ouvrir le menu"
        >
          <Menu size={22} />
        </button>

        <div className="pf-mobile-brand">
          <Waves size={23} />
          <span>AquaSmart</span>
        </div>
      </header>

      {/* FOND SUPERPOSÉ SUR MOBILE */}

      {mobileOuvert && (
        <button
          type="button"
          className="pf-sidebar-overlay"
          onClick={() => setMobileOuvert(false)}
          aria-label="Fermer le menu"
        />
      )}

      {/* BARRE LATÉRALE */}

      <aside
        className={[
          "pf-sidebar",
          reduit ? "pf-sidebar--collapsed" : "",
          mobileOuvert ? "pf-sidebar--mobile-open" : ""
        ].filter(Boolean).join(" ")}
      >
        {/* EN-TÊTE DE LA SIDEBAR */}

        <div className="pf-sidebar-header">
          <div className="pf-sidebar-logo">
            <div className="pf-sidebar-logo-icon">
              <Waves size={23} />
            </div>

            <div className="pf-sidebar-brand-text">
              <strong>AquaSmart</strong>
              <span>Pisciculture IoT</span>
            </div>
          </div>

          {/* BOUTON RÉDUIRE / AGRANDIR */}

          <button
            type="button"
            className="pf-sidebar-toggle"
            onClick={basculerSidebar}
            aria-label={
              reduit
                ? "Agrandir la barre latérale"
                : "Réduire la barre latérale"
            }
            title={
              reduit
                ? "Agrandir le menu"
                : "Réduire le menu"
            }
          >
            {reduit ? (
              <PanelLeftOpen size={19} />
            ) : (
              <PanelLeftClose size={19} />
            )}
          </button>

          {/* FERMETURE DU MENU MOBILE */}

          <button
            type="button"
            className="pf-sidebar-close-mobile"
            onClick={() => setMobileOuvert(false)}
            aria-label="Fermer"
          >
            <X size={21} />
          </button>
        </div>

        {/* TITRE DU MENU */}

        <div className="pf-sidebar-section-label">
          NAVIGATION PRINCIPALE
        </div>

        {/* LIENS DE NAVIGATION */}

        <nav
          className="pf-sidebar-nav"
          aria-label="Navigation principale"
        >
          {MENU_ITEMS.map((item) => {
            const Icone = item.icone;

            return (
              <NavLink
                key={item.chemin}
                to={item.chemin}
                end={item.fin}
                title={reduit ? item.nom : undefined}
                className={({ isActive }) =>
                  [
                    "pf-sidebar-link",
                    isActive
                      ? "pf-sidebar-link--active"
                      : ""
                  ].filter(Boolean).join(" ")
                }
              >
                <span className="pf-sidebar-link-icon">
                  <Icone size={20} strokeWidth={1.9} />
                </span>

                <span className="pf-sidebar-link-text">
                  {item.nom}
                </span>

                <ChevronRight
                  size={15}
                  className="pf-sidebar-link-arrow"
                />
              </NavLink>
            );
          })}
        </nav>

        {/* ESPACE FLEXIBLE */}

        <div className="pf-sidebar-spacer" />

        {/* PIED DU MENU */}

        <div className="pf-sidebar-footer">
          <div className="pf-sidebar-footer-icon">
            <Fish size={19} />
          </div>

          <div className="pf-sidebar-footer-text">
            <strong>Pisciculture intelligente</strong>
            <span>Supervision et analyse IoT</span>
          </div>
        </div>
      </aside>
    </>
  );
}
