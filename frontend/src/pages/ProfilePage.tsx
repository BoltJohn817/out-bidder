import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/client';
import { useAuth } from '../hooks/useAuth';

type TechStackCategory =
  | 'frontend'
  | 'backend'
  | 'fullstack'
  | 'web'
  | 'ai'
  | 'data_engineering'
  | 'devops'
  | 'language';

interface ProfileForm {
  name: string;
  googleEmail: string;
  spreadsheetId: string;
  techstack: TechStackCategory[];
}

interface ProfileApi {
  _id: string;
  name: string;
  google_email: string;
  spreadsheet_id: string;
  techstack: TechStackCategory[];
}

interface Profile extends ProfileForm {
  _id: string;
}

const AVAILABLE_TECHSTACK: { id: TechStackCategory; label: string }[] = [
  { id: 'frontend', label: 'Frontend' },
  { id: 'backend', label: 'Backend' },
  { id: 'fullstack', label: 'Fullstack' },
  { id: 'web', label: 'Web' },
  { id: 'ai', label: 'AI' },
  { id: 'data_engineering', label: 'Data Engineering' },
  { id: 'devops', label: 'DevOps' },
  { id: 'language', label: 'Programming Languages' }
];

export const ProfilePage = () => {
  const navigate = useNavigate();
  const [form, setForm] = useState<ProfileForm>({
    name: '',
    googleEmail: '',
    spreadsheetId: '',
    techstack: []
  });
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [googleAuthUrl, setGoogleAuthUrl] = useState<string | null>(null);
  const [selectedProfileId, setSelectedProfileId] = useState<string | null>(null);
  const { logout } = useAuth();

  const loadProfiles = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.get<{ profiles: ProfileApi[] }>('/profiles/');
      const mapped: Profile[] = res.data.profiles.map((p) => ({
        _id: p._id,
        name: p.name,
        googleEmail: p.google_email,
        spreadsheetId: p.spreadsheet_id,
        techstack: p.techstack
      }));
      setProfiles(mapped);
    } catch (err: any) {
      setError(err?.response?.data?.message ?? 'Failed to load profiles');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadProfiles();
  }, []);

  const toggleTech = (id: TechStackCategory) => {
    setForm((prev) => ({
      ...prev,
      techstack: prev.techstack.includes(id)
        ? prev.techstack.filter((t) => t !== id)
        : [...prev.techstack, id]
    }));
  };

  const resetForm = () => {
    setSelectedProfileId(null);
    setForm({
      name: '',
      googleEmail: '',
      spreadsheetId: '',
      techstack: []
    });
    setGoogleAuthUrl(null);
  };

  const handleSaveProfile = () => {
    setError(null);
    const payload = {
      name: form.name,
      google_email: form.googleEmail,
      spreadsheet_id: form.spreadsheetId,
      techstack: form.techstack
    };

    const request = selectedProfileId
      ? api.put(`/profiles/${selectedProfileId}`, payload)
      : api.post('/profiles/', payload);

    request
      .then(() => {
        resetForm();
        void loadProfiles();
      })
      .catch((err) => {
        setError(err?.response?.data?.message ?? 'Failed to save profile');
      });
  };

  const handleGoogleAuth = () => {
    setError(null);
    setGoogleAuthUrl(null);
    api
      .post<{ auth_url: string }>('/profiles/google/auth-url', {
        name: form.name,
        google_email: form.googleEmail,
        spreadsheet_id: form.spreadsheetId,
        techstack: form.techstack,
        profile_id: selectedProfileId ?? undefined
      })
      .then((res) => {
        if (res.data.auth_url) {
          setGoogleAuthUrl(res.data.auth_url);
        } else {
          setError('Failed to get Google auth URL');
        }
      })
      .catch((err) => {
        setError(err?.response?.data?.message ?? 'Failed to start Google auth');
      });
  };

  const handleSignOut = () => {
    // Best-effort notify backend, but always clear local auth and redirect
    void api.post('/auth/logout').finally(() => {
      logout();
      navigate('/auth');
    });
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-2xl font-semibold">Profile Management</h2>
          <p className="text-slate-400 text-sm mt-1">
            Configure profiles that map a Google account and spreadsheet with a tech stack focus.
          </p>
        </div>
        <button
          type="button"
          onClick={handleSignOut}
          className="text-xs px-3 py-1.5 rounded-lg border border-slate-700 text-slate-200 hover:bg-slate-800"
        >
          Sign out
        </button>
      </div>

      {error && <p className="text-sm text-red-400 mb-4">{error}</p>}

      <div className="grid gap-6 md:grid-cols-1">
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex-1 mr-2">
              <label className="block text-sm mb-1 text-slate-300">Profile name</label>
              <input
                className="w-full rounded-lg bg-slate-950 border border-slate-700 px-3 py-2 text-sm"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
              />
            </div>
            {selectedProfileId && (
              <button
                type="button"
                onClick={resetForm}
                className="text-xs text-slate-300 hover:text-slate-100 mt-6"
              >
                New profile
              </button>
            )}
          </div>
          <div>
            <label className="block text-sm mb-1 text-slate-300">Google email</label>
            <input
              className="w-full rounded-lg bg-slate-950 border border-slate-700 px-3 py-2 text-sm"
              value={form.googleEmail}
              onChange={(e) => setForm({ ...form, googleEmail: e.target.value })}
            />
          </div>
          <div>
            <label className="block text-sm mb-1 text-slate-300">Spreadsheet ID</label>
            <input
              className="w-full rounded-lg bg-slate-950 border border-slate-700 px-3 py-2 text-sm"
              value={form.spreadsheetId}
              onChange={(e) => setForm({ ...form, spreadsheetId: e.target.value })}
            />
          </div>
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-4">
            <p className="text-sm text-slate-300">Tech stack focus</p>
            <div className="flex flex-wrap gap-2">
              {AVAILABLE_TECHSTACK.map((item) => {
                const active = form.techstack.includes(item.id);
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => toggleTech(item.id)}
                    className={`px-3 py-1 rounded-full text-xs font-medium border ${
                      active
                        ? 'bg-sky-500/20 border-sky-400 text-sky-200'
                        : 'bg-slate-950 border-slate-700 text-slate-300'
                    }`}
                  >
                    {item.label}
                  </button>
                );
              })}
            </div>

          </div>
          <div className="flex flex-col sm:flex-row gap-2">
            <button
              type="button"
              onClick={handleSaveProfile}
              className="flex-1 py-2 rounded-lg bg-sky-500 hover:bg-sky-600 text-sm font-medium text-white"
            >
              {selectedProfileId ? 'Update Profile' : 'Create Profile'}
            </button>
            <button
              type="button"
              onClick={handleGoogleAuth}
              className="flex-1 py-2 rounded-lg bg-emerald-500 hover:bg-emerald-600 text-sm font-medium text-white"
            >
              {selectedProfileId ? 'Update Google access' : 'Connect Google (Gmail + Sheets)'}
            </button>
          </div>

          {googleAuthUrl && (
            <div className="mt-3 space-y-2">
              <p className="text-xs text-slate-300">
                Copy this URL and open it in your browser to complete Google authentication:
              </p>
              <div className="flex gap-2 items-center">
                <input
                  readOnly
                  value={googleAuthUrl}
                  className="flex-1 rounded-lg bg-slate-950 border border-slate-700 px-3 py-1 text-[11px]"
                  onFocus={(e) => e.target.select()}
                />
                <button
                  type="button"
                  onClick={() => {
                    void navigator.clipboard.writeText(googleAuthUrl);
                  }}
                  className="px-3 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs text-slate-100"
                >
                  Copy
                </button>
              </div>
            </div>
          )}
        </div>

      </div>

      <div className="mt-8 bg-slate-900 border border-slate-800 rounded-xl p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-slate-200">Existing profiles</h3>
          <button
            type="button"
            onClick={() => void loadProfiles()}
            className="text-xs text-sky-400 hover:text-sky-300"
          >
            Refresh
          </button>
        </div>
        {loading && <p className="text-sm text-slate-400">Loading...</p>}
        {!loading && profiles.length === 0 && (
          <p className="text-sm text-slate-400">No profiles yet.</p>
        )}
        <ul className="space-y-2">
          {profiles.map((p) => {
            const isSelected = selectedProfileId === p._id;
            return (
              <li
                key={p._id}
                className={`bg-slate-950 border rounded-lg px-3 py-2 text-sm cursor-pointer ${
                  isSelected ? 'border-sky-500' : 'border-slate-800'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div>
                    <button
                      type="button"
                      className="font-medium text-slate-100 text-left hover:text-sky-300"
                      onClick={() => {
                        setSelectedProfileId(p._id);
                        setForm({
                          name: p.name,
                          googleEmail: p.googleEmail,
                          spreadsheetId: p.spreadsheetId,
                          techstack: p.techstack
                        });
                        setGoogleAuthUrl(null);
                      }}
                    >
                      {p.name}
                    </button>
                    <p className="text-xs text-slate-400 mt-0.5">{p.googleEmail}</p>
                  </div>
                  <p className="text-xs text-slate-400 truncate max-w-[180px]">
                    Sheet: {p.spreadsheetId}
                  </p>
                </div>
                <div className="mt-2 flex flex-wrap gap-1">
                  {p.techstack.map((t) => (
                    <span
                      key={t}
                      className="text-[10px] px-2 py-0.5 rounded-full bg-slate-800 text-slate-200"
                    >
                      {t}
                    </span>
                  ))}
                </div>
                <div className="mt-2 flex justify-end">
                  <button
                    type="button"
                    onClick={() => navigate(`/profiles/${p._id}/sheets`)}
                    className="text-xs text-sky-400 hover:text-sky-300"
                  >
                    Manage sheets
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
};


