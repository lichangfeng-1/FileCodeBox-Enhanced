import apiClient from './client'
import type { ApiResponse } from '@/types'

export interface WebhookConfig {
  id: number
  name: string
  url: string
  events: string[]
  headers: Record<string, string> | null
  enabled: boolean
  created_at: string
}

export interface WebhookLogItem {
  id: number
  webhook_id: number
  event_type: string
  response_status: number | null
  response_body: string | null
  success: boolean
  attempt: number
  created_at: string
}

export const webhookService = {
  async list(): Promise<WebhookConfig[]> {
    const res = await apiClient.get('/admin/webhook/list') as unknown as ApiResponse<WebhookConfig[]>
    return res.detail!
  },

  async create(data: {
    name: string
    url: string
    events: string[]
    headers?: Record<string, string>
    enabled?: boolean
  }) {
    const res = await apiClient.post('/admin/webhook/create', data) as unknown as ApiResponse<WebhookConfig>
    return res.detail!
  },

  async update(data: {
    id: number
    name?: string
    url?: string
    events?: string[]
    headers?: Record<string, string> | null
    enabled?: boolean
  }) {
    const res = await apiClient.patch('/admin/webhook/update', data) as unknown as ApiResponse<WebhookConfig>
    return res.detail!
  },

  async remove(id: number) {
    const res = await apiClient.delete('/admin/webhook/delete', { data: { id } }) as unknown as ApiResponse
    return res.detail!
  },

  async test(id: number) {
    const res = await apiClient.post('/admin/webhook/test', { id }) as unknown as ApiResponse
    return res.detail!
  },

  async getLogs(webhookId?: number, page = 1, size = 20) {
    const query = new URLSearchParams({ page: String(page), size: String(size) })
    if (webhookId) query.set('webhook_id', String(webhookId))
    const res = await apiClient.get(`/admin/webhook/logs?${query.toString()}`) as unknown as ApiResponse<{ data: WebhookLogItem[]; total: number }>
    return res.detail!
  }
}
