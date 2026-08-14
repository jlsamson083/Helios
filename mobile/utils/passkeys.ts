import { HELIOS_API_BASE } from '@/constants/helios';

const authBase = `${HELIOS_API_BASE.replace(/\/energy$/, '')}/auth/passkey`;

function decode(value: string) {
  const base64 = value.replace(/-/g, '+').replace(/_/g, '/');
  const padded = base64 + '='.repeat((4 - base64.length % 4) % 4);
  return Uint8Array.from(atob(padded), (character) => character.charCodeAt(0));
}

function encode(value: ArrayBuffer) {
  const bytes = new Uint8Array(value);
  let binary = '';
  bytes.forEach((byte) => { binary += String.fromCharCode(byte); });
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

function serialize(credential: PublicKeyCredential) {
  const response = credential.response;
  const result: Record<string, unknown> = {
    id: credential.id,
    rawId: encode(credential.rawId),
    type: credential.type,
    authenticatorAttachment: credential.authenticatorAttachment,
    clientExtensionResults: credential.getClientExtensionResults(),
  };
  if (response instanceof AuthenticatorAttestationResponse) {
    result.response = {
      attestationObject: encode(response.attestationObject),
      clientDataJSON: encode(response.clientDataJSON),
      transports: response.getTransports?.() ?? ['internal'],
    };
  } else {
    const assertion = response as AuthenticatorAssertionResponse;
    result.response = {
      authenticatorData: encode(assertion.authenticatorData),
      clientDataJSON: encode(assertion.clientDataJSON),
      signature: encode(assertion.signature),
      userHandle: assertion.userHandle ? encode(assertion.userHandle) : null,
    };
  }
  return result;
}

export function passkeysSupported() {
  return typeof window !== 'undefined' && 'PublicKeyCredential' in window;
}

export async function registerPasskey() {
  const response = await fetch(`${authBase}/register/options`, { method: 'POST' });
  if (!response.ok) throw new Error('Unable to start Face ID setup.');
  const { challenge_token: token, options } = await response.json();
  options.challenge = decode(options.challenge);
  options.user.id = decode(options.user.id);
  options.excludeCredentials = (options.excludeCredentials ?? []).map((item: Record<string, unknown>) => ({
    ...item, id: decode(item.id as string),
  }));
  const credential = await navigator.credentials.create({ publicKey: options }) as PublicKeyCredential | null;
  if (!credential) throw new Error('Face ID setup was cancelled.');
  const verify = await fetch(`${authBase}/register/verify`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ challenge_token: token, credential: serialize(credential) }),
  });
  if (!verify.ok) throw new Error('Helios could not verify the Face ID passkey.');
}

export async function authenticateWithPasskey() {
  const response = await fetch(`${authBase}/authenticate/options`, { method: 'POST' });
  if (!response.ok) throw new Error('Set up Face ID from Settings first.');
  const { challenge_token: token, options } = await response.json();
  options.challenge = decode(options.challenge);
  options.allowCredentials = (options.allowCredentials ?? []).map((item: Record<string, unknown>) => ({
    ...item, id: decode(item.id as string),
  }));
  const credential = await navigator.credentials.get({ publicKey: options }) as PublicKeyCredential | null;
  if (!credential) throw new Error('Face ID was cancelled.');
  const verify = await fetch(`${authBase}/authenticate/verify`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ challenge_token: token, credential: serialize(credential) }),
  });
  if (!verify.ok) throw new Error('Face ID could not unlock Helios.');
}
