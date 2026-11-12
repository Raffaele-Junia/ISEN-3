import styles from "./Preloader.module.css";
import { Wordmark } from "./Wordmark";

export function Preloader() {
  return (
    <div className={styles.preloader} data-preloader="">
      <Wordmark className={styles.wordmark} data-preloader-part="wordmark" />
      <div className={`${styles.counter} trim`} data-preloader-part="counter">
        00%
      </div>
    </div>
  );
}
