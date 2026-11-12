
import { useEffect, useRef, useState } from "react";

/**
 * JOUR 12 — HOOK DE SUPERVISION WEBSOCKET
 *
 * Fonctionnalités :
 * - Connexion automatique à FastAPI.
 * - Réception des instantanés multi-bassins.
 * - Détection de déconnexion.
 * - Reconnexion automatique après 3 secondes.
 * - Nettoyage lorsque le composant est démonté.
 */

// Déterminer le protocole selon la page React.
// HTTPS nécessite normalement WSS.
const PROTOCOLE_WS =
  window.location.protocol === "https:" ? "wss:" : "ws:";

// Configuration locale de développement.
// En production, utiliser une URL configurée
// via une variable d'environnement Vite.
const URL_WEBSOCKET =
  import.meta.env.VITE_WS_URL ||
  `${PROTOCOLE_WS}//127.0.0.1:8000/api/v1/ws/supervision`;

const DELAI_RECONNEXION = 3000;

export default function useSupervisionWebSocket() {
  const [connecte, setConnecte] = useState(false);
  const [connexionEnCours, setConnexionEnCours] =
    useState(true);

  const [erreur, setErreur] = useState("");

  const [donnees, setDonnees] = useState({
    type: "supervision",
    date_serveur: null,
    nombre_bassins: 0,
    nombre_alertes_ouvertes: 0,
    bassins: [],
    alertes: []
  });

  const [derniereReception, setDerniereReception] =
    useState(null);

  const socketRef = useRef(null);

  useEffect(() => {
    let actif = true;
    let minuterieReconnexion = null;

    /**
     * Créer une nouvelle connexion.
     */
    function connecter() {
      if (!actif) return;

      setConnexionEnCours(true);

      const socket = new WebSocket(URL_WEBSOCKET);

      socketRef.current = socket;

      /**
       * Connexion établie.
       */
      socket.onopen = () => {
        if (!actif) return;

        setConnecte(true);
        setConnexionEnCours(false);
        setErreur("");
      };

      /**
       * Réception d'un message JSON.
       */
      socket.onmessage = (event) => {
        if (!actif) return;

        try {
          const message = JSON.parse(event.data);

          if (message.type === "supervision") {
            setDonnees(message);
            setDerniereReception(new Date());
            setErreur("");
          }

          if (message.type === "erreur") {
            setErreur(
              message.message ||
              "Erreur de supervision."
            );
          }

        } catch {
          setErreur(
            "Le serveur a envoyé un message invalide."
          );
        }
      };

      /**
       * Erreur réseau.
       */
      socket.onerror = () => {
        if (!actif) return;

        setErreur(
          "Connexion WebSocket indisponible."
        );
      };

      /**
       * Déconnexion.
       *
       * Préparer une reconnexion automatique.
       */
      socket.onclose = () => {
        if (!actif) return;

        setConnecte(false);
        setConnexionEnCours(false);

        minuterieReconnexion = setTimeout(
          connecter,
          DELAI_RECONNEXION
        );
      };
    }

    connecter();

    /**
     * Nettoyer les connexions et les délais
     * lorsque l'utilisateur quitte la page.
     */
    return () => {
      actif = false;

      if (minuterieReconnexion !== null) {
        clearTimeout(minuterieReconnexion);
      }

      if (socketRef.current) {
        socketRef.current.close();
      }
    };
  }, []);

  return {
    connecte,
    connexionEnCours,
    erreur,
    donnees,
    derniereReception
  };
}
