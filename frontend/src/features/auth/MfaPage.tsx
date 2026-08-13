import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../lib/api";
import { useAuth } from "./useAuth";

export function MfaPage() {
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const { refresh } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await api.verifyMfa(code);
      await refresh();
      navigate("/");
    } catch {
      setError("Código inválido");
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <h1>Verificación en dos pasos</h1>
      <input value={code} onChange={(e) => setCode(e.target.value)} placeholder="Código de 6 dígitos" />
      {error && <p role="alert">{error}</p>}
      <button type="submit">Verificar</button>
    </form>
  );
}
