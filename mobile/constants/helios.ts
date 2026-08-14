export const HELIOS_API_BASE =
  process.env.EXPO_PUBLIC_HELIOS_API_BASE ??
  'https://168-107-79-27.sslip.io/api/v1/energy';

// Authentication is established by /auth/login and carried by the secure
// session cookie. Never embed a reusable API key in an EXPO_PUBLIC variable.
export const HELIOS_API_HEADERS = {} as Record<string, string>;

export function assertHeliosConfigured() {}
