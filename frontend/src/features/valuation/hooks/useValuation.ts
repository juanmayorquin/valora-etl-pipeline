import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { postValuar } from '../../../services/api';
import { ValuationRequest, ValuationResponse, UserObjective } from '../../../types/valuation';

export const useValuation = () => {
  const [objective, setObjective] = useState<UserObjective>('ambas');
  const [lastRequest, setLastRequest] = useState<ValuationRequest | null>(null);
  const [valuationResult, setValuationResult] = useState<ValuationResponse | null>(null);
  const [isEditing, setIsEditing] = useState<boolean>(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: (data: ValuationRequest) => postValuar(data),
    onSuccess: (data, variables) => {
      setValuationResult(data);
      setLastRequest(variables);
      setIsEditing(false);
      setErrorMessage(null);
    },
    onError: (err: any) => {
      const detail = err?.response?.data?.detail;
      if (detail) {
        setErrorMessage(`No pudimos calcular la estimación: ${detail}. Verifica la ciudad y el sector.`);
      } else {
        setErrorMessage(
          'No pudimos calcular la estimación. Verifica la ciudad y el sector o intenta nuevamente.'
        );
      }
    },
  });

  const handleStartValuation = (data: ValuationRequest, obj: UserObjective) => {
    setObjective(obj);
    mutation.mutate(data);
  };

  const handleRecalculateScenario = (modifiedData: ValuationRequest) => {
    mutation.mutate(modifiedData);
  };

  const handleToggleEdit = () => {
    setIsEditing((prev) => !prev);
  };

  const loadExistingValuation = (
    req: ValuationRequest,
    res: ValuationResponse,
    obj: UserObjective
  ) => {
    setLastRequest(req);
    setValuationResult(res);
    setObjective(obj);
    setIsEditing(false);
    setErrorMessage(null);
  };

  const resetValuation = () => {
    setValuationResult(null);
    setIsEditing(true);
    setErrorMessage(null);
  };

  return {
    objective,
    setObjective,
    lastRequest,
    valuationResult,
    isEditing,
    setIsEditing,
    errorMessage,
    isLoading: mutation.isPending,
    isError: mutation.isError,
    startValuation: handleStartValuation,
    recalculateScenario: handleRecalculateScenario,
    toggleEdit: handleToggleEdit,
    loadExistingValuation,
    resetValuation,
  };
};
