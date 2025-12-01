import { useMemo } from 'react';
import { parseSheetColumnIndices } from '../utils/sheetColumns';

/**
 * Hook to parse and memoize sheet column indices.
 */
export function useSheetColumns(headers: string[]) {
  return useMemo(() => parseSheetColumnIndices(headers), [headers]);
}

