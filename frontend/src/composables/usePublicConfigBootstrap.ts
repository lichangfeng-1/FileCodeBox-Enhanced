import { ConfigService } from '@/services'
import { useAlertStore } from '@/stores/alertStore'
import { useConfigStore } from '@/stores/configStore'

export function usePublicConfigBootstrap() {
  const alertStore = useAlertStore()
  const configStore = useConfigStore()

  const syncPublicConfig = async () => {
    const res = await ConfigService.getUserConfig()

    if (res.code !== 200 || !res.detail) {
      return
    }

    configStore.applyPublicMeta(res.detail.meta)
    const notifyMessage = configStore.applyRemoteConfig(res.detail.config)
    if (notifyMessage) {
      alertStore.showAlert(notifyMessage, 'success')
    }

    // 前后端分离后，动态更新页面标题和 meta 标签
    updateDocumentMeta()
  }

  const updateDocumentMeta = () => {
    const cfg = configStore.config
    if (cfg.name) {
      document.title = cfg.name
    }
    if (cfg.description) {
      const descTag = document.querySelector('meta[name="description"]')
      if (descTag) descTag.setAttribute('content', cfg.description)
    }
    if (cfg.keywords) {
      const kwTag = document.querySelector('meta[name="keywords"]')
      if (kwTag) kwTag.setAttribute('content', cfg.keywords)
    }
  }

  return {
    syncPublicConfig
  }
}
