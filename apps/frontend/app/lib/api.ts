import { Api } from "~/client"

export const api = new Api()

export type {
  AuthCredentials,
  AuthStatus,
  AppendMessageOut,
  ChatDetailOut,
  ChatMessageOut,
  ChatSummaryOut,
  CreatePlaylistBody,
  GraphLinkOut,
  GraphResponseOut,
  ImportJobOut,
  JobOut,
  JobStatus,
  PlaylistChatOut,
  PlaylistDetailOut,
  PlaylistSummaryOut,
  ToolTraceOut,
  TrackOut,
  TrackStatus,
  UpdatePlaylistBody,
  UserOut,
  UserRole,
  WaveformOut,
} from "~/client"

export function trackAudioUrl(trackId: string): string {
  return `/api/v1/catalog/tracks/${trackId}/audio`
}

export function trackCoverUrl(trackId: string): string {
  return `/api/v1/catalog/tracks/${trackId}/cover`
}
