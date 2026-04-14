import { aircraftIconEntries } from "./assets/aircraft";

const previewSizes = [12, 16, 20, 24, 32] as const;
const headings = [0, 30, 60, 90, 120, 150, 180, 225, 270, 315] as const;

type GlyphProps = {
  src: string;
  label: string;
  size: number;
  color: string;
  rotationDeg?: number;
};

function AircraftGlyph({ src, label, size, color, rotationDeg = 0 }: GlyphProps) {
  return (
    <span
      aria-label={label}
      className="icon-demo-glyph"
      style={{
        width: size,
        height: size,
        backgroundColor: color,
        WebkitMaskImage: `url(${src})`,
        maskImage: `url(${src})`,
        transform: `rotate(${rotationDeg}deg)`
      }}
    />
  );
}

export default function AircraftIconDemo() {
  return (
    <main className="icon-demo-page">
      <header className="icon-demo-hero">
        <div>
          <p className="icon-demo-kicker">Eagle Eye Aircraft Pack</p>
          <h1>Original top-down silhouettes for rotatable Cesium billboards.</h1>
          <p>
            The set is drawn for map readability first: centered geometry, single-color silhouettes, and stable legibility
            from micro map sizes through analyst-focused close zoom.
          </p>
        </div>
      </header>

      <section className="icon-demo-panel dark">
        <div className="icon-demo-panel-header">
          <h2>Dark Surface</h2>
          <span>Operational console preview</span>
        </div>
        <div className="icon-grid">
          {aircraftIconEntries.map((icon) => (
            <article key={icon.key} className="icon-card dark">
              <div className="icon-card-preview">
                {previewSizes.map((size) => (
                  <AircraftGlyph key={size} src={icon.src} label={icon.label} size={size} color="#ffd54a" />
                ))}
              </div>
              <strong>{icon.label}</strong>
              <small>{icon.key}</small>
            </article>
          ))}
        </div>
      </section>

      <section className="icon-demo-panel light">
        <div className="icon-demo-panel-header">
          <h2>Light Surface</h2>
          <span>Readability check against bright charts</span>
        </div>
        <div className="icon-grid">
          {aircraftIconEntries.map((icon) => (
            <article key={`${icon.key}-light`} className="icon-card light">
              <div className="icon-card-preview">
                {previewSizes.map((size) => (
                  <AircraftGlyph key={size} src={icon.src} label={icon.label} size={size} color="#0f1724" />
                ))}
              </div>
              <strong>{icon.label}</strong>
              <small>{icon.key}</small>
            </article>
          ))}
        </div>
      </section>

      <section className="icon-demo-panel dark">
        <div className="icon-demo-panel-header">
          <h2>Rotation Demo</h2>
          <span>Heading-aware billboard behavior</span>
        </div>
        <div className="rotation-demo-grid">
          {aircraftIconEntries.map((icon) => (
            <article key={`${icon.key}-rotation`} className="rotation-card">
              <strong>{icon.label}</strong>
              <div className="rotation-ring">
                {headings.map((heading) => (
                  <AircraftGlyph
                    key={heading}
                    src={icon.src}
                    label={`${icon.label} ${heading} degrees`}
                    size={28}
                    color="#ffd54a"
                    rotationDeg={heading}
                  />
                ))}
              </div>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}
