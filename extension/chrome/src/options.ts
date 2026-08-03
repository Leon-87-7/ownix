/** Options page: choose Ownix host, connection status, pair/disconnect (issues #478/#479). */

import { getOwnixHost, setOwnixHost } from './api';
import { clearExtensionToken, getExtensionToken, redeemPairingCode } from './auth';

export async function initOptions(doc: Document): Promise<void> {
  const hostInput = doc.getElementById('host') as HTMLInputElement;
  const status = doc.getElementById('status') as HTMLParagraphElement;
  const saveBtn = doc.getElementById('save') as HTMLButtonElement;
  const connectionStatus = doc.getElementById('connection-status') as HTMLParagraphElement;
  const pairingCodeInput = doc.getElementById('pairing-code') as HTMLInputElement;
  const pairBtn = doc.getElementById('pair') as HTMLButtonElement;
  const disconnectBtn = doc.getElementById('disconnect') as HTMLButtonElement;
  const pairingStatus = doc.getElementById('pairing-status') as HTMLParagraphElement;

  hostInput.value = await getOwnixHost();

  const refreshConnectionStatus = async () => {
    const token = await getExtensionToken();
    connectionStatus.textContent = token ? 'Connected via paired token.' : 'Not paired.';
    disconnectBtn.disabled = !token;
  };
  await refreshConnectionStatus();

  saveBtn.addEventListener('click', async () => {
    await setOwnixHost(hostInput.value.trim());
    status.textContent = 'Saved.';
  });

  pairBtn.addEventListener('click', async () => {
    pairingStatus.textContent = 'Connecting…';
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

if (typeof document !== 'undefined' && document.getElementById('save')) {
  void initOptions(document);
}
