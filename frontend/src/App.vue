<template>
  <div class="flex h-screen">
    <!-- 侧边栏 -->
    <aside class="w-56 flex-shrink-0 bg-[#1e293b] border-r border-[#475569] flex flex-col">
      <!-- Logo -->
      <div class="p-4 border-b border-[#475569]">
        <h1 class="text-lg font-bold text-indigo-400">📚 Novel Analyzer</h1>
        <p class="text-xs text-slate-500 mt-1">小说智能分析系统</p>
      </div>

      <!-- 导航 -->
      <nav class="flex-1 py-4">
        <router-link
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          class="flex items-center gap-3 px-4 py-3 text-sm transition-colors"
          :class="$route.path === item.path || (item.path !== '/' && $route.path.startsWith(item.path))
            ? 'text-indigo-400 bg-indigo-500/10'
            : 'text-slate-400 hover:text-slate-200 hover:bg-slate-700/50'"
        >
          <span class="text-lg">{{ item.icon }}</span>
          <span>{{ item.label }}</span>
        </router-link>
      </nav>

      <!-- 署名 -->
      <div class="p-4 border-t border-[#475569]">
        <p class="text-xs text-slate-600">by:蓝桉, 微信:379794746</p>
        <p class="text-xs text-slate-700 mt-1">v1.0.0</p>
      </div>
    </aside>

    <!-- 主内容 -->
    <main class="flex-1 overflow-auto bg-[#0f172a]">
      <router-view />
    </main>
  </div>
</template>

<script setup>
const navItems = [
  { path: '/novels', icon: '📖', label: '小说库' },
  { path: '/search', icon: '🔍', label: '语义搜索' },
  { path: '/settings', icon: '⚙️', label: 'API设置' },
  { path: '/storage', icon: '💾', label: '存储空间' },
]
</script>
