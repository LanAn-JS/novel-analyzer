<template>
  <div class="p-6" v-if="novel">
    <!-- 返回 + 标题 -->
    <div class="flex items-center gap-4 mb-6">
      <el-button text @click="$router.push('/novels')">
        ← 返回
      </el-button>
      <div>
        <h2 class="text-2xl font-bold">《{{ novel.title }}》</h2>
        <p class="text-sm text-slate-500 mt-1">
          {{ novel.file_format }} · {{ formatSize(novel.file_size) }} · {{ novel.word_count?.toLocaleString() }} 字
          <el-tag v-if="novel.category" size="small" type="info" class="ml-2">{{ novel.category }}</el-tag>
        </p>
      </div>
      <div class="ml-auto flex gap-2">
        <!-- 分析中：暂停/继续按钮 -->
        <template v-if="novel.status === 'analyzing' || isPaused">
          <el-button
            v-if="!isPaused"
            type="warning"
            plain
            @click="doPause"
            :loading="pausing"
          >
            ⏸️ 暂停
          </el-button>
          <el-button
            v-if="isPaused"
            type="success"
            @click="doResume"
            :loading="resuming"
          >
            ▶️ 继续
          </el-button>
        </template>
        <!-- 非分析中：开始分析/重新分析 -->
        <el-button
          v-if="novel.status !== 'analyzing' && !isPaused"
          :type="novel.status === 'done' ? 'default' : 'primary'"
          :loading="analyzing"
          @click="doAnalyze"
        >
          {{ novel.status === 'done' ? '🔄 重新分析' : '🚀 开始分析' }}
        </el-button>
        <!-- 导出 + 打开目录 -->
        <el-dropdown v-if="novel.status === 'done'" @command="doExport">
          <el-button>📥 导出</el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="markdown">Markdown</el-dropdown-item>
              <el-dropdown-item command="pdf">PDF</el-dropdown-item>
              <el-dropdown-item command="json">JSON</el-dropdown-item>
              <el-dropdown-item command="docx">Word</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <el-button
          v-if="novel.status === 'done' && lastExportPath"
          type="default"
          plain
          @click="doOpenDir"
        >
          📂 打开目录
        </el-button>
        <!-- 删除：分析中时禁用 -->
        <el-tooltip
          v-if="novel.status === 'analyzing' || isPaused"
          content="分析中无法删除，请先暂停或等待完成"
          placement="top"
        >
          <el-button type="danger" plain disabled>🗑️ 删除</el-button>
        </el-tooltip>
        <el-button
          v-else
          type="danger"
          plain
          @click="doDelete"
        >
          🗑️ 删除
        </el-button>
      </div>
    </div>

    <!-- 标签 -->
    <div v-if="novel.tags?.length" class="mb-6 flex flex-wrap gap-2">
      <el-tag v-for="tag in novel.tags" :key="tag" effect="plain">{{ tag }}</el-tag>
    </div>

    <!-- 分析中提示 -->
    <div v-if="novel.status === 'analyzing' || isPaused" class="text-center py-12">
      <el-icon v-if="!isPaused" class="is-loading text-4xl text-indigo-400 mb-4"><Loading /></el-icon>
      <p v-else class="text-4xl mb-4">⏸️</p>
      <p class="text-lg text-slate-300">{{ isPaused ? '分析已暂停' : '正在分析中' }}</p>
      <div v-if="analyzeProgress.step" class="mt-4 space-y-3 max-w-md mx-auto">
        <div class="bg-[#1e293b] rounded-lg border border-[#475569] p-4">
          <div class="flex items-center justify-between mb-2">
            <span class="text-indigo-300 font-medium">{{ analyzeProgress.step }}</span>
            <span class="text-xs text-slate-500">{{ analyzeProgress.progress }}</span>
          </div>
          <el-progress
            :percentage="analyzePercent"
            :stroke-width="8"
            :show-text="false"
            :color="isPaused ? '#f59e0b' : '#818cf8'"
          />
          <p v-if="analyzeProgress.detail" class="text-xs text-slate-500 mt-2">{{ analyzeProgress.detail }}</p>
        </div>
        <!-- 分析步骤列表 -->
        <div class="bg-[#1e293b] rounded-lg border border-[#475569] p-3 text-left">
          <div v-for="(s, idx) in analyzeSteps" :key="idx" class="flex items-center gap-2 py-1 text-sm">
            <span v-if="s.status === 'done'" class="text-green-400">✅</span>
            <span v-else-if="s.status === 'current'" class="text-indigo-400">⏳</span>
            <span v-else class="text-slate-600">⬜</span>
            <span :class="s.status === 'current' ? 'text-slate-200' : s.status === 'done' ? 'text-slate-400' : 'text-slate-600'">{{ s.name }}</span>
          </div>
        </div>
      </div>
      <p v-else class="text-sm text-slate-600 mt-2">分析可能需要几分钟</p>
    </div>

    <!-- 待分析 -->
    <div v-else-if="novel.status === 'pending'" class="text-center py-20 text-slate-600">
      <p class="text-4xl mb-4">📊</p>
      <p>尚未分析，点击"开始分析"</p>
    </div>

    <!-- 分析结果 -->
    <div v-else-if="analysis" class="space-y-4">
      <!-- 流行性评分卡 -->
      <div class="grid grid-cols-2 gap-4">
        <div class="bg-[#1e293b] rounded-lg border border-[#475569] p-4 text-center">
          <p class="text-sm text-slate-500">🔥 题材热度</p>
          <p class="text-3xl font-bold mt-2" :class="scoreColor(analysis.genre_heat)">{{ analysis.genre_heat }}/10</p>
        </div>
        <div class="bg-[#1e293b] rounded-lg border border-[#475569] p-4 text-center">
          <p class="text-sm text-slate-500">📈 上升潜力</p>
          <p class="text-3xl font-bold mt-2" :class="scoreColor(analysis.rise_potential)">{{ analysis.rise_potential }}/10</p>
        </div>
      </div>

      <!-- 分析内容 Tab -->
      <div class="bg-[#1e293b] rounded-lg border border-[#475569]">
        <el-tabs v-model="activeTab" class="px-4 pt-4">
          <el-tab-pane label="📝 内容总结" name="summary" />
          <el-tab-pane label="✍️ 文笔分析" name="writing_style" />
          <el-tab-pane label="🏗️ 结构分析" name="structure" />
          <el-tab-pane label="📑 大纲" name="outline" />
          <el-tab-pane label="📑 细纲" name="detailed_outline" />
          <el-tab-pane label="🌍 世界观" name="worldview" />
          <el-tab-pane label="👤 人物分析" name="character_growth" />
          <el-tab-pane label="🕸️ 人物关系图" name="character_graph" />
          <el-tab-pane label="🔥 流行性" name="popularity" />
        </el-tabs>
        <div v-if="activeTab === 'character_graph' && analysis?.character_graph" class="p-4">
          <div ref="chartContainer" style="width: 100%; height: 500px;"></div>
        </div>
        <div v-else-if="activeTab === 'character_graph' && !analysis?.character_graph" class="p-4 text-center text-slate-500">
          <p class="text-4xl mb-4">🕸️</p>
          <p>未检测到人物关系图数据，请重新分析</p>
        </div>
        <div v-else class="p-4 prose prose-invert max-w-none" v-html="renderMd(currentContent)"></div>
      </div>
    </div>

    <!-- 失败 -->
    <div v-else-if="novel.status === 'failed'" class="text-center py-20">
      <p class="text-4xl mb-4">❌</p>
      <p class="text-red-400">分析失败</p>
      <p class="text-sm text-slate-500 mt-2">{{ novel.error_message }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'
import { getNovel, getAnalysis, analyzeNovel, pauseAnalysis, resumeAnalysis, exportAnalysis, openDirectory, deleteNovel } from '../api'
import { marked } from 'marked'
import * as echarts from 'echarts'

const route = useRoute()
const router = useRouter()
const novel = ref(null)
const analysis = ref(null)
const activeTab = ref('summary')
const analyzing = ref(false)
const pausing = ref(false)
const resuming = ref(false)
const isPaused = ref(false)
const lastExportPath = ref('')
const chartContainer = ref(null)
const analyzeProgress = ref({ step: '', progress: '', status: '', detail: '' })
let eventSource = null
let chartInstance = null

const STEP_NAMES = ['标签提取', '内容总结', '文笔分析', '结构分析', '大纲提取', '细纲提取', '世界观分析', '人物分析', '流行性评估']

const analyzePercent = computed(() => {
  const p = analyzeProgress.value.progress
  if (!p || p === 'done') return p === 'done' ? 100 : 0
  const match = p.match(/^(\d+)\/(\d+)$/)
  if (!match) return 0
  return Math.round((parseInt(match[1]) / parseInt(match[2])) * 100)
})

const analyzeSteps = computed(() => {
  const progress = analyzeProgress.value.progress
  let currentIdx = -1
  if (progress && progress !== 'done') {
    const match = progress.match(/^(\d+)/)
    if (match) currentIdx = parseInt(match[1]) - 1
  }
  return STEP_NAMES.map((name, idx) => ({
    name,
    status: idx < currentIdx ? 'done' : idx === currentIdx ? 'current' : 'pending'
  }))
})

const connectSSE = (novelId) => {
  if (eventSource) { eventSource.close(); eventSource = null }
  eventSource = new EventSource(`/api/novels/${novelId}/analyze/stream`)
  eventSource.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data)
      analyzeProgress.value = data
      // 更新暂停状态
      if (data.status === 'paused') {
        isPaused.value = true
      } else if (data.status === 'analyzing' && isPaused.value) {
        isPaused.value = false
      }
      if (data.progress === 'done') {
        eventSource.close()
        eventSource = null
        isPaused.value = false
        // 分析完成后自动刷新数据
        loadData()
      }
    } catch {}
  }
  eventSource.onerror = () => {
    eventSource.close()
    eventSource = null
  }
}

