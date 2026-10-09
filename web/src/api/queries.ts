import { useMutation, useQuery } from "@tanstack/react-query";
import { apiGet, apiPost } from "./client";
import type { Experiment, ExperimentDetailResponse, LatencyBreakdown, ModelCard, Prediction, ScenarioCatalogue, Sweep, SweepParameter, SystemStatus, Validation, ValidationSummary, WorkloadInput } from "./types";

export const useSystemStatus = () => useQuery({ queryKey: ["system-status"], queryFn: () => apiGet<SystemStatus>("/api/system/status"), refetchInterval: 15_000 });
export const useExperiments = () => useQuery({ queryKey: ["experiments"], queryFn: () => apiGet<Experiment[]>("/api/experiments?limit=500") });
export const useValidations = () => useQuery({ queryKey: ["validations"], queryFn: () => apiGet<Validation[]>("/api/validation") });
export const useValidationSummary = () => useQuery({ queryKey: ["validation-summary"], queryFn: () => apiGet<ValidationSummary>("/api/validation/summary") });

export const useExperimentDetail = (id: string) => useQuery({ queryKey: ["experiment", id], queryFn: () => apiGet<ExperimentDetailResponse>(`/api/experiments/${id}`) });
export const useLatencyBreakdown = (id: string) => useQuery({ queryKey: ["experiment-latency", id], queryFn: () => apiGet<LatencyBreakdown>(`/api/experiments/${id}/latency`) });
export const useModels = () => useQuery({ queryKey: ["models"], queryFn: () => apiGet<ModelCard[]>("/api/models"), staleTime: 60_000 });
export const useScenarios = () => useQuery({ queryKey: ["scenarios"], queryFn: () => apiGet<ScenarioCatalogue>("/api/scenarios"), staleTime: Infinity });

export const usePredict = () => useMutation({ mutationFn: (workload: WorkloadInput) => apiPost<Prediction>("/api/predictions", workload) });
export const useSweep = () =>
  useMutation({ mutationFn: (request: { baseline: WorkloadInput; parameter: SweepParameter; values: number[] }) => apiPost<Sweep>("/api/what-if/sweep", request) });
