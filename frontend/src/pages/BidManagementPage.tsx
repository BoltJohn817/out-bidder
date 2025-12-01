import { useEffect, useState } from 'react';
import api from '../api/client';
import { ErrorMessage } from '../components/ErrorMessage';
import { EmptyState } from '../components/EmptyState';
import { LoadingSpinner } from '../components/LoadingSpinner';

interface Bid {
  _id?: string;
  title: string;
  client: string;
  profileId?: string;
  status: 'draft' | 'submitted' | 'won' | 'lost';
}

export const BidManagementPage = () => {
  const [bids, setBids] = useState<Bid[]>([]);
  const [form, setForm] = useState<Bid>({
    title: '',
    client: '',
    status: 'draft'
  });
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const loadBids = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.get<{ bids: Bid[] }>('/bids/');
      setBids(res.data.bids);
    } catch (err: any) {
      setError(err?.response?.data?.message ?? 'Failed to load bids');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadBids();
  }, []);

  const handleCreate = () => {
    setError(null);
    api
      .post('/bids/', {
        title: form.title,
        client: form.client,
        status: form.status
      })
      .then(() => {
        setForm({ title: '', client: '', status: 'draft' });
        void loadBids();
      })
      .catch((err) => {
        setError(err?.response?.data?.message ?? 'Failed to create bid');
      });
  };

  return (
    <div>
      <h2 className="text-2xl font-semibold mb-4">Bid Management</h2>
      <p className="text-slate-400 text-sm mb-6">
        Track bids created using your profiles and Google spreadsheets.
      </p>

      <ErrorMessage message={error} className="mb-4" />

      <div className="grid gap-6 md:grid-cols-2">
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-4">
          <div>
            <label className="block text-sm mb-1 text-slate-300">Bid title</label>
            <input
              className="w-full rounded-lg bg-slate-950 border border-slate-700 px-3 py-2 text-sm"
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
            />
          </div>
          <div>
            <label className="block text-sm mb-1 text-slate-300">Client</label>
            <input
              className="w-full rounded-lg bg-slate-950 border border-slate-700 px-3 py-2 text-sm"
              value={form.client}
              onChange={(e) => setForm({ ...form, client: e.target.value })}
            />
          </div>
          <div>
            <label className="block text-sm mb-1 text-slate-300">Status</label>
            <select
              className="w-full rounded-lg bg-slate-950 border border-slate-700 px-3 py-2 text-sm"
              value={form.status}
              onChange={(e) =>
                setForm({ ...form, status: e.target.value as Bid['status'] })
              }
            >
              <option value="draft">Draft</option>
              <option value="submitted">Submitted</option>
              <option value="won">Won</option>
              <option value="lost">Lost</option>
            </select>
          </div>
          <button
            type="button"
            onClick={handleCreate}
            className="w-full py-2 rounded-lg bg-sky-500 hover:bg-sky-600 text-sm font-medium text-white"
          >
            Create Bid
          </button>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-slate-200">Bids</h3>
            <button
              type="button"
              onClick={() => void loadBids()}
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
          {!loading && bids.length === 0 && (
            <EmptyState message="No bids yet. Create your first one." />
          )}
          <ul className="space-y-2">
            {bids.map((bid) => (
              <li
                key={bid._id}
                className="flex items-center justify-between text-sm bg-slate-950 border border-slate-800 rounded-lg px-3 py-2"
              >
                <div>
                  <p className="font-medium text-slate-100">{bid.title}</p>
                  <p className="text-xs text-slate-400">{bid.client}</p>
                </div>
                <span className="text-xs px-2 py-1 rounded-full bg-slate-800 text-slate-200 capitalize">
                  {bid.status}
                </span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
};