const formatSize = (b) => b < 1024 ? b + 'B' : b < 1048576 ? (b/1024).toFixed(1) + 'KB' : (b/1048576).toFixed(1) + 'MB'

const scoreColor = (s) => s >= 7 ? 'text-green-400' : s >= 4 ? 'text-yellow-400' : 'text-red-400'

const currentContent = computed(() => {
  if (!analysis.value) return ''
  const key = activeTab.value === 'popularity' ? 'popularity_analysis' : activeTab.value
  return analysis.value[key] || '暂无内容'
})

const renderMd = (text) => {
  if (!text) return ''
  try { return marked(text) } catch { return text.replace(/\n/g, '<br>') }
}

const loadData = async () => {
  const id = route.params.id
  try {
    const { data } = await getNovel(id)
    novel.value = data
    if (data.status === 'done') {
      try {
        const { data: a } = await getAnalysis(id)
        analysis.value = a
      } catch { analysis.value = null }
    } else {
      analysis.value = null
    }
  } catch {
    ElMessage.error('加载失败')
  }
}

const doAnalyze = async () => {
  analyzing.value = true
  try {
    await analyzeNovel(novel.value.id)
    novel.value.status = 'analyzing'
    isPaused.value = false
    analyzeProgress.value = { step: '准备中', progress: '0/9', status: 'analyzing', detail: '读取文件...' }
    ElMessage.success('分析已开始')
    connectSSE(novel.value.id)
  } catch {
    analyzing.value = false
    ElMessage.error('分析请求失败')
  }
}

