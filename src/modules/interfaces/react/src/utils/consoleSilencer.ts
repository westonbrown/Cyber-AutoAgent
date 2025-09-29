/**
 * Console Silencer
 *
 * In production, silence console.log/info/debug/warn to prevent stray output
 * from flooding Ink's render path. console.error remains intact.
 */

let originalLog: any;
let originalInfo: any;
let originalDebug: any;
let originalWarn: any;
let active = false;

export function enableConsoleSilence() {
  if (active) return;
  originalLog = console.log;
  originalInfo = console.info;
  originalDebug = console.debug;
  originalWarn = console.warn;
  const noop = () => {};
  try { console.log = noop; } catch {}
  try { console.info = noop; } catch {}
  try { console.debug = noop; } catch {}
  try { console.warn = noop; } catch {}
  active = true;
}

export function disableConsoleSilence() {
  if (!active) return;
  try { if (originalLog) console.log = originalLog; } catch {}
  try { if (originalInfo) console.info = originalInfo; } catch {}
  try { if (originalDebug) console.debug = originalDebug; } catch {}
  try { if (originalWarn) console.warn = originalWarn; } catch {}
  active = false;
}
