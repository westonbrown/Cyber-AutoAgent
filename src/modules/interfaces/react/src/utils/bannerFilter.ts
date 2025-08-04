/**
 * Filter out ASCII banner from Python output
 */

const BANNER_PATTERNS = [
  /██████╗██╗\s+██╗██████╗\s+███████╗██████╗/,  // First line of banner
  /██╔════╝╚██╗\s*██╔╝██╔══██╗██╔════╝██╔══██╗/, // Second line
  /╚██████╗\s+██║\s+██████╔╝███████╗██║\s+██║/,  // Middle lines
  /╚═════╝\s+╚═╝\s+╚═════╝\s+╚══════╝╚═╝\s+╚═╝/, // Last line
  /█████╗\s*██╗\s+██╗████████╗\s*██████╗/,        // AUTO part
  /Autonomous Cyber Agent/i,                        // Subtitle
];

/**
 * Check if a line is part of the ASCII banner
 */
export function isBannerLine(line: string): boolean {
  // Check for box drawing characters commonly used in banners
  if (line.includes('█') || line.includes('╗') || line.includes('╔') || 
      line.includes('╝') || line.includes('╚') || line.includes('═')) {
    return true;
  }
  
  // Check against known patterns
  return BANNER_PATTERNS.some(pattern => pattern.test(line));
}

/**
 * Filter out banner lines from output
 */
export function filterBannerLines(lines: string[]): string[] {
  let inBanner = false;
  let bannerLineCount = 0;
  
  return lines.filter(line => {
    // Detect start of banner
    if (!inBanner && isBannerLine(line)) {
      inBanner = true;
      bannerLineCount = 1;
      return false; // Filter out this line
    }
    
    // If we're in banner, check if this line is also part of it
    if (inBanner) {
      if (isBannerLine(line) || line.trim() === '' && bannerLineCount < 10) {
        bannerLineCount++;
        return false; // Filter out banner lines and empty lines near banner
      } else {
        // End of banner detected
        inBanner = false;
        bannerLineCount = 0;
        // Check if this line is version info (v0.1.3 • Cyber Operations)
        if (line.includes('• Cyber Operations') || line.includes('Professional Platform')) {
          return false; // Also filter out version line
        }
      }
    }
    
    return true; // Keep all other lines
  });
}

/**
 * Clean output by removing banner and excessive whitespace
 */
export function cleanPythonOutput(output: string): string {
  const lines = output.split('\n');
  const filteredLines = filterBannerLines(lines);
  
  // Also remove lines that are just whitespace at the start
  let startIndex = 0;
  while (startIndex < filteredLines.length && filteredLines[startIndex].trim() === '') {
    startIndex++;
  }
  
  return filteredLines.slice(startIndex).join('\n');
}