"use client";

import { useState, type ReactNode } from "react";

export default function Accordion({
  title,
  count,
  defaultOpen = false,
  children,
}: {
  title: string;
  count?: number;
  defaultOpen?: boolean;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="accordion">
      <button type="button" className="accordion-header" onClick={() => setOpen((v) => !v)}>
        <span className="accordion-caret">{open ? "−" : "+"}</span>
        <span className="accordion-title">{title}</span>
        {typeof count === "number" && <span className="accordion-count">{count}</span>}
      </button>
      {open && <div className="accordion-body">{children}</div>}
    </div>
  );
}
