<template>
  <div
    class="border-t px-5 py-4 transition-colors sm:px-8 sm:py-6"
    :class="isDarkMode ? 'border-zinc-800/60 bg-zinc-900/40' : 'border-slate-100 bg-slate-50/50'"
  >
    <div class="flex items-center justify-between">
      <router-link
        v-if="linkText && linkTo"
        :to="linkTo"
        class="group flex items-center gap-1.5 text-xs font-medium transition-colors sm:gap-2 sm:text-sm"
        :class="
          isDarkMode ? 'text-zinc-400 hover:text-zinc-100' : 'text-slate-500 hover:text-zinc-950'
        "
      >
        <SendIcon
          class="h-3.5 w-3.5 transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5 sm:h-4 sm:w-4"
        />
        {{ linkText }}
      </router-link>
      <span v-else></span>

      <button
        type="button"
        @click="$emit('toggle-drawer')"
        class="group flex items-center gap-1.5 text-xs font-medium transition-colors sm:gap-2 sm:text-sm"
        :class="
          isDarkMode ? 'text-zinc-400 hover:text-zinc-100' : 'text-slate-500 hover:text-zinc-950'
        "
      >
        <HistoryIcon class="h-3.5 w-3.5 transition-transform group-hover:-rotate-12 sm:h-4 sm:w-4" />
        {{ drawerText }}
      </button>
    </div>

    <!-- 合规声明（始终显示） -->
    <p class="mt-3 text-center text-[10px] leading-relaxed opacity-40 sm:text-xs">
      请勿上传违反国家法律法规、侵犯他人知识产权或含有恶意软件的文件。上传即表示您同意承担相应法律责任。
    </p>

    <!-- ICP 备案号（填写后才显示） -->
    <p v-if="icpNumber" class="mt-1.5 text-center text-[10px] opacity-35 sm:text-xs">
      <a
        href="https://beian.miit.gov.cn/"
        target="_blank"
        rel="noopener noreferrer"
        class="hover:underline"
      >
        {{ icpNumber }}
      </a>
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed, inject } from 'vue'
import { HistoryIcon, SendIcon } from 'lucide-vue-next'
import { useConfigStore } from '@/stores/configStore'

interface Props {
  linkText?: string
  linkTo?: string
  drawerText: string
}

interface Emits {
  'toggle-drawer': []
}

defineProps<Props>()
defineEmits<Emits>()

const isDarkMode = inject('isDarkMode')
const configStore = useConfigStore()
const icpNumber = computed(() => (configStore.config as Record<string, unknown>).icp_number as string || '')
</script>
