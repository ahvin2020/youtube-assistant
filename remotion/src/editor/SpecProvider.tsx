import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import type { EnhancementSpec, Enhancement, GlobalStyle } from "../lib/types";
import sampleSpec from "../sample-spec.json";

interface SpecContextValue {
  spec: EnhancementSpec;
  selectedId: string | null;
  setSelectedId: (id: string | null) => void;
  updateEnhancement: (id: string, updates: Partial<Enhancement>) => void;
  removeEnhancement: (id: string) => void;
  addEnhancement: (enhancement: Enhancement) => void;
  updateGlobalStyle: (updates: Partial<GlobalStyle>) => void;
  setSpec: (spec: EnhancementSpec) => void;
}

const SpecContext = createContext<SpecContextValue | null>(null);

export const useSpec = () => {
  const ctx = useContext(SpecContext);
  if (!ctx) throw new Error("useSpec must be used within SpecProvider");
  return ctx;
};

export const SpecProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [spec, setSpec] = useState<EnhancementSpec>(sampleSpec as unknown as EnhancementSpec);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  // Load spec from URL param or environment
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const specPath = params.get("spec");
    if (specPath) {
      fetch(`/api/spec?path=${encodeURIComponent(specPath)}`)
        .then((r) => r.json())
        .then((data) => setSpec(data))
        .catch(() => console.log("Using sample spec"));
    }
  }, []);

  const updateEnhancement = useCallback((id: string, updates: Partial<Enhancement>) => {
    setSpec((prev) => ({
      ...prev,
      enhancements: prev.enhancements.map((e) =>
        e.id === id ? { ...e, ...updates, content: { ...e.content, ...(updates.content ?? {}) } } as Enhancement : e
      ),
    }));
  }, []);

  const removeEnhancement = useCallback((id: string) => {
    setSpec((prev) => ({
      ...prev,
      enhancements: prev.enhancements.filter((e) => e.id !== id),
    }));
    setSelectedId((prev) => (prev === id ? null : prev));
  }, []);

  const addEnhancement = useCallback((enhancement: Enhancement) => {
    setSpec((prev) => ({
      ...prev,
      enhancements: [...prev.enhancements, enhancement],
    }));
  }, []);

  const updateGlobalStyle = useCallback((updates: Partial<GlobalStyle>) => {
    setSpec((prev) => ({
      ...prev,
      global_style: { ...prev.global_style, ...updates },
    }));
  }, []);

  return (
    <SpecContext.Provider
      value={{ spec, selectedId, setSelectedId, updateEnhancement, removeEnhancement, addEnhancement, updateGlobalStyle, setSpec }}
    >
      {children}
    </SpecContext.Provider>
  );
};
