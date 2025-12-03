/**
 * Normalize user input for Google Sheets references.
 *
 * Allows users to paste either:
 * - a raw spreadsheet ID, or
 * - a full Google Sheets URL like:
 *   https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit#gid=0
 *
 * Returns just the {SPREADSHEET_ID}.
 */
export const normalizeSpreadsheetInput = (raw: string): string => {
  const value = raw.trim();

  // Only attempt URL parsing if it looks like a Google Sheets URL
  if (value.includes('docs.google.com') && value.includes('/spreadsheets/')) {
    const match = value.match(/\/spreadsheets\/d\/([a-zA-Z0-9-_]+)/);
    if (match && match[1]) {
      return match[1];
    }
  }

  // Fallback: treat the input as already being an ID
  return value;
};


