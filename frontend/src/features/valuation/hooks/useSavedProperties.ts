import { useState, useEffect, useCallback } from 'react';
import { ValuationRequest, ValuationResponse, UserObjective } from '../../../types/valuation';

export interface SavedProperty {
  id: string;
  createdAt: string;
  title: string;
  notes?: string;
  request: ValuationRequest;
  result: ValuationResponse;
  objective: UserObjective;
}

const STORAGE_KEY = 'valora_saved_properties_v1';
const COMPARE_KEY = 'valora_compare_property_ids_v1';

export function useSavedProperties() {
  const [savedProperties, setSavedProperties] = useState<SavedProperty[]>(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      return stored ? JSON.parse(stored) : [];
    } catch {
      return [];
    }
  });

  const [compareIds, setCompareIds] = useState<string[]>(() => {
    try {
      const stored = localStorage.getItem(COMPARE_KEY);
      return stored ? JSON.parse(stored) : [];
    } catch {
      return [];
    }
  });

  // Sync to localStorage
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(savedProperties));
    } catch (e) {
      console.error('Error saving properties to localStorage:', e);
    }
  }, [savedProperties]);

  useEffect(() => {
    try {
      localStorage.setItem(COMPARE_KEY, JSON.stringify(compareIds));
    } catch (e) {
      console.error('Error saving compare list to localStorage:', e);
    }
  }, [compareIds]);

  const saveProperty = useCallback((
    request: ValuationRequest,
    result: ValuationResponse,
    objective: UserObjective,
    customTitle?: string,
    notes?: string
  ): SavedProperty => {
    const title = customTitle || `${request.tipo === 'apartamento' ? 'Apartamento' : request.tipo === 'casa' ? 'Casa' : 'Apartaestudio'} en ${request.sector}, ${request.ciudad}`;
    
    // Check if duplicate already exists (same sector, city, area and rooms)
    const existingIndex = savedProperties.findIndex(
      (p) =>
        p.request.ciudad === request.ciudad &&
        p.request.sector === request.sector &&
        p.request.area_m2 === request.area_m2 &&
        p.request.habitaciones === request.habitaciones
    );

    const newProperty: SavedProperty = {
      id: existingIndex >= 0 ? savedProperties[existingIndex].id : `prop_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`,
      createdAt: new Date().toISOString(),
      title,
      notes,
      request,
      result,
      objective,
    };

    setSavedProperties((prev) => {
      if (existingIndex >= 0) {
        const copy = [...prev];
        copy[existingIndex] = newProperty;
        return copy;
      }
      return [newProperty, ...prev];
    });

    return newProperty;
  }, [savedProperties]);

  const removeProperty = useCallback((id: string) => {
    setSavedProperties((prev) => prev.filter((p) => p.id !== id));
    setCompareIds((prev) => prev.filter((cId) => cId !== id));
  }, []);

  const isSaved = useCallback(
    (request: ValuationRequest | null | undefined): boolean => {
      if (!request) return false;
      return savedProperties.some(
        (p) =>
          p.request.ciudad === request.ciudad &&
          p.request.sector === request.sector &&
          p.request.area_m2 === request.area_m2 &&
          p.request.habitaciones === request.habitaciones
      );
    },
    [savedProperties]
  );

  const toggleCompare = useCallback((id: string) => {
    setCompareIds((prev) => {
      if (prev.includes(id)) {
        return prev.filter((cId) => cId !== id);
      }
      if (prev.length >= 4) {
        alert('Puedes comparar un máximo de 4 propiedades a la vez.');
        return prev;
      }
      return [...prev, id];
    });
  }, []);

  const clearCompare = useCallback(() => {
    setCompareIds([]);
  }, []);

  const clearAllSaved = useCallback(() => {
    setSavedProperties([]);
    setCompareIds([]);
  }, []);

  const comparedProperties = savedProperties.filter((p) => compareIds.includes(p.id));

  return {
    savedProperties,
    compareIds,
    comparedProperties,
    saveProperty,
    removeProperty,
    isSaved,
    toggleCompare,
    clearCompare,
    clearAllSaved,
  };
}
