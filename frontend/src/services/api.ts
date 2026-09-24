import axios from 'axios';
import { CiudadCatalogItem, SectorCatalogItem, ValuationRequest, ValuationResponse } from '../types/valuation';

export interface HealthResponse {
  status: 'ready' | 'loading' | 'error';
  model_loaded: boolean;
  gold_loaded: boolean;
  error?: string | null;
}

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api',
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 120_000, // 120s: la predicción con comparables puede tardar 5-15s
});

export const getCiudades = async (): Promise<CiudadCatalogItem[]> => {
  const response = await apiClient.get<CiudadCatalogItem[]>('/ciudades');
  return response.data;
};

export const getHealth = async (): Promise<HealthResponse> => {
  const response = await apiClient.get<HealthResponse>('/health');
  return response.data;
};

export const getSectores = async (ciudad: string, query: string = ''): Promise<SectorCatalogItem[]> => {
  const response = await apiClient.get<SectorCatalogItem[]>('/sectores', {
    params: { ciudad, q: query, limite: 12 },
  });
  return response.data;
};

export const postValuar = async (data: ValuationRequest): Promise<ValuationResponse> => {
  const response = await apiClient.post<ValuationResponse>('/valuar', data);
  return response.data;
};
