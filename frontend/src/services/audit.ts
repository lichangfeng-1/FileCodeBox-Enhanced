import apiClient from './client'
import { readStoredToken } from '@/utils/auth-storage'
import type { ApiResponse } from '@/types'

export interface AuditLogItem {
  id: number
  event_type: string
  file_id: number | null
  file_code: string | null
  file_name: string | null
  ip: string
  ip_location: string | null
  browser: string | null
  browser_version: string | null
  os: string | null
  os_version: string | null
  device_type: string | null
  detail: Record<string, unknown> | null
  created_at: string
}

export interface AuditLogResponse {
  page: number
  size: number
  total: number
  data: AuditLogItem[]
}

export interface AuditQueryParams {
  page?: number
  size?: number
  event_type?: string
  file_id?: number
  ip?: string
  keyword?: string
  start_time?: string
  end_time?: string
  sort_by?: string
  sort_order?: string
}

export const auditService = {
  async getLogs(params: AuditQueryParams = {}): Promise<AuditLogResponse> {
    const query = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== '') {
        query.set(key, String(value))
      }
    })
    const res = await apiClient.get(`/admin/audit/logs?${query.toString()}`) as unknown as ApiResponse<AuditLogResponse>
    return res.detail!
  },

  async getFileTimeline(fileId: number) {
    const res = await apiClient.get(`/admin/audit/file/${fileId}/timeline`) as unknown as ApiResponse<{ file_id: number; events: unknown[] }>
    return res.detail!
  },

  getExportUrl(params: AuditQueryParams = {}): string {
    const query = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== '') {
        query.set(key, String(value))
      }
    })
    const token = readStoredToken()
    query.set('token', token)
    return `/admin/audit/export?${query.toString()}`
  }
}
