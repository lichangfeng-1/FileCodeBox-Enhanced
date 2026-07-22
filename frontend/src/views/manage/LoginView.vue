<template>
  <div class="min-h-screen flex items-center justify-center py-12 px-4 sm:px-6">
    <!-- 毛玻璃登录卡片 -->
    <div class="glass-card w-full max-w-sm p-8 sm:p-10">
      <!-- 顶部高光线 -->
      <div class="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/30 to-transparent rounded-t-[1.25rem]"></div>

      <!-- Logo -->
      <div class="flex flex-col items-center">
        <div class="theme-brand flex h-14 w-14 items-center justify-center rounded-2xl">
          <BoxIcon class="h-7 w-7" />
        </div>
        <h2 class="theme-text-strong mt-5 text-2xl font-bold">
          {{ t('manage.login.title') }}
        </h2>
      </div>

      <!-- 登录表单 -->
      <form class="mt-8 space-y-5" @submit.prevent="submitLogin">
        <div>
          <label for="password" class="sr-only">{{ t('manage.login.password') }}</label>
          <input
            id="password"
            name="password"
            type="password"
            autocomplete="current-password"
            required
            v-model="password"
            class="theme-input w-full rounded-xl px-4 py-3 text-sm"
            :placeholder="t('manage.login.passwordPlaceholder')"
          />
        </div>

        <button
          type="submit"
          :disabled="isLoading"
          class="theme-brand w-full rounded-xl py-3 text-sm font-semibold disabled:opacity-50 disabled:cursor-not-allowed disabled:shadow-none disabled:transform-none"
        >
          {{ isLoading ? t('manage.login.loggingIn') : t('manage.login.loginButton') }}
        </button>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import { BoxIcon } from 'lucide-vue-next'
import { useI18n } from 'vue-i18n'
import { useAdminLogin } from '@/composables'
import { ROUTES } from '@/constants'

const { t } = useI18n()
const router = useRouter()
const route = useRoute()
const { password, isLoading, handleSubmit } = useAdminLogin()

const getRedirectPath = () => {
  const redirect = route.query.redirect
  if (typeof redirect === 'string' && redirect.startsWith('/')) {
    return redirect
  }
  return ROUTES.ADMIN
}

const submitLogin = async () => {
  const success = await handleSubmit()
  if (success) {
    await router.push(getRedirectPath())
  }
}
</script>
