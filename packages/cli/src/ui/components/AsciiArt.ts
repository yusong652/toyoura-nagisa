/**
 * ASCII Art for aiNagisa CLI
 * Responsive logo designs for different terminal widths
 *
 * Features Nagisa - the cute pink pixel ball mascot with particle cluster ears
 * Based on nagisa_round_ears.py v4 (粒子簇耳朵) design
 * - Round ears like particles (fitting for PFC expert identity)
 * - Ball-shaped body (most stable natural form)
 * - Cute expression (◕ω◕) with blush marks
 */

// Nagisa pixel avatar - compact version (half height)
// Matches nagisa_round_ears.py create_round_ears_ball_v4()
// Features: particle cluster ears, eyes, blush marks, cute mouth (ω)
// Using █ (full block) and half blocks (▀▄▌▐) for higher resolution details
export const nagisaAscii = `
█████       █████
█████       █████
█████████████████
 ███████████████
█████ █████ █████
█████████████████
█ █████████████ █
█████████████████
 ███████████████
   ███████████
`;

// Full logo with Nagisa - for wide terminals (70+ columns)
// Features: particle cluster ears, eyes, blush marks
export const fullAsciiLogo = `
                       _   _             _
█████       █████     | \\ | | __ _  __ _(_)___  __ _
█████       █████     |  \\| |/ _\` |/ _\` | / __|/ _\` |
█████████████████     | |\\  | (_| | (_| | \\__ \\ (_| |
 ███████████████      |_| \\_|\\__,_|\\__, |_|___/\\__,_|
█████ █████ █████                  |___/
█████████████████
█ █████████████ █
█████████████████
 ███████████████
   ███████████
`;

// Short logo - for medium terminals (50+ columns)
export const shortAsciiLogo = `
█████   █████    _   _             _
█████████████   | \\ | | __ _  __ _(_)___  __ _
 ███████████    |  \\| |/ _\` |/ _\` | / __|/ _\` |
███ █████ ███   | |\\  | (_| | (_| | \\__ \\ (_| |
█████████████   |_| \\_|\\__,_|\\__, |_|___/\\__,_|
█ █████████ █                |___/
 ███████████
`;

// Tiny logo - for narrow terminals (30+ columns)
export const tinyAsciiLogo = `
███     ███
 █████████
███ ███ ███   Nagisa
███████████
█ ███████ █
 █████████
`;

// Minimal - just text for very narrow terminals
export const minimalLogo = '(◕ω◕) Nagisa';

/**
 * Get the width of an ASCII art string (max line length)
 */
export function getAsciiArtWidth(art: string): number {
  const lines = art.split('\n').filter(line => line.length > 0);
  return Math.max(...lines.map(line => line.length));
}

/**
 * Normalize line widths for consistent gradient rendering
 * Pads shorter lines with spaces to match the longest line
 */
export function normalizeLineWidths(art: string): string {
  const lines = art.split('\n');
  const maxWidth = Math.max(...lines.map(line => line.length));
  return lines.map(line => line.padEnd(maxWidth)).join('\n');
}

/**
 * Select appropriate logo based on terminal width
 */
export function selectLogo(terminalWidth: number): string {
  const fullWidth = getAsciiArtWidth(fullAsciiLogo);
  const shortWidth = getAsciiArtWidth(shortAsciiLogo);
  const tinyWidth = getAsciiArtWidth(tinyAsciiLogo);

  if (terminalWidth >= fullWidth + 4) {
    return fullAsciiLogo;
  } else if (terminalWidth >= shortWidth + 4) {
    return shortAsciiLogo;
  } else if (terminalWidth >= tinyWidth + 4) {
    return tinyAsciiLogo;
  } else {
    return minimalLogo;
  }
}
