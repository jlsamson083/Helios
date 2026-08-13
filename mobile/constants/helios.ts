const apiKey =
  process.env.EXPO_PUBLIC_HELIOS_API_KEY ?? '';

export const HELIOS_API_BASE =
  process.env.EXPO_PUBLIC_HELIOS_API_BASE ??
  'https://168-107-79-27.sslip.io/api/v1/energy';

export const HELIOS_API_HEADERS = {
  'X-Helios-Key': apiKey,
};

export function assertHeliosConfigured() {
  if (!apiKey) {
    throw new Error(
      'Helios API key is missing. Restart Expo after configuring mobile/.env.',
    );
  }
}
