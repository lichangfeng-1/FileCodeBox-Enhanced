<template>
  <div class="theme-page flex h-screen overflow-hidden flex-col lg:flex-row">
    <!-- 毛玻璃侧边栏 -->
    <aside
      class="theme-surface fixed inset-y-0 left-0 z-50 flex h-full w-64 shrink-0 transform flex-col border-r backdrop-blur-2xl lg:relative lg:h-screen lg:translate-x-0"
      :class="[
        isSidebarOpen ? 'translate-x-0' : '-translate-x-full',
        'transition-transform duration-300 ease-in-out lg:transition-none'
      ]"
    >
      <!-- Logo 区域 -->
      <div class="theme-divider flex h-16 shrink-0 items-center justify-between gap-3 border-b px-4">
        <div class="flex min-w-0 items-center">
          <div class="theme-brand flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl">
            <BoxIcon class="h-5 w-5 shrink-0" />
          </div>
          <h1
            @click="router.push('/')"
            class="theme-text-strong ml-2 min-w-0 truncate text-lg font-semibold cursor-pointer"
          >
            {{ t('common.appName') }}
          </h1>
        </div>
        <button @click="toggleSidebar" class="shrink-0 lg:hidden">
          <XIcon class="theme-text-muted w-5 h-5" />
        </button>
      </div>

      <!-- 导航菜单 -->
      <nav class="flex-1 overflow-y-auto custom-scrollbar">
        <ul class="p-4 space-y-1.5">
          <li v-for="item in menuItems" :key="item.id">
            <RouterLink
              :to="item.redirect"
              class="flex h-10 w-full items-center rounded-xl border-l-4 px-3 text-sm font-medium transition-all duration-200"
              :class="route.name === item.id ? 'theme-nav-item-active' : 'theme-nav-item'"
            >
              <component :is="item.icon" class="mr-3 h-5 w-5 shrink-0" />
              {{ item.name }}
            </RouterLink>
          </li>
        </ul>
      </nav>

      <!-- 退出登录 -->
      <div class="theme-divider p-4 border-t">
        <button
          @click="handleLogout"
          class="theme-icon-button flex items-center w-full p-2.5 rounded-xl text-sm"
        >
          <LogOutIcon class="w-5 h-5 mr-3" />
          {{ t('admin.logout') }}
        </button>
      </div>
    </aside>

    <!-- 主内容区 -->
    <div class="flex h-full min-h-0 min-w-0 flex-1 flex-col">
      <!-- 顶栏 -->
      <header class="theme-surface border-b h-16 backdrop-blur-xl">
        <div class="flex items-center justify-between h-16 px-4">
          <button @click="toggleSidebar" class="lg:hidden">
            <MenuIcon class="theme-text-muted w-6 h-6" />
          </button>
        </div>
      </header>

      <!-- 页面内容 -->
      <main class="min-h-0 flex-1 overflow-y-auto custom-scrollbar">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import {
  BoxIcon,
  MenuIcon,
  XIcon,
  FolderIcon,
  CogIcon,
  LayoutDashboardIcon,
  LogOutIcon,
  ScrollTextIcon,
  WebhookIcon
} from 'lucide-vue-next'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ROUTE_NAMES, ROUTES } from '@/constants'
import { useAdminSession } from '@/composables'

interface MenuItem {
  id: string
  name: string
  icon: typeof LayoutDashboardIcon
  redirect: string
}

const router = useRouter()
const route = useRoute()
const { t } = useI18n()
const { verifySession, logout } = useAdminSession()
const menuItems: MenuItem[] = [
  {
    id: ROUTE_NAMES.DASHBOARD,
    name: t('admin.dashboard.title'),
    icon: LayoutDashboardIcon,
    redirect: ROUTES.DASHBOARD
  },
  {
    id: ROUTE_NAMES.FILE_MANAGE,
    name: t('admin.fileManage.title'),
    icon: FolderIcon,
    redirect: ROUTES.FILE_MANAGE
  },
  {
    id: ROUTE_NAMES.AUDIT,
    name: t('admin.audit.title'),
    icon: ScrollTextIcon,
    redirect: ROUTES.AUDIT
  },
  {
    id: ROUTE_NAMES.WEBHOOK,
    name: t('admin.webhook.title'),
    icon: WebhookIcon,
    redirect: ROUTES.WEBHOOK
  },
  {
    id: ROUTE_NAMES.SETTINGS,
    name: t('admin.settings.title'),
    icon: CogIcon,
    redirect: ROUTES.SETTINGS
  }
]

const isSidebarOpen = ref(true)
const toggleSidebar = () => {
  isSidebarOpen.value = !isSidebarOpen.value
}

const handleResize = () => {
  if (window.innerWidth >= 1024) {
    isSidebarOpen.value = true
  } else {
    isSidebarOpen.value = false
  }
}

onMounted(() => {
  handleResize()
  window.addEventListener('resize', handleResize)
  void verifySession().then((isValid) => {
    if (!isValid) {
      void router.push(ROUTES.LOGIN)
    }
  })
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
})

const handleLogout = async () => {
  await logout()
  await router.push(ROUTES.LOGIN)
}
</script>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 6px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background-color: rgb(var(--color-scrollbar));
  border-radius: 3px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background-color: rgb(var(--color-scrollbar-hover));
}
</style>
