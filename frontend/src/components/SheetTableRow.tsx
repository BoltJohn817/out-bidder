import { memo } from 'react';

interface SheetTableRowProps {
  row: string[];
  rowIndex: number;
  headers: string[];
  visibleColumnIndices: number[];
  jobUrlIndex: number;
  companyIndex: number;
  appliedDateIndex: number;
  status?: 'applied' | 'not_applied' | 'error';
  checkingIndex: number | null;
  onCheck: (rowIndex: number) => void;
  onSelectUrl: (url: string) => void;
}

export const SheetTableRow = memo<SheetTableRowProps>(({
  row,
  rowIndex,
  headers,
  visibleColumnIndices,
  jobUrlIndex,
  companyIndex,
  appliedDateIndex,
  status,
  checkingIndex,
  onCheck,
  onSelectUrl,
}) => {
  const baseColor =
    status === 'applied'
      ? 'bg-emerald-900/40'
      : status === 'not_applied'
        ? 'bg-red-900/20'
        : status === 'error'
          ? 'bg-red-900/40'
          : rowIndex % 2 === 0
            ? 'bg-slate-950'
            : 'bg-slate-900';

  const handleRowClick = () => {
    const url = row[jobUrlIndex];
    if (url) {
      onSelectUrl(url);
    }
  };

  const handleCheckClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    onCheck(rowIndex);
  };

  return (
    <tr
      key={`${rowIndex}-${headers[rowIndex]}`}
      className={`${baseColor} cursor-pointer hover:bg-slate-800/70`}
      onClick={handleRowClick}
    >
      {visibleColumnIndices.map((cidx) => {
        const cell = row[cidx];
        const isJobUrl = cidx === jobUrlIndex;
        const display =
          isJobUrl && cell && cell.length > 40
            ? `${cell.slice(0, 40)}…`
            : cell;
        return (
          <td
            key={cidx}
            className={`px-3 py-1 border-b border-slate-800 align-top max-w-xs break-words ${
              isJobUrl ? 'text-sky-300' : ''
            }`}
          >
            {display}
          </td>
        );
      })}
      <td className="px-3 py-1 border-b border-slate-800 align-top whitespace-nowrap">
        {status === 'applied' && (
          <span className="text-emerald-400 text-xs font-semibold">Applied</span>
        )}
        {status === 'not_applied' && (
          <span className="text-slate-300 text-xs">Not found</span>
        )}
        {status === 'error' && (
          <span className="text-red-400 text-xs">Error</span>
        )}
        {!status && (
          <button
            type="button"
            onClick={handleCheckClick}
            className="text-xs text-sky-400 hover:text-sky-300 disabled:opacity-50"
            disabled={checkingIndex === rowIndex || !row[companyIndex] || !row[appliedDateIndex]}
          >
            {checkingIndex === rowIndex ? 'Checking...' : 'Check'}
          </button>
        )}
      </td>
    </tr>
  );
});

SheetTableRow.displayName = 'SheetTableRow';

