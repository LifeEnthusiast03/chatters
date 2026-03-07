import Login from "../components/Login.tsx";
import { useAuth } from "../context/AuthContext";
import { useNavigate } from "react-router-dom";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleLogin = async (email: string) => {
    await login(email, "password"); // Simple mock login for now as AuthContext doesn't check password
    navigate("/");
  };

  return <Login onLogin={handleLogin} />;
}
