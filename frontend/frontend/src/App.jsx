import { useEffect, useState } from "react";
import { getBassins } from "./services/api";

function App() {
  // Stocker les bassins récupérés depuis PostgreSQL.
  const [bassins, setBassins] = useState([]);

  // Stocker les erreurs éventuelles.
  const [erreur, setErreur] = useState("");

  useEffect(() => {
    // Appeler FastAPI au chargement de la page.
    getBassins()
      .then((donnees) => setBassins(donnees))
      .catch(() => {
        setErreur("Impossible de charger les bassins.");
      });
  }, []);

  return (
    <main style={{ padding: "30px" }}>
      <h1>Pisciculture intelligente</h1>
      <h2>Liste des bassins</h2>

      {erreur && <p style={{ color: "red" }}>{erreur}</p>}

      <ul>
        {bassins.map((bassin) => (
          <li key={bassin.id}>
            {bassin.code} — {bassin.nom}
            {" "}({bassin.capacite_litres} litres)
          </li>
        ))}
      </ul>
    </main>
  );
}

export default App;
