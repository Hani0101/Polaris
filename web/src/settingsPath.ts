/** Route helper for the Settings page (ST-01). */

export const SETTINGS_PATH = '/settings'

export function isSettingsPath(path: string): boolean {
  return path === SETTINGS_PATH
}
