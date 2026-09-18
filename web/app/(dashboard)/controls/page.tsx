'use client';

import { SlidersHorizontal } from 'lucide-react';
import { useRestrictedMode } from '@/lib/restricted/context';
import { RestrictedFacade } from '@/components/shell/restricted-facade';
import { PageShell, PageHeader } from '@/components/shell/page-shell';
import { Section } from '@/components/controls/section';
import { TagsPanel } from '@/components/controls/tags-panel';
import { DomainPanel } from '@/components/controls/domain-panel';
import { AccessibilityPanel } from '@/components/controls/accessibility-panel';
import { RecoveryNotificationsPanel } from '@/components/controls/recovery-notifications-panel';
import { DeleteAccountPanel } from '@/components/controls/delete-account-panel';
import { ExtensionTokensPanel } from '@/components/controls/extension-tokens-panel';
import { McpTokensPanel } from '@/components/controls/mcp-tokens-panel';
import { ScoutSettingsPanel } from '@/components/controls/scout-settings-panel';
import { DiscordPairingPanel } from '@/components/controls/discord-pairing-panel';

export default function ControlsPage() {
  const { restricted } = useRestrictedMode();
  if (restricted)
    return (
      <RestrictedFacade icon={SlidersHorizontal} title="Settings">
        Settings is where you tune domains, tags, and how the dashboard behaves
        in your own Index. Nothing you change here is saved.
      </RestrictedFacade>
    );

  return (
    <PageShell>
      <PageHeader
        icon={SlidersHorizontal}
        title="Settings"
        description="Tags, domain rules, accessibility, and the devices connected to your Index."
      />
      <div className="space-y-3">
        <Section title="Tags" defaultOpen>
          <TagsPanel />
        </Section>
        <Section title="Domains" defaultOpen>
          <p className="mb-4 text-copy text-body">
            Decide which sites Ownix processes on its own. Put a domain in
            Allowed and links from it get picked up; put it in Ignored and they
            get skipped. It is how you route around a noisy source without
            having to reject its links one by one.
          </p>
          <div className="grid gap-6 md:grid-cols-2">
            <div>
              <h4 className="mb-3 text-label font-semibold text-muted">
                Allowed
              </h4>
              <DomainPanel
                apiPath="/api/controls/allowed-domains"
                label="Allowed Domains"
              />
            </div>
            <div className="md:border-l md:border-line md:pl-6">
              <h4 className="mb-3 text-label font-semibold text-muted">
                Ignored
              </h4>
              <DomainPanel
                apiPath="/api/controls/ignored-domains"
                label="Ignored Domains"
              />
            </div>
          </div>
        </Section>
        <Section title="Accessibility">
          <AccessibilityPanel />
        </Section>
        <Section title="Recovery notifications">
          <RecoveryNotificationsPanel />
        </Section>
        <Section title="Chrome Extension">
          <ExtensionTokensPanel />
        </Section>
        <Section title="MCP clients">
          <div className="grid gap-6 md:grid-cols-2">
            <div>
              <McpTokensPanel />
            </div>
            <div className="md:border-l md:border-line md:pl-6">
              <h4 className="mb-3 text-label font-semibold text-muted">
                Scouting
              </h4>
              <ScoutSettingsPanel />
            </div>
          </div>
        </Section>
        <Section title="Discord">
          <DiscordPairingPanel />
        </Section>
        <Section title="Danger zone" titleClassName="text-status-error">
          <DeleteAccountPanel />
        </Section>
      </div>
    </PageShell>
  );
}
