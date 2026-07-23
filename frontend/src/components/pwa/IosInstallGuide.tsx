export function IosInstallGuide() {
  return (
    <div className="ios-install-guide" aria-label="Five steps to add AirSpace to your Home Screen">
      <ol>
        <li>
          <span className="install-step-visual menu-symbol" aria-hidden="true">···</span>
          <span><strong>Tap the ··· menu</strong><small>Open Safari’s page menu.</small></span>
        </li>
        <li>
          <span className="install-step-visual share-symbol" aria-hidden="true">
            <svg viewBox="0 0 24 24" role="img">
              <path d="M12 16V3m0 0L7.5 7.5M12 3l4.5 4.5M5 11v8h14v-8" />
            </svg>
          </span>
          <span><strong>Tap Share</strong><small>Use Safari’s Share button.</small></span>
        </li>
        <li>
          <span className="install-step-visual add-symbol" aria-hidden="true">＋</span>
          <span><strong>Add to Home Screen</strong><small>Scroll down if you don't see it.</small></span>
        </li>
        <li>
          <span className="install-step-visual confirm-symbol" aria-hidden="true">Add</span>
          <span><strong>Confirm</strong><small>Tap Add in the upper corner.</small></span>
        </li>
        <li>
          <img className="install-step-visual" src="/icons/icon-192.png" alt="" />
          <span><strong>Open AirSpace</strong><small>Launch it from your Home Screen.</small></span>
        </li>
      </ol>
    </div>
  );
}
