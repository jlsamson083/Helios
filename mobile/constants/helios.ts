import { Platform } from 'react-native';

const nativeApiKey = process.env.EXPO_PUBLIC_HELIOS_API_KEY ?? '';

export function getHeliosApiKey() {
  if (Platform.OS === 'web' && typeof window !== 'undefined') {
    return window.localStorage.getItem('helios_api_key') ?? '';
  }
  return nativeApiKey;
}

export function saveHeliosApiKey(value: string) {
  if (Platform.OS === 'web' && typeof window !== 'undefined') {
    window.localStorage.setItem('helios_api_key', value);
  }
}

export const HELIOS_API_BASE =
  process.env.EXPO_PUBLIC_HELIOS_API_BASE ??
  'https://168-107-79-27.sslip.io/api/v1/energy';

export const HELIOS_API_HEADERS = {} as Record<string, string>;
Object.defineProperty(HELIOS_API_HEADERS, 'X-Helios-Key', {
  enumerable: true,
  get: getHeliosApiKey,
});

export function assertHeliosConfigured() {
  if (Platform.OS === 'web') return;
  if (!getHeliosApiKey()) {
    throw new Error(
      'Helios API key is missing. Restart Expo after configuring mobile/.env.',
    );
  }
}
