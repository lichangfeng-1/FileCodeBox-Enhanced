import { ref, computed } from 'vue'
import { auditService, type AuditLogItem, type AuditQueryParams } from '@/services'

export function useAuditLogs() {
  const logs = ref<AuditLogItem[]>([])
  const page = ref(1)
  const pageSize = 20
  const total = ref(0)
  const totalPages = computed(() => Math.ceil(total.value / pageSize))

  const filters = ref<AuditQueryParams>({
    event_type: '',
    ip: '',
    keyword: ''
  })

  const loadLogs = async () => {
    try {
      const res = await auditService.getLogs({
        ...filters.value,
        page: page.value,
        size: pageSize,
        sort_by: 'created_at',
        sort_order: 'desc'
      })
      logs.value = res.data
      total.value = res.total
    } catch (e) {
      console.error('Failed to load audit logs:', e)
    }
  }

  const prevPage = () => {
    if (page.value > 1) {
      page.value--
      void loadLogs()
    }
  }

  const nextPage = () => {
    if (page.value < totalPages.value) {
      page.value++
      void loadLogs()
    }
  }

  const exportCsv = () => {
    const url = auditService.getExportUrl(filters.value)
    const link = document.createElement('a')
    link.href = url
    link.target = '_blank'
    link.rel = 'noopener'
    link.click()
  }

  return {
    logs,
    page,
    pageSize,
    total,
    totalPages,
    filters,
    loadLogs,
    prevPage,
    nextPage,
    exportCsv
  }
}
