export function LoadingScreen() {
  return (
    <div className="helios-loader" role="status" aria-live="polite">
      <div className="helios-loader__orbit" aria-hidden="true">
        <span className="helios-loader__sun">H</span>
        <span className="helios-loader__satellite" />
      </div>
      <p className="helios-loader__title">Starting Helios</p>
      <p className="helios-loader__copy">Preparing your workspace</p>
    </div>
  );
}
