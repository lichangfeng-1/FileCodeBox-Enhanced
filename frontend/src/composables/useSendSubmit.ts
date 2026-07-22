import { FileService, uploadChunkedFile } from '@/services'
import type { AlertType, ApiResponse, ExpireStyle, UploadProgress } from '@/types'
import { calculateFileHash, packFilesAsZip } from '@/utils/file-processing'
import { usePresignedUpload } from './usePresignedUpload'
import type { ExpireStyle as ExpireStyleType } from '@/types'

type Translate = (
  key: string,
  params?: Record<string, string | number | undefined>
) => string

type UseSendSubmitOptions = {
  getMaxFileSize: () => number
  notify: (message: string, type: AlertType) => void
  translate: Translate
  onProgress: (progress: UploadProgress) => void
  onHashCalculated: (hash: string) => void
}

type SubmitFileOptions = {
  selectedFile: File | null
  selectedFiles: File[]
  expireValue: number
  expireStyle: string
  enableChunk: boolean
  validateFileSize: (file: File) => boolean
  text?: string
}

type SubmitTextOptions = {
  text: string
  expireValue: number
  expireStyle: string
}

export function useSendSubmit(options: UseSendSubmitOptions) {
  const { uploadFile: presignUploadFile, reset: resetPresignUpload } = usePresignedUpload({
    getMaxFileSize: options.getMaxFileSize,
    notify: options.notify
  })

  const handleChunkUpload = async (
    file: File,
    expireValue: number,
    expireStyle: string,
    text?: string
  ): Promise<ApiResponse> => {
    // 秒传检查：计算哈希并查询是否已存在相同文件
    const fileHash = await calculateFileHash(file)
    options.onHashCalculated(fileHash)
    try {
      const dedupRes = await FileService.dedupCheck({
        file_hash: fileHash,
        file_size: file.size,
        file_name: file.name,
        expire_value: expireValue,
        expire_style: expireStyle,
        text: text || ''
      })
      if (dedupRes.code === 200 && dedupRes.detail?.existed && dedupRes.detail.code) {
        return { code: 200, detail: { code: dedupRes.detail.code, name: file.name } }
      }
    } catch {
      // 秒传检查失败不影响正常上传
    }

    return uploadChunkedFile(file, {
      expireValue,
      expireStyle,
      text,
      onHashCalculated: options.onHashCalculated,
      onProgress: (progress: UploadProgress) => {
        options.onProgress(progress)
      },
      messages: {
        initFailed: options.translate('send.messages.initChunkUploadFailed'),
        chunkFailed: (index) => options.translate('send.messages.chunkUploadFailed', { index }),
        completeFailed: options.translate('send.messages.completeUploadFailed')
      }
    })
  }

  const handlePresignedUpload = async (
    file: File,
    expireValue: number,
    expireStyle: string,
    text?: string
  ): Promise<ApiResponse<{ code?: string; name?: string }>> => {
    // 秒传检查：计算哈希并查询是否已存在相同文件
    const fileHash = await calculateFileHash(file)
    options.onHashCalculated(fileHash)
    try {
      const dedupRes = await FileService.dedupCheck({
        file_hash: fileHash,
        file_size: file.size,
        file_name: file.name,
        expire_value: expireValue,
        expire_style: expireStyle,
        text: text || ''
      })
      if (dedupRes.code === 200 && dedupRes.detail?.existed && dedupRes.detail.code) {
        return { code: 200, detail: { code: dedupRes.detail.code, name: file.name } }
      }
    } catch {
      // 秒传检查失败不影响正常上传
    }

    const code = await presignUploadFile(file, {
      expireValue,
      expireStyle: expireStyle as ExpireStyle,
      text,
      onProgress: (progress) => {
        options.onProgress(progress)
      }
    })

    if (!code) {
      throw new Error(options.translate('send.messages.uploadFailed'))
    }

    return {
      code: 200,
      detail: {
        code,
        name: file.name
      }
    }
  }

  const submitFile = async ({
    selectedFile,
    selectedFiles,
    expireValue,
    expireStyle,
    enableChunk,
    validateFileSize,
    text
  }: SubmitFileOptions): Promise<ApiResponse | null> => {
    let fileToUpload = selectedFile

    if (selectedFiles.length > 0) {
      options.notify('正在打包文件...', 'success')
      fileToUpload = await packFilesAsZip(selectedFiles)
      if (!validateFileSize(fileToUpload)) {
        return null
      }
      options.onHashCalculated(await calculateFileHash(fileToUpload))
    }

    if (!fileToUpload) {
      throw new Error(options.translate('send.messages.selectFile'))
    }

    return enableChunk
      ? handleChunkUpload(fileToUpload, expireValue, expireStyle, text)
      : handlePresignedUpload(fileToUpload, expireValue, expireStyle, text)
  }

  const submitText = ({ text, expireValue, expireStyle }: SubmitTextOptions) =>
    FileService.uploadText(text, expireValue, expireStyle)

  return {
    resetPresignUpload,
    submitFile,
    submitText
  }
}
