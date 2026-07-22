<template>
  <div class="relative flex min-h-screen flex-col items-center justify-center overflow-hidden p-4 sm:p-8">
    <!-- 主卡片 -->
    <div class="relative z-10 w-full max-w-md">
      <div class="glass-card relative overflow-hidden rounded-[2rem] sm:rounded-[2.5rem]">
        <!-- 顶部高光线 -->
        <div class="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/30 to-transparent"></div>

        <div class="px-6 pb-8 pt-10 sm:px-9 sm:pb-10 sm:pt-12">
          <PageHeader
            :title="t('retrieve.title')"
            :subtitle="t('retrieve.codeInput.placeholder')"
            mode="retrieve"
            @title-click="toSend"
          />
          <RetrieveForm
            v-model="code"
            :input-status="inputStatus"
            :error="!!error"
            @submit="handleSubmit"
          />
        </div>

        <PageFooter
          :link-text="t('retrieve.needSendFile')"
          link-to="/send"
          :drawer-text="t('retrieve.recordsDrawer')"
          @toggle-drawer="toggleDrawer"
        />
      </div>
    </div>

    <!-- 取件记录抽屉 -->
    <SideDrawer :visible="showDrawer" :title="t('retrieve.recordsDrawer')" @close="toggleDrawer">
      <FileRecordList
        :records="records"
        @view-details="viewDetails"
        @download-record="downloadRecord"
        @delete-record="deleteRecord"
      />
    </SideDrawer>

    <!-- 文件详情弹窗 -->
    <FileDetailModal
      :visible="!!selectedRecord"
      :record="selectedRecord"
      @close="closeDetails"
      @preview-content="showContentPreview"
    />

    <!-- 内容预览弹窗 -->
    <ContentPreviewModal
      :visible="showPreview"
      :rendered-content="renderedContent"
      @close="closeContentPreview"
      @copy-content="copyContent"
    />
  </div>
</template>

<script setup lang="ts">
import { onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import PageHeader from '@/components/common/PageHeader.vue'
import RetrieveForm from '@/components/common/RetrieveForm.vue'
import PageFooter from '@/components/common/PageFooter.vue'
import SideDrawer from '@/components/common/SideDrawer.vue'
import FileDetailModal from '@/components/common/FileDetailModal.vue'
import FileRecordList from '@/components/common/FileRecordList.vue'
import ContentPreviewModal from '@/components/common/ContentPreviewModal.vue'
import { useRetrieveFlow } from '@/composables'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const {
  code,
  inputStatus,
  error,
  records,
  selectedRecord,
  showDrawer,
  showPreview,
  renderedContent,
  closeContentPreview,
  closeDetails,
  copyContent,
  deleteRecord,
  downloadRecord,
  handleSubmit,
  showContentPreview,
  toggleDrawer,
  viewDetails
} = useRetrieveFlow()

const toSend = () => {
  router.push('/send')
}

onMounted(() => {
  const queryCode = route.query.code
  if (queryCode && typeof queryCode === 'string') {
    code.value = queryCode
  }
})

watch(code, (newCode) => {
  if (newCode.length === 5) {
    void handleSubmit()
  }
})
</script>
