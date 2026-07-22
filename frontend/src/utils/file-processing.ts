import { sha256 } from 'js-sha256'

type JSZipConstructor = typeof import('jszip')
type JSZipModule = JSZipConstructor & {
  default?: JSZipConstructor
}

let jsZipLoader: Promise<JSZipConstructor> | null = null

const loadJSZip = async () => {
  jsZipLoader ??= import('jszip').then((module) => {
    const normalizedModule = module as unknown as JSZipModule
    return normalizedModule.default ?? normalizedModule
  })
  return jsZipLoader
}

const generateFallbackHash = (file: File): string => {
  const fileInfo = `${file.name}-${file.size}-${file.lastModified}`
  let hash = 0
  for (let i = 0; i < fileInfo.length; i++) {
    const char = fileInfo.charCodeAt(i)
    hash = (hash << 5) - hash + char
    hash = hash & hash
  }
  return Math.abs(hash).toString(16).padStart(64, '0')
}

// 分块读取的块大小（5MB），保证内存占用恒定，支持任意大小文件
const HASH_CHUNK_SIZE = 5 * 1024 * 1024

/**
 * 计算文件的完整 SHA-256 哈希（与后端 merge_chunks 的结果一致，确保秒传可用）
 * 使用 js-sha256 增量计算 + 分块读取，避免大文件一次性加载到内存
 */
export const calculateFileHash = async (file: File): Promise<string> => {
  try {
    const hasher = sha256.create()
    let offset = 0
    while (offset < file.size) {
      const chunk = file.slice(offset, offset + HASH_CHUNK_SIZE)
      const buffer = await chunk.arrayBuffer()
      hasher.update(new Uint8Array(buffer))
      offset += HASH_CHUNK_SIZE
    }
    return hasher.hex()
  } catch (error) {
    console.error('File hash calculation failed:', error)
    return generateFallbackHash(file)
  }
}

export const packFilesAsZip = async (files: File[]): Promise<File> => {
  const JSZip = await loadJSZip()
  const zip = new JSZip()
  for (const file of files) {
    zip.file(file.name, file)
  }
  const blob = await zip.generateAsync({
    type: 'blob',
    compression: 'DEFLATE',
    compressionOptions: { level: 6 }
  })
  return new File([blob], `files_${Date.now()}.zip`, { type: 'application/zip' })
}
