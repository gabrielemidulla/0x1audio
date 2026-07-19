import { Api } from "~/client"

export const api = new Api()

export type {
  AuthCredentials,
  AuthStatus,
  AppendMessageOut,
  ArtistOut,
  ArtistRefOut,
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
  PlaylistColor,
  PlaylistDetailOut,
  PlaylistSummaryOut,
  ToolTraceOut,
  TrackOut,
  TrackStatus,
  UpdatePlaylistBody,
  UpdateTrackBody,
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

export function artistImageUrl(artistId: string): string {
  return `/api/v1/catalog/artists/${artistId}/image`
}

export function userAvatarUrl(cacheKey?: string | number): string {
  const base = "/api/v1/auth/me/avatar"
  return cacheKey == null ? base : `${base}?v=${cacheKey}`
}
