import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: '/novels' },
  { path: '/novels', name: 'Novels', component: () => import('../views/Novels.vue'), meta: { title: '小说库' } },
  { path: '/novels/:id', name: 'NovelDetail', component: () => import('../views/NovelDetail.vue'), meta: { title: '小说详情' } },
  { path: '/search', name: 'Search', component: () => import('../views/Search.vue'), meta: { title: '语义搜索' } },
  { path: '/settings', name: 'Settings', component: () => import('../views/Settings.vue'), meta: { title: 'API设置' } },
  { path: '/storage', name: 'Storage', component: () => import('../views/Storage.vue'), meta: { title: '存储空间' } },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  document.title = `${to.meta.title || 'Novel Analyzer'} - 小说智能分析`
})

export default router
