/**
 * Utility functions for finding column indices in sheet headers.
 */

export function findColumnIndex(
  headers: string[],
  predicate: (header: string) => boolean,
  defaultIndex: number
): number {
  const index = headers.findIndex((h) => predicate(h.toLowerCase().trim()));
  return index !== -1 ? index : defaultIndex;
}

export function parseSheetColumnIndices(headers: string[]) {
  return {
    companyIndex: findColumnIndex(headers, (h) => h.includes('company'), 0),
    positionIndex: findColumnIndex(headers, (h) => h.includes('position'), 0),
    jobUrlIndex: findColumnIndex(
      headers,
      (h) => h === 'job url' || h.includes('url'),
      2
    ),
    appliedDateIndex: findColumnIndex(headers, (h) => h.includes('date'), 1),
  };
}

