import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it } from 'vitest';
import { moveFocusBeforeStepTransition } from './onboarding-stepper';

afterEach(() => {
  document.body.replaceChildren();
});

describe('onboarding step focus management', () => {
  it('falls back to the incoming step when advancing to a card without controls', async () => {
    const user = userEvent.setup();
    const outgoing = document.createElement('article');
    const outgoingLink = document.createElement('a');
    outgoingLink.href = '#capture';
    outgoing.append(outgoingLink);
    const incoming = document.createElement('article');
    incoming.tabIndex = -1;
    document.body.append(outgoing, incoming);

    await user.tab();
    expect(outgoingLink).toHaveFocus();

    moveFocusBeforeStepTransition(outgoing, incoming, []);

    expect(incoming).toHaveFocus();
  });

  it('moves focus to the previous step when a reverse transition hides a control', () => {
    const previous = document.createElement('article');
    previous.tabIndex = -1;
    const previousButton = document.createElement('button');
    previous.append(previousButton);
    const outgoing = document.createElement('article');
    outgoing.tabIndex = -1;
    const outgoingLink = document.createElement('a');
    outgoingLink.href = '#invite';
    outgoing.append(outgoingLink);
    document.body.append(previous, outgoing);
    outgoingLink.focus();

    moveFocusBeforeStepTransition(outgoing, previous, [previousButton]);

    expect(previousButton).toHaveFocus();
  });
});
