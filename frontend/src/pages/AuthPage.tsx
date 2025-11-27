import { FormEvent, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import api from '../api/client';

type Mode = 'signin' | 'register';

export const AuthPage = () => {
  const [mode, setMode] = useState<Mode>('signin');
  const [userId, setUserId] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      const endpoint = mode === 'signin' ? '/auth/login' : '/auth/register';
      const res = await api.post(endpoint, { user_id: userId, user_password: password });
      login(res.data.token);
      navigate('/profile');
    } catch (err: any) {
      setError(err?.response?.data?.message ?? 'Something went wrong');
    }
  };

  return (
    <div className="flex flex-col items-center pt-24">
      <h1 className="text-3xl font-semibold mb-8">Outbidder Dashboard</h1>
      <div className="w-full max-w-md bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-xl">
        <div className="flex mb-6 space-x-2">
          <button
            className={`flex-1 py-2 rounded-lg text-sm font-medium ${
              mode === 'signin' ? 'bg-sky-500 text-white' : 'bg-slate-800 text-slate-300'
            }`}
            onClick={() => setMode('signin')}
          >
            Sign In
          </button>
          <button
            className={`flex-1 py-2 rounded-lg text-sm font-medium ${
              mode === 'register' ? 'bg-sky-500 text-white' : 'bg-slate-800 text-slate-300'
            }`}
            onClick={() => setMode('register')}
          >
            Register
          </button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm mb-1 text-slate-300">User ID</label>
            <input
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
              className="w-full rounded-lg bg-slate-950 border border-slate-700 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
            />
          </div>
          <div>
            <label className="block text-sm mb-1 text-slate-300">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-lg bg-slate-950 border border-slate-700 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
            />
          </div>
          {error && <p className="text-sm text-red-400">{error}</p>}
          <button
            type="submit"
            className="w-full py-2 rounded-lg bg-sky-500 hover:bg-sky-600 text-sm font-medium text-white"
          >
            {mode === 'signin' ? 'Sign In' : 'Create Account'}
          </button>
        </form>
      </div>
    </div>
  );
};


