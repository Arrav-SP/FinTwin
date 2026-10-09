import { useQuery } from "@tanstack/react-query";
import { apiGet } from "./client";
import type { Experiment, SystemStatus, Validation, ValidationSummary } from "./types";

export const useSystemStatus = () => useQuery({ queryKey: ["system-status"], queryFn: () => apiGet<SystemStatus>("/api/system/status"), refetchInterval: 15_000 });
export const useExperiments = () => useQuery({ queryKey: ["experiments"], queryFn: () => apiGet<Experiment[]>("/api/experiments?limit=500") });
export const useValidations = () => useQuery({ queryKey: ["validations"], queryFn: () => apiGet<Validation[]>("/api/validation") });
export const useValidationSummary = () => useQuery({ queryKey: ["validation-summary"], queryFn: () => apiGet<ValidationSummary>("/api/validation/summary") });
