<template>
  <div class="p-6 space-y-6">
    <!-- 页面标题 -->
    <div class="flex items-center justify-between">
      <h2 class="theme-text-strong text-2xl font-bold">{{ t('admin.webhook.title') }}</h2>
      <button
        @click="showCreateForm = true"
        class="theme-brand rounded-lg px-4 py-2 text-sm font-medium text-white transition-colors"
      >
        + {{ t('admin.webhook.create') }}
      </button>
    </div>

    <!-- Webhook 列表 -->
    <div class="space-y-4">
      <div
        v-for="hook in webhooks"
        :key="hook.id"
        class="theme-surface rounded-xl border p-4"
      >
        <div class="flex items-center justify-between">
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-2">
              <span class="font-medium" v-text="hook.name"></span>
              <span
                class="rounded-full px-2 py-0.5 text-xs"
                :class="hook.enabled ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'"
                v-text="hook.enabled ? t('admin.webhook.enabled') : t('admin.webhook.disabled')"
              ></span>
            </div>
            <p class="mt-1 truncate text-xs opacity-60" v-text="hook.url"></p>
            <div class="mt-2 flex flex-wrap gap-1">
              <span
                v-for="evt in hook.events"
                :key="evt"
                class="rounded bg-blue-50 px-1.5 py-0.5 text-xs text-blue-600 dark:bg-blue-900 dark:text-blue-300"
                v-text="evt"
              ></span>
            </div>
          </div>
          <div class="ml-4 flex shrink-0 gap-2">
            <button @click="testWebhook(hook.id)" class="theme-icon-button rounded-lg p-2 text-xs" :title="t('admin.webhook.test')">
              <ZapIcon class="h-4 w-4" />
            </button>
            <button @click="toggleEnabled(hook)" class="theme-icon-button rounded-lg p-2 text-xs" :title="t('admin.webhook.toggle')">
              <PowerIcon class="h-4 w-4" />
            </button>
            <button @click="confirmAndDelete(hook.id)" class="theme-icon-button rounded-lg p-2 text-xs text-red-500" :title="t('admin.webhook.delete')">
              <TrashIcon class="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>

      <div v-if="webhooks.length === 0" class="theme-surface rounded-xl border p-8 text-center text-sm opacity-60">
        {{ t('admin.webhook.empty') }}
      </div>
    </div>

    <!-- 创建表单 -->
    <div v-if="showCreateForm" class="theme-surface rounded-xl border p-6 space-y-4">
      <h3 class="font-medium">{{ t('admin.webhook.createTitle') }}</h3>
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div>
          <label class="mb-1 block text-xs font-medium opacity-70">{{ t('admin.webhook.name') }}</label>
          <input v-model="form.name" class="theme-input w-full rounded-lg border px-3 py-2 text-sm" />
        </div>
        <div>
          <label class="mb-1 block text-xs font-medium opacity-70">URL</label>
          <input v-model="form.url" placeholder="https://example.com/webhook" class="theme-input w-full rounded-lg border px-3 py-2 text-sm" />
        </div>
      </div>
      <div>
        <label class="mb-1 block text-xs font-medium opacity-70">{{ t('admin.webhook.events') }}</label>
        <div class="flex flex-wrap gap-3">
          <label v-for="evt in availableEvents" :key="evt" class="flex items-center gap-2 text-sm">
            <input type="checkbox" :value="evt" v-model="form.events" class="rounded" />
            <span v-text="evt"></span>
          </label>
        </div>
      </div>
      <div class="flex gap-3">
        <button @click="createWebhook" class="theme-brand rounded-lg px-4 py-2 text-sm font-medium text-white">
          {{ t('admin.webhook.save') }}
        </button>
        <button @click="showCreateForm = false" class="theme-icon-button rounded-lg px-4 py-2 text-sm">
          {{ t('admin.webhook.cancel') }}
        </button>
      </div>
    </div>

    <!-- 发送日志 -->
    <div v-if="logItems.length > 0" class="theme-surface overflow-hidden rounded-xl border">
      <div class="theme-divider border-b px-4 py-3 font-medium text-sm">{{ t('admin.webhook.logs') }}</div>
      <div class="overflow-x-auto">
        <table class="w-full text-left text-xs">
          <thead class="theme-divider border-b">
            <tr>
              <th class="px-4 py-2">{{ t('admin.audit.time') }}</th>
              <th class="px-4 py-2">{{ t('admin.audit.event') }}</th>
              <th class="px-4 py-2">{{ t('admin.webhook.status') }}</th>
              <th class="px-4 py-2">{{ t('admin.webhook.result') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="log in logItems" :key="log.id" class="theme-divider border-b last:border-0">
              <td class="px-4 py-2" v-text="formatTime(log.created_at)"></td>
              <td class="px-4 py-2" v-text="log.event_type"></td>
              <td class="px-4 py-2" v-text="log.response_status || 'Timeout'"></td>
              <td class="px-4 py-2">
                <span :class="log.success ? 'text-green-600' : 'text-red-500'" v-text="log.success ? 'OK' : 'FAIL'"></span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ZapIcon, TrashIcon, PowerIcon } from 'lucide-vue-next'
import { useWebhooks } from '@/composables'

const { t } = useI18n()
const {
  webhooks, logItems, showCreateForm, availableEvents, form,
  loadWebhooks, loadLogs, createWebhook, toggleEnabled, deleteWebhook, testWebhook
} = useWebhooks()

const confirmAndDelete = async (id: number) => {
  if (!confirm(t('admin.webhook.confirmDelete'))) return
  await deleteWebhook(id)
}

const formatTime = (iso: string) => {
  return new Date(iso).toLocaleString('zh-CN', { hour12: false })
}

onMounted(() => {
  void loadWebhooks()
  void loadLogs()
})
</script>
