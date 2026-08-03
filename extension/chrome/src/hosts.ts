const DEFAULT_HOST = 'https://app.leondev.xyz';
const LOCAL_DEV_HOST = 'http://localhost:8000';

const ALLOWED_OWNIX_ORIGINS = [DEFAULT_HOST, LOCAL_DEV_HOST] as const;

export type AllowedOwnixOrigin = (typeof ALLOWED_OWNIX_ORIGINS)[number];

export function defaultOwnixHost(): AllowedOwnixOrigin {
  return DEFAULT_HOST;
}

export function allowedOwnixHostList(): readonly AllowedOwnixOrigin[] {
  return ALLOWED_OWNIX_ORIGINS;
}

export function normalizeAllowedOwnixHost(host: string): AllowedOwnixOrigin {
  let origin: string;
  try {
    origin = new URL(host).origin;
  } catch {
    throw new Error(allowedOwnixHostError());
  }

  const allowed = ALLOWED_OWNIX_ORIGINS.find((candidate) => candidate === origin);
  if (!allowed) {
    throw new Error(allowedOwnixHostError());
  }
  return allowed;
}

export function isAllowedOwnixHost(host: string): boolean {
  try {
    normalizeAllowedOwnixHost(host);
    return true;
  } catch {
    return false;
  }
}

export function fetchExtensionToken(origin: AllowedOwnixOrigin, init: RequestInit): Promise<Response> {
  switch (origin) {
    case DEFAULT_HOST:
      return fetch('https://app.leondev.xyz/api/extension/token', init);
    case LOCAL_DEV_HOST:
      return fetch('http://localhost:8000/api/extension/token', init);
  }
}

export function fetchIntakeMessage(origin: AllowedOwnixOrigin, init: RequestInit): Promise<Response> {
  switch (origin) {
    case DEFAULT_HOST:
      return fetch('https://app.leondev.xyz/api/intake/message', init);
    case LOCAL_DEV_HOST:
      return fetch('http://localhost:8000/api/intake/message', init);
  }
}

function allowedOwnixHostError(): string {
  return `Ownix host must be one of: ${ALLOWED_OWNIX_ORIGINS.join(', ')}.`;
}
