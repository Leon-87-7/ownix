import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { moveFocusBeforeStepTransition } from './onboarding-stepper';

describe('onboarding step focus management', () => {
  it('moves keyboard focus into the incoming step before advancing', async () => {
    const user = userEvent.setup();
    const outgoing = document.createElement('article');
    const outgoingLink = document.createElement('a');
    outgoingLink.href = '#capture';
    outgoing.append(outgoingLink);
    const incomingButton = document.createElement('button');
    document.body.append(outgoing, incomingButton);

    await user.tab();
    expect(outgoingLink).toHaveFocus();

    moveFocusBeforeStepTransition(outgoing, [incomingButton]);

    expect(incomingButton).toHaveFocus();
  });
});
