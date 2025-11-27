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
  const [selectedJobUrl, setSelectedJobUrl] = useState<string | null>(null);
  const [checkingIndex, setCheckingIndex] = useState<number | null>(null);
  const [appliedStatus, setAppliedStatus] = useState<Record<number, 'applied' | 'not_applied' | 'error'>>({});
  const jobUrlIndex =
    headers.findIndex((h) => h.toLowerCase().trim() === 'job url') !== -1
      ? headers.findIndex((h) => h.toLowerCase().trim() === 'job url')
      : 2; // fallback to column C
  const companyIndex =
    headers.findIndex((h) => h.toLowerCase().includes('company')) !== -1
      ? headers.findIndex((h) => h.toLowerCase().includes('company'))
      : 0;
  const appliedDateIndex =
    headers.findIndex((h) => h.toLowerCase().includes('date')) !== -1
      ? headers.findIndex((h) => h.toLowerCase().includes('date'))
      : 1;

  // Only show a compact set of columns in the UI table
  const positionIndex =
    headers.findIndex((h) => h.toLowerCase().includes('position')) !== -1
      ? headers.findIndex((h) => h.toLowerCase().includes('position'))
      : 0;
  const visibleColumnIndices = [appliedDateIndex, companyIndex, positionIndex, jobUrlIndex];

  const handleCheckApplied = async (rowIndex: number) => {
    if (!profileId) return;
    const row = rows[rowIndex];
    const company = row[companyIndex];
    const appliedDate = row[appliedDateIndex];
    if (!company || !appliedDate) {
      return;
    }
    try {
      setCheckingIndex(rowIndex);
      setError(null);
      const res = await api.post<{ applied: boolean }>(
        `/profiles/${profileId}/gmail/check-application`,
        {
          company_name: company,
          applied_date: appliedDate,
          sheet_id: selectedSheetId,
          row_index: rowIndex,
          position: row[positionIndex],
          job_url: row[jobUrlIndex]
        }
      );
      setAppliedStatus((prev) => ({
        ...prev,
        [rowIndex]: res.data.applied ? 'applied' : 'not_applied'
      }));
    } catch (err: any) {
      setAppliedStatus((prev) => ({ ...prev, [rowIndex]: 'error' }));
      setError(err?.response?.data?.message ?? 'Failed to check Gmail for this position');
    } finally {
      setCheckingIndex(null);
    }
  };

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
        statuses?: (string | null)[];
      }>(`/profiles/${profileId}/sheets/${sheetId}`);
      setHeaders(res.data.headers);
      setRows(res.data.rows);
      if (res.data.statuses && Array.isArray(res.data.statuses)) {
        const statusMap: Record<number, 'applied' | 'not_applied' | 'error'> = {};
        res.data.statuses.forEach((s, idx) => {
          if (s === 'applied' || s === 'not_applied') {
            statusMap[idx] = s;
          }
        });
        setAppliedStatus(statusMap);
      } else {
        setAppliedStatus({});
      }
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

        <div className="md:col-span-3 space-y-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
            <h3 className="text-sm font-semibold text-slate-200 mb-3">
              Sheet content (columns A–G)
            </h3>
            {loading && rows.length === 0 && (
              <p className="text-sm text-slate-400">Loading...</p>
            )}
            {!loading && rows.length === 0 && (
              <p className="text-sm text-slate-400">No data found in this sheet.</p>
            )}

            {rows.length > 0 && (
              <div className="overflow-auto max-h-64">
                <table className="min-w-full text-xs border border-slate-800">
                  <thead className="bg-slate-800">
                    <tr>
                      {visibleColumnIndices.map((idx) => (
                        <th
                          key={idx}
                          className="px-3 py-2 text-left font-semibold border-b border-slate-700"
                        >
                          {headers[idx]}
                        </th>
                      ))}
                      <th className="px-3 py-2 text-left font-semibold border-b border-slate-700">
                        Applied?
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row, idx) => {
                      const status = appliedStatus[idx];
                      const baseColor =
                        status === 'applied'
                          ? 'bg-emerald-900/40'
                          : status === 'not_applied'
                            ? 'bg-red-900/20'
                            : status === 'error'
                              ? 'bg-red-900/40'
                              : idx % 2 === 0
                                ? 'bg-slate-950'
                                : 'bg-slate-900';

                      return (
                        <tr
                          key={idx}
                          className={`${baseColor} cursor-pointer hover:bg-slate-800/70`}
                          onClick={() => {
                            const url = row[jobUrlIndex];
                            if (url) {
                              setSelectedJobUrl(url);
                            }
                          }}
                        >
                        {visibleColumnIndices.map((cidx) => {
                          const cell = row[cidx];
                          const isJobUrl = cidx === jobUrlIndex;
                          return (
                            <td
                              key={cidx}
                              className={`px-3 py-1 border-b border-slate-800 align-top max-w-xs break-words ${
                                isJobUrl ? 'text-sky-300' : ''
                              }`}
                            >
                              {cell}
                            </td>
                          );
                        })}
                        <td className="px-3 py-1 border-b border-slate-800 align-top whitespace-nowrap">
                          {appliedStatus[idx] === 'applied' && (
                            <span className="text-emerald-400 text-xs font-semibold">Applied</span>
                          )}
                          {appliedStatus[idx] === 'not_applied' && (
                            <span className="text-slate-300 text-xs">Not found</span>
                          )}
                          {appliedStatus[idx] === 'error' && (
                            <span className="text-red-400 text-xs">Error</span>
                          )}
                          {!appliedStatus[idx] && (
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                void handleCheckApplied(idx);
                              }}
                              className="text-xs text-sky-400 hover:text-sky-300"
                              disabled={checkingIndex === idx}
                            >
                              {checkingIndex === idx ? 'Checking...' : 'Check'}
                            </button>
                          )}
                        </td>
                      </tr>
                    );})}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 h-[560px]">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-semibold text-slate-200">External job page preview</h3>
              {selectedJobUrl && (
                <a
                  href={selectedJobUrl}
                  target="_blank"
                  rel="noreferrer noopener"
                  className="text-xs text-sky-400 hover:text-sky-300"
                >
                  Open in new tab
                </a>
              )}
            </div>
            {!selectedJobUrl && (
              <p className="text-sm text-slate-400">
                Select a row&apos;s Job Url to preview the external job page here.
              </p>
            )}
            {selectedJobUrl && (
              <iframe
                src={selectedJobUrl}
                title="Job page preview"
                className="w-full h-full rounded-lg border border-slate-800 bg-white"
              />
            )}
          </div>
        </div>
      </div>
    </div>
  );
};


