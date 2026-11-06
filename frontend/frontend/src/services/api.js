
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
