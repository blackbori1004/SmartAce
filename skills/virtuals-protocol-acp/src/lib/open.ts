// =============================================================================
// Open URL helper (hardened mode)
// =============================================================================

export function openUrl(url: string): void {
  // Hardened mode: do not spawn shell/browser commands from this skill.
  // We print the URL so the user can open it manually.
  console.log(`Open this URL in your browser: ${url}`);
}
