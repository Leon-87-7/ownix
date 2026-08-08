/** Options page: connection status, pair/disconnect (issues #478/#479). */

import { getOwnixHost } from './api.js';
import { clearExtensionToken, getExtensionToken, redeemPairingCode } from './auth.js';

export async function initOptions(doc: Document): Promise<void> {
  const connectionStatus = doc.getElementById('connection-status') as HTMLParagraphElement;
  const pairingCodeInput = doc.getElementById('pairing-code') as HTMLInputElement;
  const pairBtn = doc.getElementById('pair') as HTMLButtonElement;
  const disconnectBtn = doc.getElementById('disconnect') as HTMLButtonElement;
  const pairingStatus = doc.getElementById('pairing-status') as HTMLParagraphElement;

  const refreshConnectionStatus = async () => {
    const token = await getExtensionToken();
    connectionStatus.textContent = token ? 'Connected to Ownix.' : 'Not connected.';
    disconnectBtn.disabled = !token;
  };
  await refreshConnectionStatus();

  pairBtn.addEventListener('click', async () => {
    pairingStatus.textContent = 'Connecting...';
    try {
      await redeemPairingCode(await getOwnixHost(), pairingCodeInput.value.trim());
      pairingCodeInput.value = '';
      pairingStatus.textContent = 'Paired successfully.';
      await refreshConnectionStatus();
    } catch (err) {
      pairingStatus.textContent = err instanceof Error ? err.message : 'Pairing failed.';
    }
  });

  disconnectBtn.addEventListener('click', async () => {
    await clearExtensionToken();
    pairingStatus.textContent = 'Disconnected.';
    await refreshConnectionStatus();
  });
}

if (typeof document !== 'undefined' && document.getElementById('pair')) {
  void initOptions(document);
}
