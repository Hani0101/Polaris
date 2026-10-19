/** Route helper for the sign-in page (AU-02). */

export const SIGN_IN_PATH = '/sign-in'

export function isSignInPath(path: string): boolean {
  return path === SIGN_IN_PATH
}
