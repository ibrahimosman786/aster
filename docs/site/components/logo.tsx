import Link from "next/link";

export function Logo() {
  return (
    <Link href="/" className="logo" aria-label="Aster documentation home">
      <svg className="logo-mark" width="22" height="22" viewBox="0 0 24 24" aria-hidden="true">
        <path fill="currentColor" d="M12 1.5 13.7 9.1 21.5 12 13.7 14.9 12 22.5 10.3 14.9 2.5 12 10.3 9.1Z" />
      </svg>
      <span className="logo-name">ASTER</span>
    </Link>
  );
}
