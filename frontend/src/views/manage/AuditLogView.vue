<template>
  <div class="p-6 space-y-6">
    <!-- 页面标题 -->
    <div class="flex items-center justify-between">
      <h2 class="theme-text-strong text-2xl font-bold">{{ t('admin.audit.title') }}</h2>
      <button
        @click="exportCsv"
        class="theme-icon-button flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors"
      >
        <DownloadIcon class="h-4 w-4" />
        {{ t('admin.audit.export') }}
      </button>
    </div>

    <!-- 筛选栏 -->
    <div class="theme-surface rounded-xl border p-4">
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <select v-model="filters.event_type" class="theme-input rounded-lg border px-3 py-2 text-sm" @change="loadLogs">
          <option value="">{{ t('admin.audit.allEvents') }}</option>
          <option value="upload">{{ t('admin.audit.upload') }}</option>
          <option value="download">{{ t('admin.audit.download') }}</option>
          <option value="retrieve">{{ t('admin.audit.retrieve') }}</option>
          <option value="admin_login">{{ t('admin.audit.adminLogin') }}</option>
          <option value="expire">{{ t('admin.audit.expire') }}</option>
          <option value="delete">{{ t('admin.audit.delete') }}</option>
        </select>
        <input
          v-model="filters.ip"
          :placeholder="t('admin.audit.ipPlaceholder')"
          class="theme-input rounded-lg border px-3 py-2 text-sm"
          @keyup.enter="loadLogs"
        />
        <input
          v-model="filters.keyword"
          :placeholder="t('admin.audit.keywordPlaceholder')"
          class="theme-input rounded-lg border px-3 py-2 text-sm"
          @keyup.enter="loadLogs"
        />
        <button
          @click="loadLogs"
          class="theme-brand rounded-lg px-4 py-2 text-sm font-medium text-white transition-colors"
        >
          {{ t('admin.audit.search') }}
        </button>
      </div>
    </div>

    <!-- 日志表格 -->
    <div class="theme-surface overflow-hidden rounded-xl border">
      <div class="overflow-x-auto">
        <table class="w-full text-left text-sm">
          <thead class="theme-divider border-b">
            <tr>
              <th class="px-4 py-3 font-medium">{{ t('admin.audit.time') }}</th>
              <th class="px-4 py-3 font-medium">{{ t('admin.audit.event') }}</th>
              <th class="px-4 py-3 font-medium">{{ t('admin.audit.file') }}</th>
              <th class="px-4 py-3 font-medium">IP</th>
              <th class="px-4 py-3 font-medium">{{ t('admin.audit.location') }}</th>
              <th class="px-4 py-3 font-medium">{{ t('admin.audit.device') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="log in logs" :key="log.id" class="theme-divider border-b last:border-0">
              <td class="whitespace-nowrap px-4 py-3 text-xs" v-text="formatTime(log.created_at)"></td>
              <td class="px-4 py-3">
                <span
                  class="inline-flex rounded-full px-2 py-0.5 text-xs font-medium"
                  :class="eventClass(log.event_type)"
                  v-text="log.event_type"
                ></span>
              </td>
              <td class="max-w-[200px] truncate px-4 py-3">
                              <span v-text="log.file_name || '-'"></span>
                              <span
                                v-if="log.detail && log.detail.mode === 'dedup'"
                                class="ml-1 inline-flex items-center rounded-full bg-orange-100 px-1.5 py-0.5 text-[10px] font-medium text-orange-700"
                                :title="log.detail.note ? String(log.detail.note) : '秒传'"
                              >秒传</span>
                            </td>
              <td class="whitespace-nowrap px-4 py-3 font-mono text-xs" v-text="log.ip"></td>
              <td class="px-4 py-3 text-xs" v-text="log.ip_location || '-'"></td>
              <td class="px-4 py-3 text-xs" v-text="formatDevice(log)"></td>
            </tr>
            <tr v-if="logs.length === 0">
              <td colspan="6" class="px-4 py-8 text-center text-sm opacity-60">
                {{ t('admin.audit.empty') }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 分页 -->
    <div v-if="total > pageSize" class="flex items-center justify-between">
      <span class="text-sm opacity-60">{{ t('admin.audit.totalRecords', { total }) }}</span>
      <div class="flex gap-2">
        <button
          @click="prevPage"
          :disabled="page <= 1"
          class="theme-icon-button rounded-lg px-3 py-1.5 text-sm disabled:opacity-40"
        >
          &larr;
        </button>
        <span class="px-3 py-1.5 text-sm">{{ page }} / {{ totalPages }}</span>
        <button
          @click="nextPage"
          :disabled="page >= totalPages"
          class="theme-icon-button rounded-lg px-3 py-1.5 text-sm disabled:opacity-40"
        >
          &rarr;
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { DownloadIcon } from 'lucide-vue-next'
import { useAuditLogs } from '@/composables'

const { t } = useI18n()
const {
  logs, page, pageSize, total, totalPages,
  filters, loadLogs, prevPage, nextPage, exportCsv
} = useAuditLogs()

const formatTime = (iso: string) => {
  return new Date(iso).toLocaleString('zh-CN', { hour12: false })
}

const formatDevice = (log: Record<string, unknown>) => {
  const parts = [log.browser, log.os, log.device_type].filter(Boolean) as string[]
  return parts.join(' / ') || '-'
}

const eventClass = (type: string) => {
  const map: Record<string, string> = {
    upload: 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300',
    download: 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300',
    retrieve: 'bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300',
    admin_login: 'bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300',
    expire: 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400',
    delete: 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300'
  }
  return map[type] || 'bg-gray-100 text-gray-600'
}

onMounted(() => {
  void loadLogs()
})
</script>
