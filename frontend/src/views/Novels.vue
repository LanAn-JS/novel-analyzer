<template>
  <div class="p-6">
    <!-- 头部 -->
    <div class="flex items-center justify-between mb-6">
      <div>
        <h2 class="text-2xl font-bold">📖 小说库</h2>
        <p class="text-sm text-slate-500 mt-1">共 {{ novels.length }} 部小说</p>
      </div>
      <div class="flex gap-3">
        <el-select v-model="filterCategory" placeholder="分类筛选" clearable size="default" style="width:140px">
          <el-option v-for="c in categories" :key="c" :label="c" :value="c" />
        </el-select>
        <el-select v-model="filterStatus" placeholder="状态筛选" clearable size="default" style="width:140px">
          <el-option label="待分析" value="pending" />
          <el-option label="分析中" value="analyzing" />
          <el-option label="已完成" value="done" />
          <el-option label="失败" value="failed" />
        </el-select>
        <el-button type="primary" @click="showUpload = true">
          📤 上传小说
        </el-button>
      </div>
    </div>

    <!-- 小说网格 -->
    <div v-if="filteredNovels.length" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
      <div
        v-for="novel in filteredNovels"
        :key="novel.id"
        class="bg-[#1e293b] rounded-lg border border-[#475569] p-4 cursor-pointer hover:border-indigo-500 transition-colors"
        @click="$router.push(`/novels/${novel.id}`)"
      >
        <div class="flex items-start justify-between">
          <h3 class="font-semibold text-lg truncate flex-1">{{ novel.title }}</h3>
          <el-tag :type="statusType(novel.status)" size="small">{{ statusLabel(novel.status) }}</el-tag>
        </div>
        <div class="mt-2 text-sm text-slate-500 space-y-1">
          <p>📄 {{ novel.file_format }} · {{ formatSize(novel.file_size) }}</p>
          <p>📝 {{ novel.word_count?.toLocaleString() }} 字</p>
          <p v-if="novel.category" class="text-indigo-400">📂 {{ novel.category }}</p>
        </div>
        <div v-if="novel.tags?.length" class="mt-3 flex flex-wrap gap-1">
          <el-tag v-for="tag in novel.tags.slice(0, 5)" :key="tag" size="small" type="info" effect="plain">{{ tag }}</el-tag>
          <el-tag v-if="novel.tags.length > 5" size="small" type="info">+{{ novel.tags.length - 5 }}</el-tag>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else class="text-center py-20 text-slate-600">
      <p class="text-4xl mb-4">📚</p>
      <p>还没有小说，点击右上角上传</p>
    </div>

    <!-- 上传对话框 -->
    <el-dialog v-model="showUpload" title="📤 上传小说" width="500px" :close-on-click-modal="false" @close="onUploadDialogClose">
      <el-upload
        ref="uploadRef"
        drag
        :auto-upload="false"
        :limit="1"
        accept=".txt,.epub,.pdf,.docx,.md,.rtf"
        :on-change="onFileChange"
        :on-exceed="onFileExceed"
        :disabled="uploading"
      >
        <div class="py-4">
          <p class="text-4xl mb-2">📄</p>
          <p>拖拽文件到此处，或点击选择</p>
          <p class="text-xs text-slate-500 mt-2">支持：TXT、EPUB、PDF、DOCX、MD、RTF</p>
        </div>
      </el-upload>
      <template #footer>
        <el-button @click="cancelUpload" :disabled="uploading">取消</el-button>
        <el-button type="primary" :loading="uploading" @click="doUpload">
          {{ uploading ? '上传中...' : '上传' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElNotification } from 'element-plus'
import { getNovels, uploadNovel, analyzeNovel, getCategories } from '../api'

const novels = ref([])
const categories = ref([])
const filterCategory = ref('')
const filterStatus = ref('')
const showUpload = ref(false)
const uploading = ref(false)
const selectedFile = ref(null)

const filteredNovels = computed(() => {
  return novels.value.filter(n => {
    if (filterCategory.value && n.category !== filterCategory.value) return false
    if (filterStatus.value && n.status !== filterStatus.value) return false
    return true
  })
})

const statusType = (s) => ({ pending: 'info', analyzing: 'warning', done: 'success', failed: 'danger' }[s] || 'info')
const statusLabel = (s) => ({ pending: '待分析', analyzing: '分析中', done: '已完成', failed: '失败' }[s] || s)
const formatSize = (b) => b < 1024 ? b + 'B' : b < 1048576 ? (b/1024).toFixed(1) + 'KB' : (b/1048576).toFixed(1) + 'MB'

const onFileChange = (file) => {
  selectedFile.value = file.raw
}

const onFileExceed = (files, uploadFiles) => {
  // 超出limit时，替换为新选择的文件
  uploadFiles.splice(0, uploadFiles.length)
  uploadFiles.push(files[0])
  selectedFile.value = files[0].raw || files[0]
}

const cancelUpload = () => {
  showUpload.value = false
  if (uploadController) {
    uploadController.abort()
    uploadController = null
  }
  uploading.value = false
  selectedFile.value = null
}

const onUploadDialogClose = () => {
  selectedFile.value = null
  // 清空上传组件文件列表，下次打开可以重新选
  nextTick(() => {
    uploadRef.value?.clearFiles()
  })
  if (!uploading.value) return
  if (uploadController) {
    uploadController.abort()
    uploadController = null
  }
  uploading.value = false
}

let uploadController = null

const doUpload = async () => {
  if (!selectedFile.value) {
    ElMessage.warning('请先选择文件')
    return
  }
  uploading.value = true
  uploadController = new AbortController()
  try {
    const fd = new FormData()
    fd.append('file', selectedFile.value)
    const { data } = await uploadNovel(fd, uploadController.signal)
    ElMessage.success(`${data.title} 上传成功！`)
    showUpload.value = false
    selectedFile.value = null
    uploadController = null
    // 刷新小说列表
    await loadNovels()
    ElNotification({ title: '上传完成', message: `《${data.title}》已上传，可在小说列表中点击分析`, type: 'success', duration: 5000 })
  } catch (e) {
    if (e.name === 'CanceledError' || e.code === 'ERR_CANCELED') {
      ElMessage.info('已取消上传')
    } else {
      ElMessage.error(e.response?.data?.detail || '上传失败')
    }
  } finally {
    uploading.value = false
    uploadController = null
  }
}

const route = useRoute()

const loadNovels = async () => {
  try {
    const { data } = await getNovels()
    novels.value = data
  } catch {}
}

onMounted(async () => {
  await loadNovels()
  try {
    const { data } = await getCategories()
    categories.value = data.categories
  } catch {}
  checkPolling()
})

// 路由变化时刷新列表（从详情页返回时）
watch(() => route.path, async () => {
  await loadNovels()
  try {
    const { data } = await getCategories()
    categories.value = data.categories
  } catch {}
})

// 轮询：当有正在分析的小说时，每10秒刷新一次状态
let pollTimer = null
const checkPolling = () => {
  const hasAnalyzing = novels.value.some(n => n.status === 'analyzing')
  if (hasAnalyzing && !pollTimer) {
    pollTimer = setInterval(async () => {
      await loadNovels()
      try { const { data } = await getCategories(); categories.value = data.categories } catch {}
      checkPolling() // 刷新后再检查，分析完成就停轮询
    }, 10000)
  } else if (!hasAnalyzing && pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}
</script>
