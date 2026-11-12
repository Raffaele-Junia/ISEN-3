import { CONTENT } from "../content";
import styles from "./Nav.module.css";

export type NavTheme = "light" | "dark";

const ICON_ACCOUNT = "https://assets.uberdesigner.ai/portale/icon-account.svg";

export function Nav({ theme }: { theme: NavTheme }) {
  const { links, heroActive, readyActive, account, cta } = CONTENT.nav;
  const active = theme === "dark" ? readyActive : heroActive;
  return (
    <header className={styles.nav} data-nav="" data-theme={theme}>
      <a href="#" className={`${styles.brand} trim`} aria-label={`${CONTENT.brand} home`}>
        {CONTENT.brand}
      </a>
      <nav className={styles.links} aria-label="Main">
        {links.map((link) => (
          <a key={link} href="#" className={`${styles.link} trim`} data-active={link === active || undefined}>
            {link}
          </a>
        ))}
      </nav>
      <div className={styles.right}>
        <a href="#" className={styles.account}>
          <img src={ICON_ACCOUNT} alt="" width={23} height={23} className={styles.icon} />
          <span className="trim">{account}</span>
        </a>
        <a href="#" className={styles.cta}>
          <span className="trim">{cta}</span>
        </a>
      </div>
    </header>
  );
}
