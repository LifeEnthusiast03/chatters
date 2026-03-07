import { useState } from "react";
import { Mail, Lock, LogIn, UserPlus } from "lucide-react";

interface LoginProps {
  onLogin: (email: string, password: string) => void;
  onSignup?: (email: string, password: string) => void;
}

export default function Login({ onLogin, onSignup }: LoginProps) {
  const [isSignup, setIsSignup] = useState(false);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    setError("");

    if (isSignup && password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }

    setLoading(true);

    try {
      await new Promise((r) => setTimeout(r, 800));

      if (isSignup) {
        onSignup?.(email, password);
      } else {
        onLogin(email, password);
      }

    } catch {
      setError("Authentication failed");
    }

    setLoading(false);
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-[#0b0d1a] via-[#0f1225] to-[#070812]">

      <div className="w-full max-w-md p-8 rounded-2xl border border-white/10 bg-white/[0.04] backdrop-blur-xl shadow-2xl">

        {/* Title */}
        <div className="mb-8 text-center">
          <h1 className="text-xl font-bold text-white">MessageHub</h1>
          <p className="text-gray-400 text-sm mt-1">
            {isSignup ? "Create your account" : "Sign in to access your messages"}
          </p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-5">

          {/* Email */}
          <div>
            <label className="text-xs text-gray-400 mb-1 block">
              Email
            </label>

            <div className="flex items-center gap-2 px-3 py-2 rounded-lg border border-white/10 bg-white/5">
              <Mail size={16} className="text-gray-400" />

              <input
                type="email"
                required
                placeholder="you@example.com"
                className="bg-transparent outline-none text-sm flex-1 text-gray-200"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
          </div>

          {/* Password */}
          <div>
            <label className="text-xs text-gray-400 mb-1 block">
              Password
            </label>

            <div className="flex items-center gap-2 px-3 py-2 rounded-lg border border-white/10 bg-white/5">
              <Lock size={16} className="text-gray-400" />

              <input
                type="password"
                required
                placeholder="••••••••"
                className="bg-transparent outline-none text-sm flex-1 text-gray-200"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>
          </div>

          {/* Confirm Password (Signup only) */}
          {isSignup && (
            <div>
              <label className="text-xs text-gray-400 mb-1 block">
                Confirm Password
              </label>

              <div className="flex items-center gap-2 px-3 py-2 rounded-lg border border-white/10 bg-white/5">
                <Lock size={16} className="text-gray-400" />

                <input
                  type="password"
                  required
                  placeholder="••••••••"
                  className="bg-transparent outline-none text-sm flex-1 text-gray-200"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                />
              </div>
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="text-xs text-red-400">
              {error}
            </div>
          )}

          {/* Button */}
          <button
            disabled={loading}
            className="w-full py-2.5 rounded-lg text-sm font-semibold flex items-center justify-center gap-2
            bg-gradient-to-r from-indigo-500 to-violet-600
            hover:opacity-90 transition"
          >
            {isSignup ? <UserPlus size={16} /> : <LogIn size={16} />}
            {loading
              ? "Processing..."
              : isSignup
              ? "Create Account"
              : "Sign In"}
          </button>

        </form>

        {/* Toggle Login / Signup */}
        <div className="text-center mt-6 text-sm text-gray-400">

          {isSignup ? "Already have an account?" : "Don't have an account?"}

          <button
            onClick={() => {
              setIsSignup(!isSignup);
              setError("");
            }}
            className="ml-2 text-indigo-400 hover:text-indigo-300 font-semibold"
          >
            {isSignup ? "Sign In" : "Create Account"}
          </button>

        </div>

        {/* Footer */}
        <p className="text-xs text-gray-500 text-center mt-4">
          Demo mode: any credentials work
        </p>

      </div>

    </div>
  );
}