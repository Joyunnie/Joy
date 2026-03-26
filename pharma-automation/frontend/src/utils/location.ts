export interface ParsedLocation {
  layoutId: number;
  row: number;
  col: number;
}

export function parseLocation(loc: string | null): ParsedLocation | null {
  if (!loc) return null;
  const match = loc.match(/^(\d+):(\d+),(\d+)$/);
  if (!match) return null;
  return {
    layoutId: parseInt(match[1]),
    row: parseInt(match[2]),
    col: parseInt(match[3]),
  };
}

export function formatLocation(layoutId: number, row: number, col: number): string {
  return `${layoutId}:${row},${col}`;
}