const doPause = async () => {
  pausing.value = true
  try {
    await pauseAnalysis(novel.value.id)
    isPaused.value = true
    ElMessage.info('分析已暂停')
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '暂停失败')
  } finally {
    pausing.value = false
  }
}

const doResume = async () => {
  resuming.value = true
  try {
    await resumeAnalysis(novel.value.id)
    isPaused.value = false
    ElMessage.success('继续分析')
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '继续失败')
  } finally {
    resuming.value = false
  }
}

const doExport = async (format) => {
  try {
    const { data } = await exportAnalysis(novel.value.id, format)
    lastExportPath.value = data.file_path
    ElMessage.success(`已导出: ${data.file_path}`)
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '导出失败')
  }
}

const doOpenDir = async () => {
  if (!lastExportPath.value) return
  try {
    await openDirectory(lastExportPath.value)
    ElMessage.success('已打开目录')
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '打开目录失败')
  }
}

const renderChart = async () => {
  await nextTick()
  if (!chartContainer.value || !analysis.value?.character_graph) return

  // 销毁旧实例
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }

  const graphData = analysis.value.character_graph
  const nodes = (graphData.nodes || []).map(n => ({
    name: n.name,
    symbolSize: n.role === '主角' ? 60 : n.role === '反派' ? 50 : 35,
    itemStyle: {
      color: n.role === '主角' ? '#818cf8' : n.role === '反派' ? '#ef4444' : n.role === '配角' ? '#22d3ee' : '#94a3b8'
    },
    label: { show: true, fontSize: 12, color: '#e2e8f0' },
    tooltip: { formatter: `<b>${n.name}</b><br/>${n.role || ''}<br/>${n.desc || ''}` }
  }))

  const typeColors = {
    ally: '#22d3ee',
    enemy: '#ef4444',
    lover: '#f472b6',
    family: '#a78bfa',
    mentor: '#fbbf24',
    other: '#94a3b8'
  }

  const edges = (graphData.edges || []).map(e => ({
    source: e.source,
    target: e.target,
    lineStyle: {
      color: typeColors[e.type] || '#94a3b8',
      width: e.type === 'lover' || e.type === 'enemy' ? 2.5 : 1.5,
      curveness: 0.2
    },
    label: { show: true, fontSize: 10, color: '#cbd5e1', formatter: e.relation || '' },
    tooltip: { formatter: `${e.source} → ${e.target}: ${e.relation || e.type}` }
  }))

  chartInstance = echarts.init(chartContainer.value, 'dark')
  chartInstance.setOption({
    tooltip: {},
    legend: {
      data: ['主角', '配角', '反派', '其他'],
      bottom: 10,
      textStyle: { color: '#94a3b8' },
      itemWidth: 14, itemHeight: 14
    },
    series: [{
      type: 'graph',
      layout: 'force',
      roam: true,
      draggable: true,
      force: {
        repulsion: 300,
        edgeLength: [80, 200],
        gravity: 0.1
      },
      data: nodes,
      links: edges,
      emphasis: {
        focus: 'adjacency',
        lineStyle: { width: 4 }
      },
      edgeSymbol: ['none', 'arrow'],
      edgeSymbolSize: [0, 8],
      label: {
        show: true,
        position: 'right',
        formatter: '{b}'
      }
    }]
  })
}

