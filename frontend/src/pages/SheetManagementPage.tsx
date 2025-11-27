import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import api from '../api/client';

interface RouteParams {
  profileId: string;
}

interface SheetSummary {
  sheet_id: number;
  title: string;
  index: number;
}

export const SheetManagementPage = () => {
  const { profileId } = useParams<RouteParams>();
  const navigate = useNavigate();

  const [sheets, setSheets] = useState<SheetSummary[]>([]);
  const [selectedSheetId, setSelectedSheetId] = useState<number | null>(null);
  const [headers, setHeaders] = useState<string[]>([]);
  const [rows, setRows] = useState<string[][]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadSheets = async () => {
    if (!profileId) return;
    try {
      setLoading(true);
      setError(null);
      const res = await api.get<{ sheets: SheetSummary[] }>(`/profiles/${profileId}/sheets`);
      setSheets(res.data.sheets);
      if (res.data.sheets.length > 0 && selectedSheetId === null) {
        setSelectedSheetId(res.data.sheets[0].sheet_id);
      }
    } catch (err: any) {
      setError(err?.response?.data?.message ?? 'Failed to load sheets');
    } finally {
      setLoading(false);
    }
  };

  const loadSheetValues = async (sheetId: number) => {
    if (!profileId) return;
    try {
      setLoading(true);
      setError(null);
      const res = await api.get<{
        headers: string[];
        rows: string[][];
        title: string;
      }>(`/profiles/${profileId}/sheets/${sheetId}`);
      setHeaders(res.data.headers);
      setRows(res.data.rows);
    } catch (err: any) {
      setError(err?.response?.data?.message ?? 'Failed to load sheet values');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadSheets();
  }, [profileId]);

  useEffect(() => {
    if (selectedSheetId !== null) {
      void loadSheetValues(selectedSheetId);
    }
  }, [selectedSheetId]);

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-2xl font-semibold">Sheet Management</h2>
        <button
          type="button"
          onClick={() => navigate('/profile')}
          className="text-sm text-sky-400 hover:text-sky-300"
        >
          Back to profiles
        </button>
      </div>

      {error && <p className="text-sm text-red-400 mb-3">{error}</p>}

      <div className="grid md:grid-cols-4 gap-4">
        <div className="md:col-span-1 bg-slate-900 border border-slate-800 rounded-xl p-3">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-semibold text-slate-200">Sheets</h3>
            <button
              type="button"
              onClick={() => void loadSheets()}
              className="text-xs text-sky-400 hover:text-sky-300"
            >
              Refresh
            </button>
          </div>
          {loading && sheets.length === 0 && (
            <p className="text-xs text-slate-400">Loading...</p>
          )}
          {!loading && sheets.length === 0 && (
            <p className="text-xs text-slate-400">No sheets found for this spreadsheet.</p>
          )}
          <ul className="space-y-1 max-h-80 overflow-auto text-sm">
            {sheets.map((s) => (
              <li
                key={s.sheet_id}
                onClick={() => setSelectedSheetId(s.sheet_id)}
                className={`px-3 py-2 rounded-lg cursor-pointer ${
                  selectedSheetId === s.sheet_id
                    ? 'bg-sky-500/20 border border-sky-500 text-sky-100'
                    : 'bg-slate-950 border border-slate-800 text-slate-200'
                }`}
              >
                <p className="truncate">{s.title}</p>
              </li>
            ))}
          </ul>
        </div>

        <div className="md:col-span-3 bg-slate-900 border border-slate-800 rounded-xl p-4 overflow-auto">
          <h3 className="text-sm font-semibold text-slate-200 mb-3">
            Sheet content (columns A–G)
          </h3>
          {loading && rows.length === 0 && <p className="text-sm text-slate-400">Loading...</p>}
          {!loading && rows.length === 0 && (
            <p className="text-sm text-slate-400">No data found in this sheet.</p>
          )}

          {rows.length > 0 && (
            <div className="overflow-auto">
              <table className="min-w-full text-xs border border-slate-800">
                <thead className="bg-slate-800">
                  <tr>
                    {headers.map((h) => (
                      <th key={h} className="px-3 py-2 text-left font-semibold border-b border-slate-700">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row, idx) => (
                    <tr key={idx} className="odd:bg-slate-950 even:bg-slate-900">
                      {row.map((cell, cidx) => (
                        <td key={cidx} className="px-3 py-1 border-b border-slate-800 align-top">
                          {cell}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};


