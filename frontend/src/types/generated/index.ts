/**
 * Re-export generated API types for easier imports.
 *
 * Usage:
 *   import type { LoginRequest, UserResponse, ActivitySummary } from '@/types/generated';
 *
 * Note: This file is manually maintained but types come from auto-generated api.ts.
 * Run `npm run generate:api` to update api.ts when backend changes.
 */

export type { paths, components, operations } from './api';

// Convenience type aliases for common schemas
export type Schemas = import('./api').components['schemas'];

// Auth types
export type LoginRequest = Schemas['LoginRequest'];
export type LoginResponse = Schemas['LoginResponse'];
export type UserResponse = Schemas['UserResponse'];
export type GarminConnectRequest = Schemas['GarminConnectRequest'];
export type GarminConnectResponse = Schemas['GarminConnectResponse'];
export type GarminStatusResponse = Schemas['GarminStatusResponse'];
export type DisconnectResponse = Schemas['DisconnectResponse'];

// Ingest types
export type IngestRunRequest = Schemas['IngestRunRequest'];
export type IngestRunResponse = Schemas['IngestRunResponse'];
export type IngestStatusResponse = Schemas['IngestStatusResponse'];
export type SyncStateResponse = Schemas['SyncStateResponse'];
export type SyncHistoryResponse = Schemas['SyncHistoryResponse'];
export type SyncHistoryItem = Schemas['SyncHistoryItem'];

// Activity types
export type ActivityListResponse = Schemas['ActivityListResponse'];
export type ActivitySummary = Schemas['ActivitySummary'];
export type ActivityDetailResponse = Schemas['ActivityDetailResponse'];
export type ActivityMetricResponse = Schemas['ActivityMetricResponse'];
export type SamplesListResponse = Schemas['SamplesListResponse'];
export type SampleResponse = Schemas['SampleResponse'];
export type HRZonesResponse = Schemas['HRZonesResponse'];
export type HRZoneResponse = Schemas['HRZoneResponse'];
export type LapsResponse = Schemas['LapsResponse'];
export type LapResponse = Schemas['LapResponse'];

// Gear types
export type GearListResponse = Schemas['GearListResponse'];
export type GearSummaryResponse = Schemas['GearSummaryResponse'];
export type GearDetailResponse = Schemas['GearDetailResponse'];
export type ActivityGearsResponse = Schemas['ActivityGearsResponse'];

// Health types
export type SleepListResponse = Schemas['SleepListResponse'];
export type SleepDetailResponse = Schemas['SleepDetailResponse'];
export type HeartRateListResponse = Schemas['HeartRateListResponse'];
export type HeartRateSummary = Schemas['HeartRateSummary'];
export type BodyCompositionListResponse = Schemas['BodyCompositionListResponse'];
export type FitnessMetricListResponse = Schemas['FitnessMetricListResponse'];
export type MetricsSummary = Schemas['MetricsSummary'];

// Dashboard types
export type DashboardSummaryResponse = Schemas['DashboardSummaryResponse'];
export type WeeklySummary = Schemas['WeeklySummary'];
export type RecentActivity = Schemas['RecentActivity'];
export type HealthStatus = Schemas['HealthStatus'];
export type FitnessStatus = Schemas['FitnessStatus'];

// Calendar types
export type CalendarResponse = Schemas['CalendarResponse'];
export type CalendarDay = Schemas['CalendarDay'];

// Workout types
export type WorkoutResponse = Schemas['WorkoutResponse'];
export type WorkoutSchema = Schemas['WorkoutSchema'];
export type WorkoutSummary = Schemas['WorkoutSummary'];
export type WorkoutListResponse = Schemas['WorkoutListResponse'];

// Plan types
export type PlanResponse = Schemas['PlanResponse'];
export type PlanListResponse = Schemas['PlanListResponse'];
export type PlanDetailResponse = Schemas['PlanDetailResponse'];

// Race types
export type RaceResponse = Schemas['RaceResponse'];
export type RacesListResponse = Schemas['RacesListResponse'];

// Analytics types
export type TrendsResponse = Schemas['TrendsResponse'];
export type CompareResponse = Schemas['CompareResponse'];
export type PersonalRecordsResponse = Schemas['PersonalRecordsResponse'];

// AI Chat types
export type ConversationResponse = Schemas['ConversationResponse'];
export type ConversationListResponse = Schemas['ConversationListResponse'];
export type MessageResponse = Schemas['MessageResponse'];
export type ChatRequest = Schemas['ChatRequest'];
export type ChatResponse = Schemas['ChatResponse'];