// 图表大小自适应
const handleResize = () => { chartInstance?.resize() }

const doDelete = async () => {
  try {
    await ElMessageBox.confirm('确认删除？分析数据将一并删除。', '警告', { type: 'warning' })
    await deleteNovel(novel.value.id)
    ElMessage.success('已删除')
    router.push('/novels')
  } catch {}
}

onMounted(() => {
  loadData().then(() => {
    // 如果正在分析，连接SSE
    if (novel.value?.status === 'analyzing') {
      connectSSE(novel.value.id)
      // 检查是否暂停状态
      const current = analyzeProgress.value
      if (current.status === 'paused') {
        isPaused.value = true
      }
    }
  })
  window.addEventListener('resize', handleResize)
})
onUnmounted(() => {
  if (eventSource) { eventSource.close(); eventSource = null }
  if (chartInstance) { chartInstance.dispose(); chartInstance = null }
  window.removeEventListener('resize', handleResize)
})

// 监听路由变化，刷新数据
watch(() => route.params.id, (newId) => {
  if (newId) {
    if (eventSource) { eventSource.close(); eventSource = null }
    isPaused.value = false
    loadData().then(() => {
      if (novel.value?.status === 'analyzing') {
        connectSSE(novel.value.id)
      }
    })
  }
})

// 切到人物关系图tab时渲染
watch(activeTab, (val) => {
  if (val === 'character_graph') {
    renderChart()
  }
})
</script>
