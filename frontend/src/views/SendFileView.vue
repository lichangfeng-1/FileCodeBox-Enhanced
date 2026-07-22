<template>
  <div
    class="relative flex min-h-screen flex-col items-center justify-center overflow-hidden p-4 sm:p-8"
    @paste.prevent="handlePaste"
  >
    <!-- 主卡片 -->
    <div class="relative z-10 w-full max-w-md">
      <div class="glass-card relative overflow-hidden rounded-[2rem] sm:rounded-[2.5rem]">
        <!-- 顶部高光线 -->
        <div class="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/30 to-transparent"></div>

        <div class="px-6 pb-7 pt-10 sm:px-9 sm:pb-9 sm:pt-12">
          <PageHeader
            :title="t('send.title')"
            :subtitle="t('send.uploadArea.placeholder')"
            mode="send"
            @title-click="toRetrieve"
          />

          <form @submit.prevent="handleSubmit" class="space-y-5 sm:space-y-6">
            <!-- 文件上传区域（始终显示）-->
            <FileUploadArea
              class="payload-panel"
              :selected-file="selectedFile"
              :selected-files="selectedFiles"
              :progress="uploadProgress"
              :uploaded-bytes="uploadedBytes"
              :total-bytes="totalBytes"
              :upload-speed="uploadSpeed"
              :upload-status="isSubmitting ? 'uploading' : 'idle'"
              :description="uploadDescription"
              :accepted-types="acceptedTypes"
              @file-selected="handleFileSelected"
              @files-selected="handleFilesSelected"
              @file-drop="handleFileDrop"
            />

            <!-- 文本/备注区域（始终显示）-->
            <TextInputArea
              v-model="textContent"
              class="text-panel"
              :placeholder="textPlaceholder"
            />

            <!-- 过期方式 -->
            <ExpirationSelector
              v-model:expiration-method="expirationMethod"
              v-model:expiration-value="expirationValue"
              :options="expirationOptions"
            />

            <!-- 提交按钮 -->
            <button
              type="submit"
              :disabled="isSubmitting || !canSubmit"
              class="theme-brand flex w-full items-center justify-center gap-2 rounded-2xl py-3.5 text-sm font-semibold tracking-wide sm:py-4 sm:text-base disabled:cursor-not-allowed disabled:opacity-40 disabled:shadow-none disabled:transform-none"
            >
              <LoaderCircleIcon v-if="isSubmitting" class="h-4 w-4 animate-spin sm:h-5 sm:w-5" />
              <SendIcon v-else class="h-4 w-4 sm:h-5 sm:w-5" />
              {{ isSubmitting ? t('send.submitting') : t('send.submit') }}
            </button>
          </form>
        </div>

        <!-- 底部导航 + 合规声明 -->
        <PageFooter
          :link-text="t('send.needRetrieveFile')"
          link-to="/"
          :drawer-text="t('send.sendRecords')"
          @toggle-drawer="toggleDrawer"
        />
      </div>
    </div>

    <!-- 发件记录抽屉 -->
    <SideDrawer :visible="showDrawer" :title="t('send.sendRecords')" @close="toggleDrawer">
      <SentRecordList
        :records="sendRecords"
        @copy-link="copySentRecordLink"
        @view-details="viewDetails"
        @delete-record="deleteRecord"
      />
    </SideDrawer>

    <!-- 发件详情弹窗 -->
    <SentRecordDetailModal
      :record="selectedRecord"
      :get-q-r-code-value="getQRCodeValue"
      @close="closeDetails"
      @copy-code="copySentRecordCode"
      @copy-link="copySentRecordLink"
      @copy-wget="copySentRecordWgetCommand"
    />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { LoaderCircleIcon, SendIcon } from 'lucide-vue-next'
import PageFooter from '@/components/common/PageFooter.vue'
import PageHeader from '@/components/common/PageHeader.vue'
import FileUploadArea from '@/components/common/FileUploadArea.vue'
import ExpirationSelector from '@/components/common/ExpirationSelector.vue'
import TextInputArea from '@/components/common/TextInputArea.vue'
import SideDrawer from '@/components/common/SideDrawer.vue'
import SentRecordList from '@/components/common/SentRecordList.vue'
import SentRecordDetailModal from '@/components/common/SentRecordDetailModal.vue'
import { useSendFlow } from '@/composables'

const { t } = useI18n()
const router = useRouter()
const {
  sendType,
  selectedFile,
  selectedFiles,
  textContent,
  expirationMethod,
  expirationValue,
  uploadProgress,
  uploadedBytes,
  totalBytes,
  uploadSpeed,
  acceptedTypes,
  showDrawer,
  selectedRecord,
  isSubmitting,
  sendRecords,
  uploadDescription,
  expirationOptions,
  closeDetails,
  copySentRecordCode,
  copySentRecordLink,
  copySentRecordWgetCommand,
  deleteRecord,
  getQRCodeValue,
  handleFileDrop,
  handleFileSelected,
  handleFilesSelected,
  handlePaste,
  handleSubmit,
  toggleDrawer,
  viewDetails
} = useSendFlow()

/** 是否有文件被选择 */
const hasFiles = computed(() => {
  return selectedFiles.value.length > 0 || !!selectedFile.value
})

/** 是否可以提交（至少有文件或文本） */
const canSubmit = computed(() => {
  return hasFiles.value || textContent.value.trim().length > 0
})

/** 文本框动态 placeholder */
const textPlaceholder = computed(() => {
  return hasFiles.value
    ? t('send.uploadArea.textNote')
    : t('send.uploadArea.textInput')
})

const toRetrieve = () => {
  router.push('/')
}
</script>

<style scoped>
:deep(.payload-panel) {
  min-height: 9rem;
}

:deep(.text-panel) {
  min-height: 5rem;
}

:deep(.text-panel textarea) {
  min-height: 5rem;
  resize: vertical;
}

@media (min-width: 640px) {
  :deep(.payload-panel) {
    min-height: 10rem;
  }
  :deep(.text-panel) {
    min-height: 6rem;
  }
}
</style>
