<template>
  <div class="p-6 max-w-4xl mx-auto">
    <h2 class="text-2xl font-bold mb-6">💾 存储空间</h2>

    <!-- 总览卡片 -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
      <div class="bg-[#1e293b] rounded-lg border border-[#475569] p-5">
        <p class="text-sm text-slate-500">数据库大小</p>
        <p class="text-3xl font-bold mt-2 text-indigo-400">{{ stats.storage?.db_size_human || '--' }}</p>
        <p class="text-xs text-slate-600 mt-2">SQLite 元数据</p>
      </div>
      <div class="bg-[#1e293b] rounded-lg border border-[#475569] p-5">
        <p class="text-sm text-slate-500">数据目录总占用</p>
        <p class="text-3xl font-bold mt-2 text-cyan-400">{{ stats.storage?.data_size_human || '--' }}</p>
        <p class="text-xs text-slate-600 mt-2">含数据库、向量索引、上传文件等</p>
      </div>
      <div class="bg-[#1e293b] rounded-lg border border-[#475569] p-5">
        <p class="text-sm text-slate-500">磁盘剩余空间</p>
        <p class="text-3xl font-bold mt-2" :class="stats.storage?.disk_free && stats.storage.disk_free < 1073741824 ? 'text-red-400' : 'text-green-400'">
          {{ stats.storage?.disk_free_human || '--' }}
        </p>
        <p class="text-xs text-slate-600 mt-2">总 {{ stats.storage?.disk_total_human }} / 已用 {{ stats.storage?.disk_used_human }}</p>
      </div>
    </div>

    <!-- 磁盘使用进度条 -->
    <div class="bg-[#1e293b] rounded-lg border border-[#475569] p-5 mb-6">
      <div class="flex items-center justify-between mb-2">
        <span class="text-sm text-slate-400">磁盘使用率</span>
        <span class="text-sm font-bold" :class="diskPercent > 90 ? 'text-red-400' : 'text-slate-300'">{{ diskPercent }}%</span>
      </div>
      <div class="w-full bg-[#0f172a] rounded-full h-3 overflow-hidden">
        <div
          class="h-full rounded-full transition-all duration-500"
          :class="diskPercent > 90 ? 'bg-red-500' : diskPercent > 70 ? 'bg-yellow-500' : 'bg-indigo-500'"
          :style="{ width: diskPercent + '%' }"
        />
      </div>
      <div class="flex justify-between text-xs text-slate-600 mt-1">
        <span>已用 {{ stats.storage?.disk_used_human }}</span>
        <span>总计 {{ stats.storage?.disk_total_human }}</span>
      </div>
    </div>

    <!-- 数据目录明细 -->
    <div class="bg-[#1e293b] rounded-lg border border-[#475569] p-5 mb-6">
      <h3 class="font-semibold mb-3">📂 数据目录明细</h3>
      <div class="space-y-2">
        <div v-for="(info, name) in stats.storage?.breakdown" :key="name"
          class="flex items-center gap-3 text-sm"
        >
          <span class="text-slate-400 w-32 truncate">{{ name }}</span>
          <div class="flex-1 bg-[#0f172a] rounded-full h-2 overflow-hidden">
            <div class="h-full rounded-full" :class="breakdownColor(name)"
              :style="{ width: breakdownPercent(info.size) + '%' }" />
          </div>
          <span class="text-slate-300 w-20 text-right font-mono">{{ info.size_human }}</span>
        </div>
      </div>
    </div>

    <!-- 统计信息 -->
    <div class="bg-[#1e293b] rounded-lg border border-[#475569] p-5">
      <h3 class="font-semibold mb-3">📊 数据统计</h3>
      <div class="grid grid-cols-2 gap-4 text-sm">
        <div class="flex justify-between">
          <span class="text-slate-500">小说总数</span>
          <span>{{ stats.total_novels ?? '--' }}</span>
        </div>
        <div class="flex justify-between">
          <span class="text-slate-500">已分析</span>
          <span class="text-green-400">{{ stats.analyzed_novels ?? '--' }}</span>
        </div>
        <div class="flex justify-between">
          <span class="text-slate-500">待分析</span>
          <span>{{ (stats.total_novels ?? 0) - (stats.analyzed_novels ?? 0) }}</span>
        </div>
        <div class="flex justify-between">
          <span class="text-slate-500">分类数</span>
          <span>{{ stats.categories ? Object.keys(stats.categories).length : '--' }}</span>
        </div>
      </div>

      <!-- 分类分布 -->
      <div v-if="stats.categories && Object.keys(stats.categories).length" class="mt-4 pt-4 border-t border-[#475569]">
        <p class="text-sm text-slate-400 mb-2">分类分布</p>
        <div class="space-y-2">
          <div v-for="(count, cat) in stats.categories" :key="cat" class="flex items-center gap-3 text-sm">
            <span class="text-slate-500 w-20 truncate">{{ cat }}</span>
            <div class="flex-1 bg-[#0f172a] rounded-full h-2 overflow-hidden">
              <div class="h-full bg-indigo-500/60 rounded-full" :style="{ width: (count / maxCategoryCount * 100) + '%' }" />
            </div>
            <span class="text-slate-400 w-8 text-right">{{ count }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { getStats } from '../api'

const stats = ref({})

const diskPercent = computed(() => {
  const s = stats.value.storage
  if (!s || !s.disk_total) return 0
  return Math.round(s.disk_used / s.disk_total * 100)
})

const maxCategoryCount = computed(() => {
  const cats = stats.value.categories
  if (!cats) return 1
  return Math.max(...Object.values(cats), 1)
})

const maxBreakdownSize = computed(() => {
  const bd = stats.value.storage?.breakdown
  if (!bd) return 1
  return Math.max(...Object.values(bd).map(v => v.size), 1)
})

const breakdownPercent = (size) => {
  return Math.round(size / maxBreakdownSize.value * 100)
}

const breakdownColor = (name) => {
  if (name.startsWith('chroma')) return 'bg-cyan-500/60'
  if (name.startsWith('uploads')) return 'bg-indigo-500/60'
  if (name.startsWith('exports')) return 'bg-green-500/60'
  if (name.endsWith('.db')) return 'bg-yellow-500/60'
  return 'bg-slate-500/60'
}

onMounted(async () => {
  try {
    const { data } = await getStats()
    stats.value = data
  } catch {}
})
</script>
