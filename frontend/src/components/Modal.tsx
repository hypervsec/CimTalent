import type { ReactNode } from "react";
export function Modal({
  title,
  children,
  close,
}: {
  title: string;
  children: ReactNode;
  close: () => void;
}) {
  return (
    <div className="modal" role="dialog" aria-modal="true">
      <div className="modal-card">
        <button onClick={close}>Kapat</button>
        <h2>{title}</h2>
        {children}
      </div>
    </div>
  );
}
