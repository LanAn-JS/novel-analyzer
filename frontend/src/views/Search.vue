<template>
  <div class="p-6 max-w-4xl mx-auto">
    <h2 class="text-2xl font-bold mb-6">🔍 语义搜索</h2>

    <!-- 搜索框 -->
    <div class="flex gap-3 mb-6">
      <el-input
        v-model="query"
        placeholder="输入搜索内容，如：修仙穿越的小说、主角从弱变强..."
        size="large"
        @keyup.enter="doSearch"
        clearable
      />
      <el-button type="primary" size="large" :loading="searching" @click="doSearch">搜索</el-button>
    </div>

    <!-- 搜索结果 -->
    <div v-if="results.length" class="space-y-3">
      <p class="text-sm text-slate-500">找到 {{ results.length }} 条相关结果</p>
      <div
        v-for="r in results"
        :key="r.novel_id"
        class="bg-[#1e293b] rounded-lg border border-[#475569] p-4 cursor-pointer hover:border-indigo-500 transition-colors"
        @click="$router.push(`/novels/${r.novel_id}`)"
      >
        <div class="flex items-center justify-between">
          <h3 class="font-semibold">《{{ r.title }}》</h3>
          <span class="text-sm text-indigo-400">相关度 {{ (r.relevance * 100).toFixed(0) }}%</span>
        </div>
        <p v-if="r.category" class="text-sm text-slate-500 mt-1">📂 {{ r.category }}</p>
        <p class="text-sm text-slate-400 mt-2 line-clamp-2">{{ r.chunk_preview }}</p>
        <div v-if="r.tags?.length" class="mt-2 flex flex-wrap gap-1">
          <el-tag v-for="tag in r.tags.slice(0, 5)" :key="tag" size="small" type="info" effect="plain">{{ tag }}</el-tag>
        </div>
      </div>
    </div>

    <!-- 空结果 -->
    <div v-else-if="searched" class="text-center py-20 text-slate-600">
      <p class="text-4xl mb-4">🔍</p>
      <p>未找到相关小说</p>
    </div>

    <!-- AI问答 -->
    <div class="mt-12 border-t border-[#475569] pt-6">
      <h3 class="text-lg font-semibold mb-4">🤖 AI 问答</h3>
      <p class="text-sm text-slate-500 mb-3">用自然语言查询小说数据库，外部智能体也可调用此接口</p>
      <div class="flex gap-3 mb-4">
        <el-input
          v-model="agentQueryText"
          placeholder="如：有哪些修仙类且热度高的小说？"
          size="default"
          @keyup.enter="doAgentQuery"
          clearable
        />
        <el-button type="primary" :loading="agentLoading" @click="doAgentQuery">提问</el-button>
      </div>
      <div v-if="agentAnswer" class="bg-[#1e293b] rounded-lg border border-[#475569] p-4">
        <div class="prose prose-invert max-w-none" v-html="renderMd(agentAnswer)"></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { semanticSearch, agentQuery } from '../api'
import { marked } from 'marked'

const query = ref('')
const searching = ref(false)
const searched = ref(false)
const results = ref([])

const agentQueryText = ref('')
const agentLoading = ref(false)
const agentAnswer = ref('')

const doSearch = async () => {
  if (!query.value.trim()) return
  searching.value = true
  searched.value = false
  try {
    const { data } = await semanticSearch({ query: query.value, top_k: 10 })
    results.value = data.results
    searched.value = true
  } catch {
    ElMessage.error('搜索失败')
  } finally {
    searching.value = false
  }
}

const doAgentQuery = async () => {
  if (!agentQueryText.value.trim()) return
  agentLoading.value = true
  agentAnswer.value = ''
  try {
    const { data } = await agentQuery({ query: agentQueryText.value })
    agentAnswer.value = data.answer
  } catch {
    ElMessage.error('查询失败')
  } finally {
    agentLoading.value = false
  }
}

const renderMd = (text) => {
  if (!text) return ''
  try { return marked(text) } catch { return text.replace(/\n/g, '<br>') }
}
</script>
