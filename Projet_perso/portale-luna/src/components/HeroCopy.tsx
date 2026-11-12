import { CONTENT } from "../content";
import styles from "./HeroCopy.module.css";
import { Words } from "./Words";

export function HeroCopy() {
  const { badge, lines, lead, primary, secondary } = CONTENT.hero;
  return (
    <div className={styles.copy} data-hero="copy">
      <div className={styles.column}>
        <div className={styles.badge} data-intro="badge">
          <span className={styles.square} />
          <span className="trim">{badge}</span>
        </div>
        <h1 className={`${styles.title} trim`} aria-label={lines.join(" ")} data-intro="title">
          {lines.map((line) => (
            <span key={line} className={styles.line} aria-hidden="true">
              <Words text={line} className={styles.word} />
            </span>
          ))}
        </h1>
      </div>
      <div className={styles.buttons} data-intro="buttons">
        <a href="#" className={`${styles.button} ${styles.primary}`}>
          <span className="trim">{primary}</span>
        </a>
        <a href="#" className={`${styles.button} ${styles.secondary}`}>
          <span className="trim">{secondary}</span>
        </a>
      </div>
      <p className={`${styles.lead} trim`} data-intro="lead">
        {lead}
      </p>
    </div>
  );
}
