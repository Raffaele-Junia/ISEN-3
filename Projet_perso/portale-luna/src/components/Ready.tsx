import { CONTENT } from "../content";
import styles from "./Ready.module.css";
import { Wordmark } from "./Wordmark";
import { Words } from "./Words";

const ICON_PLUS = "https://assets.uberdesigner.ai/portale/icon-plus.svg";

export function Ready({ product }: { product: string | null }) {
  const { first, second, more, text, cta, scroll } = CONTENT.ready;
  return (
    <section className={styles.ready} data-ready="section">
      <div className={styles.wordmark} data-ready="wordmark">
        <Wordmark className={styles.mark} />
      </div>
      <div className={styles.card} data-ready="card">
        <div className={styles.float} data-ready="float">
          {product ? <img src={product} alt="" className={styles.image} data-ready="image" /> : null}
        </div>
      </div>
      <h2 className={styles.heading} aria-label={`${first} ${second}`}>
        <span className={`${styles.line} ${styles.first} trim`} aria-hidden="true" data-ready="first">
          <Words text={first} className={styles.word} />
        </span>
        <span className={`${styles.line} ${styles.second} trim`} aria-hidden="true" data-ready="second">
          <Words text={second} className={styles.word} />
        </span>
      </h2>
      <a href="#" className={styles.more} data-ready="more">
        <img src={ICON_PLUS} alt="" width={23} height={23} className={styles.icon} />
        <span className="trim">{more}</span>
      </a>
      <p className={`${styles.text} trim`} data-ready="text">
        {text}
      </p>
      <a href="#" className={styles.cta} data-ready="cta">
        <span className="trim">{cta}</span>
      </a>
      <p className={`${styles.scroll} trim`} data-ready="scroll">
        {scroll}
      </p>
    </section>
  );
}
