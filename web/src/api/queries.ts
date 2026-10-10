import { useMutation, useQuery } from "@tanstack/react-query";
import { apiGet, apiPost } from "./client";
import type { Assessment, Experiment, ExperimentDetailResponse, Job, JobRequest, LatencyBreakdown, ModelCard, Prediction, ScenarioCatalogue, Sweep, SweepParameter, SystemStatus, Validation, ValidationSummary, WorkloadInput } from "./types";

export const useSystemStatus = () => useQuery({ queryKey: ["system-status"], queryFn: () => apiGet<SystemStatus>("/api/system/status"), refetchInterval: 15_000 });
export const useExperiments = () => useQuery({ queryKey: ["experiments"], queryFn: () => apiGet<Experiment[]>("/api/experiments?limit=500") });
/** "current" keeps only checks predicted by the models now on disk. */
export type ValidationScope = "current" | "all";
export const useValidations = (scope: ValidationScope) => useQuery({ queryKey: ["validations", scope], queryFn: () => apiGet<Validation[]>(`/api/validation?scope=${scope}&limit=1000`) });
export const useValidationSummary = (scope: ValidationScope) => useQuery({ queryKey: ["validation-summary", scope], queryFn: () => apiGet<ValidationSummary>(`/api/validation/summary?scope=${scope}`) });

export const useExperimentDetail = (id: string) => useQuery({ queryKey: ["experiment", id], queryFn: () => apiGet<ExperimentDetailResponse>(`/api/experiments/${id}`) });
export const useLatencyBreakdown = (id: string) => useQuery({ queryKey: ["experiment-latency", id], queryFn: () => apiGet<LatencyBreakdown>(`/api/experiments/${id}/latency`) });
export const useModels = () => useQuery({ queryKey: ["models"], queryFn: () => apiGet<ModelCard[]>("/api/models"), staleTime: 60_000 });
export const useScenarios = () => useQuery({ queryKey: ["scenarios"], queryFn: () => apiGet<ScenarioCatalogue>("/api/scenarios"), staleTime: Infinity });

export const usePredict = () => useMutation({ mutationFn: (workload: WorkloadInput) => apiPost<Prediction>("/api/predictions", workload) });
export const useSweep = () =>
  useMutation({ mutationFn: (request: { baseline: WorkloadInput; parameter: SweepParameter; values: number[] }) => apiPost<Sweep>("/api/what-if/sweep", request) });

const ACTIVE = ["queued", "running"];

export const useJobs = () => useQuery({ queryKey: ["jobs"], queryFn: () => apiGet<Job[]>("/api/jobs") });
/** Polls while the job is queued or running, then stops. */
export const useJob = (id: string | undefined) =>
  useQuery({
    queryKey: ["job", id],
    queryFn: () => apiGet<Job>(`/api/jobs/${id}`),
    enabled: Boolean(id),
    refetchInterval: (query) => (query.state.data && !ACTIVE.includes(query.state.data.status) ? false : 700),
    // Keep following the job when the tab is not in front, so the outcome is there on return.
    refetchIntervalInBackground: true,
  });
export const useSubmitJob = () => useMutation({ mutationFn: (request: JobRequest) => apiPost<Job>("/api/jobs", request) });
export const useAssessment = (id: string) => useQuery({ queryKey: ["assessment", id], queryFn: () => apiGet<Assessment>(`/api/recommendations/${id}`) });
