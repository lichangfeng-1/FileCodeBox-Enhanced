import { ref } from 'vue'
import { webhookService, type WebhookConfig, type WebhookLogItem } from '@/services'

export function useWebhooks() {
  const webhooks = ref<WebhookConfig[]>([])
  const logItems = ref<WebhookLogItem[]>([])
  const showCreateForm = ref(false)
  const availableEvents = ['file.uploaded', 'file.retrieved', 'file.expired']

  const form = ref({
    name: '',
    url: '',
    events: [] as string[]
  })

  const loadWebhooks = async () => {
    try {
      webhooks.value = await webhookService.list()
    } catch (e) {
      console.error('Failed to load webhooks:', e)
    }
  }

  const loadLogs = async () => {
    try {
      const res = await webhookService.getLogs(undefined, 1, 10)
      logItems.value = res.data
    } catch (e) {
      console.error('Failed to load webhook logs:', e)
    }
  }

  const createWebhook = async () => {
    if (!form.value.name || !form.value.url || form.value.events.length === 0) return
    try {
      await webhookService.create({
        name: form.value.name,
        url: form.value.url,
        events: form.value.events
      })
      showCreateForm.value = false
      form.value = { name: '', url: '', events: [] }
      await loadWebhooks()
    } catch (e) {
      console.error('Failed to create webhook:', e)
    }
  }

  const toggleEnabled = async (hook: WebhookConfig) => {
    try {
      await webhookService.update({ id: hook.id, enabled: !hook.enabled })
      await loadWebhooks()
    } catch (e) {
      console.error('Failed to toggle webhook:', e)
    }
  }

  const deleteWebhook = async (id: number) => {
    try {
      await webhookService.remove(id)
      await loadWebhooks()
    } catch (e) {
      console.error('Failed to delete webhook:', e)
    }
  }

  const testWebhook = async (id: number) => {
    try {
      await webhookService.test(id)
      await loadLogs()
    } catch (e) {
      console.error('Failed to test webhook:', e)
    }
  }

  return {
    webhooks,
    logItems,
    showCreateForm,
    availableEvents,
    form,
    loadWebhooks,
    loadLogs,
    createWebhook,
    toggleEnabled,
    deleteWebhook,
    testWebhook
  }
}
