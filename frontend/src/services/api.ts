import axios from 'axios';
import { CiudadCatalogItem, SectorCatalogItem, ValuationRequest, ValuationResponse } from '../types/valuation';

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

export const getCiudades = async (): Promise<CiudadCatalogItem[]> => {
  const response = await apiClient.get<CiudadCatalogItem[]>('/ciudades');
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
