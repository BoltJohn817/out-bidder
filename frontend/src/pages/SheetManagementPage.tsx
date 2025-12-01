import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { io, Socket } from 'socket.io-client';
import api from '../api/client';
import { useSheetColumns } from '../hooks/useSheetColumns';
import { ErrorMessage } from '../components/ErrorMessage';
import { EmptyState } from '../components/EmptyState';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { SheetTableRow } from '../components/SheetTableRow';

interface SheetSummary {
  sheet_id: number;
  title: string;
  index: number;
}

export const SheetManagementPage = () => {
  const { profileId } = useParams<{ profileId: string }>();
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
  const [bulkChecking, setBulkChecking] = useState(false);
  const [bulkSummary, setBulkSummary] = useState<{ applied: number; notApplied: number; notChecked: number } | null>(
    null
  );

  const abortControllerRef = useRef<AbortController | null>(null);
  const currentSheetIdRef = useRef<number | null>(null);
  const requestIdRef = useRef<number>(0);

  const socket: Socket | null = useMemo(() => {
    // Assume backend websocket is served from same origin/port as API
    return io(import.meta.env.VITE_API_BASE_URL?.replace('/api', '') ?? 'http://localhost:5001', {
      autoConnect: false,
      transports: ['websocket']
    });
  }, []);
  // Parse column indices using the utility hook
  const columnIndices = useSheetColumns(headers);
  const { companyIndex, positionIndex, jobUrlIndex, appliedDateIndex } = columnIndices;
  
  // Only show a compact set of columns in the UI table
  const visibleColumnIndices = useMemo(
    () => Array.from(new Set([appliedDateIndex, companyIndex, positionIndex, jobUrlIndex])),
    [appliedDateIndex, companyIndex, positionIndex, jobUrlIndex]
  );

  const handleSelectUrl = useCallback((url: string) => {
    setSelectedJobUrl(url);
  }, []);

  const handleCheckApplied = useCallback(async (rowIndex: number) => {
    if (!profileId || selectedSheetId === null) return;
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
  }, [profileId, selectedSheetId, rows, companyIndex, appliedDateIndex, positionIndex, jobUrlIndex]);

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
    
    // Cancel any previous request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    
    // Increment request ID to track this request
    requestIdRef.current += 1;
    const currentRequestId = requestIdRef.current;
    
    // Create a new AbortController for this request
    const abortController = new AbortController();
    abortControllerRef.current = abortController;
    currentSheetIdRef.current = sheetId;
    
    try {
      setLoading(true);
      setError(null);
      const res = await api.get<{
        headers: string[];
        rows: string[][];
        title: string;
        statuses?: (string | null)[];
      }>(`/profiles/${profileId}/sheets/${sheetId}`, {
        signal: abortController.signal
      });
      
      // Ignore response if this request was superseded or aborted
      if (abortController.signal.aborted || currentSheetIdRef.current !== sheetId || requestIdRef.current !== currentRequestId) {
        return;
      }
      
      setHeaders(res.data.headers);
      setRows(res.data.rows);

      const totalRows = res.data.rows.length;
      if (res.data.statuses && Array.isArray(res.data.statuses)) {
        const statusMap: Record<number, 'applied' | 'not_applied' | 'error'> = {};
        let appliedCount = 0;
        let notAppliedCount = 0;
        res.data.statuses.forEach((s, idx) => {
          if (s === 'applied') {
            statusMap[idx] = 'applied';
            appliedCount += 1;
          } else if (s === 'not_applied') {
            statusMap[idx] = 'not_applied';
            notAppliedCount += 1;
          }
        });
        setAppliedStatus(statusMap);
        const notChecked = Math.max(totalRows - appliedCount - notAppliedCount, 0);
        setBulkSummary({ applied: appliedCount, notApplied: notAppliedCount, notChecked });
      } else {
        setAppliedStatus({});
        setBulkSummary({ applied: 0, notApplied: 0, notChecked: totalRows });
      }
    } catch (err: any) {
      // Ignore errors from aborted requests
      if (err.name === 'CanceledError' || err.name === 'AbortError' || abortController.signal.aborted) {
        return;
      }
      // Only set error if this is still the current request
      if (currentSheetIdRef.current === sheetId && requestIdRef.current === currentRequestId) {
        setError(err?.response?.data?.message ?? 'Failed to load sheet values');
      }
    } finally {
      // Only update loading state if this is still the current request
      if (currentSheetIdRef.current === sheetId && requestIdRef.current === currentRequestId) {
        setLoading(false);
      }
    }
  };

  useEffect(() => {
    void loadSheets();
  }, [profileId]);

  useEffect(() => {
    if (selectedSheetId !== null) {
      void loadSheetValues(selectedSheetId);
    }
    
    // Cleanup: cancel any pending request when selectedSheetId changes or component unmounts
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [selectedSheetId]);

  useEffect(() => {
    if (!socket) return;
    socket.connect();

    socket.on('connect_error', () => {
      // Silently ignore for now; page will still work without live updates
    });

    socket.on('application_check_progress', (payload: any) => {
      const { job_id, row_index, status } = payload;
      setAppliedStatus((prev) => {
        if (status === 'applied' || status === 'not_applied') {
          return { ...prev, [row_index]: status };
        }
        return prev;
      });
    });

    socket.on('application_check_complete', (payload: any) => {
      const { statuses } = payload;
      if (Array.isArray(statuses)) {
        const statusMap: Record<number, 'applied' | 'not_applied' | 'error'> = {};
        statuses.forEach((s: string | null, idx: number) => {
          if (s === 'applied' || s === 'not_applied') {
            statusMap[idx] = s;
          }
        });
        setAppliedStatus(statusMap);

        // Recompute summary based only on rows we actually render
        const appliedCount = Object.values(statusMap).filter((s) => s === 'applied').length;
        const notAppliedCount = Object.values(statusMap).filter((s) => s === 'not_applied').length;
        const notChecked = Math.max(rows.length - appliedCount - notAppliedCount, 0);
        setBulkSummary({ applied: appliedCount, notApplied: notAppliedCount, notChecked });
      } else {
        setBulkSummary(null);
      }
      setBulkChecking(false);
    });

    socket.on('application_check_error', (payload: any) => {
      setError(payload?.message ?? 'Background check failed');
      setBulkChecking(false);
      setBulkSummary(null);
    });

    return () => {
      socket.disconnect();
      socket.removeAllListeners();
    };
  }, [socket]);

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

      <ErrorMessage message={error} className="mb-3" />

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
            <div className="flex items-center gap-2 text-xs text-slate-400">
              <LoadingSpinner size="sm" />
              <span>Loading...</span>
            </div>
          )}
          {!loading && sheets.length === 0 && (
            <EmptyState message="No sheets found for this spreadsheet." className="text-xs" />
          )}
          <ul className="space-y-1 max-h-80 overflow-auto text-sm">
            {sheets.map((s) => (
              <li
                key={s.sheet_id}
                onClick={() => {
                  // When switching sheets, clear in-memory statuses and summary
                  setSelectedSheetId(s.sheet_id);
                  setAppliedStatus({});
                  setBulkSummary(null);
                  setCheckingIndex(null);
                  setSelectedJobUrl(null);
                  setHeaders([]);
                  setRows([]);
                  setError(null);
                }}
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
            <div className="flex items-center justify-between mb-2">
              <p className="text-xs text-slate-400">
                Date, Company, Position, Job Url and application status.
              </p>
              <button
                type="button"
                onClick={async () => {
                  if (!profileId || selectedSheetId === null || !socket) return;
                  try {
                    setBulkChecking(true);
                    setError(null);
                    setBulkSummary(null);
                    setAppliedStatus({});
                    const res = await api.post<{ job_id: string }>(
                      `/profiles/${profileId}/sheets/${selectedSheetId}/gmail/check-all`
                    );
                    const jobId = res.data.job_id;
                    socket.emit('join_job', { job_id: jobId });

                    setTimeout(() => {
                      setBulkChecking(false);
                    }, 60000);
                  } catch (err: any) {
                    setError(
                      err?.response?.data?.message ?? 'Failed to start Gmail check for all positions'
                    );
                    setBulkChecking(false);
                  }
                }}
                className="text-xs text-sky-400 hover:text-sky-300 disabled:opacity-50"
                disabled={bulkChecking || rows.length === 0}
              >
                {bulkChecking ? 'Checking all…' : 'Check all applications'}
              </button>
            </div>
            {bulkSummary && (
              <p className="text-xs text-slate-300 mb-1">
                Confirmed applied:{' '}
                <span className="text-emerald-400 font-semibold">{bulkSummary.applied}</span>{' '}
                · Not found:{' '}
                <span className="text-red-300 font-semibold">{bulkSummary.notApplied}</span>{' '}
                · Not checked yet:{' '}
                <span className="text-slate-200 font-semibold">{bulkSummary.notChecked}</span>
              </p>
            )}
            {loading && rows.length === 0 && (
              <div className="flex items-center gap-2 text-sm text-slate-400">
                <LoadingSpinner size="sm" />
                <span>Loading...</span>
              </div>
            )}
            {!loading && rows.length === 0 && (
              <EmptyState message="No data found in this sheet." />
            )}

            {rows.length > 0 && (
              <div className="overflow-auto max-h-[28rem]">
                <table className="min-w-full text-xs border border-slate-800">
                  <thead className="bg-slate-800">
                    <tr>
                      {visibleColumnIndices.map((idx) => (
                        <th
                          key={`${idx}-${headers[idx]}`}
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
                    {rows.map((row, idx) => (
                      <SheetTableRow
                        key={`row-${idx}`}
                        row={row}
                        rowIndex={idx}
                        headers={headers}
                        visibleColumnIndices={visibleColumnIndices}
                        jobUrlIndex={jobUrlIndex}
                        companyIndex={companyIndex}
                        appliedDateIndex={appliedDateIndex}
                        status={appliedStatus[idx]}
                        checkingIndex={checkingIndex}
                        onCheck={handleCheckApplied}
                        onSelectUrl={handleSelectUrl}
                      />
                    ))}
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


