"use client";

import { useState } from "react";
import { ADVANCED_MODES, type ResearchMode } from "../types";

export default function AdvancedSearchPopover({
  selected,
  onChange,
}: {
  selected: ResearchMode[];
  onChange: (modes: ResearchMode[]) => void;
}) {
  const [open, setOpen] = useState(false);

  function toggle(mode: ResearchMode) {
    onChange(selected.includes(mode) ? selected.filter((m) => m !== mode) : [...selected, mode]);
  }

  return (
    <div className="popover-container">
      <button
        type="button"
        className={`chip-toggle ${selected.length > 0 ? "chip-toggle--active" : ""}`}
        onClick={() => setOpen((v) => !v)}
      >
        Advanced Search{selected.length > 0 ? ` (${selected.length})` : ""}
      </button>
      {open && (
        <div className="popover">
          {ADVANCED_MODES.map((mode) => (
            <label key={mode.value} className={`popover-option ${mode.implemented ? "" : "popover-option--disabled"}`}>
              <input
                type="checkbox"
                checked={selected.includes(mode.value)}
                disabled={!mode.implemented}
                onChange={() => toggle(mode.value)}
              />
              {mode.label}
              {!mode.implemented && " (Phase 2)"}
            </label>
          ))}
        </div>
      )}
    </div>
  );
}
