import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/client';
import { useAuth } from '../hooks/useAuth';
import { ErrorMessage } from '../components/ErrorMessage';
import { EmptyState } from '../components/EmptyState';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { normalizeSpreadsheetInput } from '../utils/spreadsheet';

type TechStackCategory =
  | 'frontend'
  | 'backend'
  | 'fullstack'
  | 'web'
  | 'ai'
  | 'data_engineering'
  | 'devops'
  | 'language';

type EmailProvider = 'gmail' | 'outlook';

interface ProfileForm {
  name: string;
  googleEmail: string;
  spreadsheetId: string;
  techstack: TechStackCategory[];
  emailProvider: EmailProvider;
}

interface ProfileApi {
  _id: string;
  name: string;
  google_email: string;
  spreadsheet_id: string;
  techstack: TechStackCategory[];
  email_provider?: EmailProvider;
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
    techstack: [],
    emailProvider: 'gmail'
  });
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [googleAuthUrl, setGoogleAuthUrl] = useState<string | null>(null);
  const [outlookAuthUrl, setOutlookAuthUrl] = useState<string | null>(null);
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
        techstack: p.techstack,
        emailProvider: p.email_provider || 'gmail'
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
      techstack: [],
      emailProvider: 'gmail'
    });
    setGoogleAuthUrl(null);
    setOutlookAuthUrl(null);
  };

  const handleSaveProfile = () => {
    setError(null);
    const payload = {
      name: form.name,
      google_email: form.googleEmail,
      spreadsheet_id: form.spreadsheetId,
      techstack: form.techstack,
      email_provider: form.emailProvider
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

  const handleOutlookAuth = () => {
    setError(null);
    setOutlookAuthUrl(null);
    api
      .post<{ auth_url: string }>('/profiles/outlook/auth-url', {
        name: form.name,
        google_email: form.googleEmail,
        spreadsheet_id: form.spreadsheetId,
        techstack: form.techstack,
        email_provider: form.emailProvider,
        profile_id: selectedProfileId ?? undefined
      })
      .then((res) => {
        if (res.data.auth_url) {
          setOutlookAuthUrl(res.data.auth_url);
        } else {
          setError('Failed to get Outlook auth URL');
        }
      })
      .catch((err) => {
        setError(err?.response?.data?.message ?? 'Failed to start Outlook auth');
      });
  };

  const handleSignOut = () => {
    // Best-effort notify backend, but always clear local auth and redirect
    void api.post('/auth/logout').finally(() => {
      logout();
      navigate('/auth');
    });
  };

  const handleDeleteProfile = async (profileId: string, profileName: string) => {
    if (!confirm(`Are you sure you want to delete the profile "${profileName}"? This action cannot be undone.`)) {
      return;
    }

    try {
      setError(null);
      await api.delete(`/profiles/${profileId}`);
      
      // If the deleted profile was selected, reset the form
      if (selectedProfileId === profileId) {
        resetForm();
      }
      
      // Reload profiles list
      void loadProfiles();
    } catch (err: any) {
      setError(err?.response?.data?.message ?? 'Failed to delete profile');
    }
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

      <ErrorMessage message={error} className="mb-4" />

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
            <label className="block text-sm mb-1 text-slate-300">Email address</label>
            <input
              className="w-full rounded-lg bg-slate-950 border border-slate-700 px-3 py-2 text-sm"
              value={form.googleEmail}
              onChange={(e) => setForm({ ...form, googleEmail: e.target.value })}
              placeholder="your@email.com"
            />
          </div>
          <div>
            <label className="block text-sm mb-1 text-slate-300">Email provider</label>
            <select
              className="w-full rounded-lg bg-slate-950 border border-slate-700 px-3 py-2 text-sm"
              value={form.emailProvider}
              onChange={(e) => setForm({ ...form, emailProvider: e.target.value as EmailProvider })}
            >
              <option value="gmail">Gmail</option>
              <option value="outlook">Outlook</option>
            </select>
          </div>
          <div>
            <label className="block text-sm mb-1 text-slate-300">Spreadsheet ID</label>
            <input
              className="w-full rounded-lg bg-slate-950 border border-slate-700 px-3 py-2 text-sm"
              value={form.spreadsheetId}
              onChange={(e) =>
                setForm({
                  ...form,
                  spreadsheetId: normalizeSpreadsheetInput(e.target.value)
                })
              }
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
          <div className="flex flex-col gap-2">
            {
              selectedProfileId ? (
                <button
                  type="button"
                  onClick={handleSaveProfile}
                  className="w-full py-2 rounded-lg bg-sky-500 hover:bg-sky-600 text-sm font-medium text-white"
                >
                  Update Profile
                </button>
              ) : (
                null
              )
            }
            <div className="flex flex-col sm:flex-row gap-2">
              {form.emailProvider === 'gmail' ? (
                <button
                  type="button"
                  onClick={handleGoogleAuth}
                  className="flex-1 py-2 rounded-lg bg-emerald-500 hover:bg-emerald-600 text-sm font-medium text-white"
                >
                  {selectedProfileId ? 'Update Gmail access' : 'Connect Gmail'}
                </button>
              ) : (
                <button
                  type="button"
                  onClick={handleOutlookAuth}
                  className="flex-1 py-2 rounded-lg bg-blue-500 hover:bg-blue-600 text-sm font-medium text-white"
                >
                  {selectedProfileId ? 'Update Outlook access' : 'Connect Outlook'}
                </button>
              )}
            </div>
            <p className="text-xs text-slate-400 mt-1">
              Note: Google Sheets access is required for spreadsheet functionality. {form.emailProvider === 'gmail' ? 'Gmail connection also provides Sheets access.' : 'Outlook is only used for email checking.'}
            </p>
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

          {outlookAuthUrl && (
            <div className="mt-3 space-y-2">
              <p className="text-xs text-slate-300">
                Copy this URL and open it in your browser to complete Outlook authentication:
              </p>
              <div className="flex gap-2 items-center">
                <input
                  readOnly
                  value={outlookAuthUrl}
                  className="flex-1 rounded-lg bg-slate-950 border border-slate-700 px-3 py-1 text-[11px]"
                  onFocus={(e) => e.target.select()}
                />
                <button
                  type="button"
                  onClick={() => {
                    void navigator.clipboard.writeText(outlookAuthUrl);
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
        {loading && (
          <div className="flex items-center gap-2 text-sm text-slate-400">
            <LoadingSpinner size="sm" />
            <span>Loading...</span>
          </div>
        )}
        {!loading && profiles.length === 0 && (
          <EmptyState message="No profiles yet." />
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
                          techstack: p.techstack,
                          emailProvider: p.emailProvider
                        });
                        setGoogleAuthUrl(null);
                        setOutlookAuthUrl(null);
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
                <div className="mt-2 flex justify-end gap-2">
                  <button
                    type="button"
                    onClick={() => navigate(`/profiles/${p._id}/sheets`)}
                    className="text-xs text-sky-400 hover:text-sky-300"
                  >
                    Manage sheets
                  </button>
                  <button
                    type="button"
                    onClick={() => void handleDeleteProfile(p._id, p.name)}
                    className="text-xs text-red-400 hover:text-red-300"
                  >
                    Delete
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


