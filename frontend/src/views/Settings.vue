<template>
  <div class="p-6 max-w-4xl mx-auto">
    <h2 class="text-2xl font-bold mb-6">⚙️ API 设置</h2>
    <p class="text-sm text-slate-500 mb-6">配置LLM模型API，支持OpenAI兼容接口（DeepSeek、Qwen、GPT、本地LM Studio等）</p>

    <!-- 当前激活 -->
    <div v-if="activeProvider" class="bg-indigo-500/10 border border-indigo-500/30 rounded-lg p-4 mb-6">
      <p class="text-sm text-indigo-400 font-semibold">🟢 当前使用</p>
      <p class="text-lg mt-1">{{ activeProvider.name }} <span class="text-sm text-slate-500">({{ activeProvider.model_name }})</span></p>
    </div>
    <div v-else class="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-4 mb-6">
      <p class="text-yellow-400">⚠️ 尚未配置API，请添加至少一个</p>
    </div>

    <!-- API列表 -->
    <div class="space-y-3 mb-6">
      <div
        v-for="p in providers"
        :key="p.id"
        class="bg-[#1e293b] rounded-lg border border-[#475569] p-4 flex items-center justify-between"
        :class="p.is_active ? 'border-indigo-500/50' : ''"
      >
        <div>
          <p class="font-semibold">
            {{ p.name }}
            <el-tag v-if="p.is_active" type="success" size="small" class="ml-2">使用中</el-tag>
          </p>
          <p class="text-sm text-slate-500 mt-1">{{ p.model_name }} · {{ p.base_url }}</p>
          <p class="text-xs text-slate-600 mt-1">Key: {{ p.api_key }}</p>
        </div>
        <div class="flex gap-2">
          <el-button v-if="!p.is_active" size="small" type="primary" @click="doActivate(p.id)">激活</el-button>
          <el-button size="small" @click="editProvider(p)">编辑</el-button>
          <el-button size="small" type="danger" plain @click="doDelete(p.id)">删除</el-button>
        </div>
      </div>
    </div>

    <!-- 添加按钮 -->
    <el-button type="primary" @click="showAdd = true">➕ 添加API</el-button>

    <!-- 添加/编辑对话框 -->
    <el-dialog v-model="showAdd" :title="editingId ? '编辑API' : '添加API'" width="560px" :close-on-click-modal="false">
      <el-form :model="form" label-width="100px" label-position="top">
        <el-form-item label="模型别称（自定义名字）" required>
          <el-input v-model="form.name" placeholder="如：DeepSeek、本地Qwen、GPT-4o" />
        </el-form-item>
        <el-form-item label="模型名字" required>
          <el-input v-model="form.model_name" placeholder="如：deepseek-chat、qwen-plus、gpt-4o" />
        </el-form-item>
        <el-form-item label="接入地址" required>
          <el-input v-model="form.base_url" placeholder="如：https://api.deepseek.com/v1" />
        </el-form-item>
        <el-form-item label="API Key" required>
          <el-input v-model="form.api_key" placeholder="sk-..." show-password />
        </el-form-item>
        <el-form-item label="系统提示词">
          <el-input v-model="form.system_prompt" type="textarea" :rows="3" placeholder="自定义系统级提示词（可选）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAdd = false; editingId = null">取消</el-button>
        <el-button type="info" :loading="testing" @click="doTest">测试连接</el-button>
        <el-button type="primary" :loading="saving" @click="doSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getProviders, createProvider, updateProvider, deleteProvider, activateProvider, testProvider } from '../api'

const providers = ref([])
const showAdd = ref(false)
const editingId = ref(null)
const saving = ref(false)
const testing = ref(false)

const form = ref({
  name: '',
  model_name: '',
  base_url: '',
  api_key: '',
  system_prompt: '',
})

const activeProvider = computed(() => providers.value.find(p => p.is_active))

const editProvider = (p) => {
  editingId.value = p.id
  form.value = { name: p.name, model_name: p.model_name, base_url: p.base_url, api_key: '', system_prompt: p.system_prompt || '' }
  showAdd.value = true
}

const doSave = async () => {
  if (!form.value.name || !form.value.model_name || !form.value.base_url) {
    ElMessage.warning('请填写必填项')
    return
  }
  // 清理输入中的前后空白
  const cleanForm = {
    ...form.value,
    name: form.value.name.trim(),
    model_name: form.value.model_name.trim(),
    base_url: form.value.base_url.trim(),
    api_key: form.value.api_key ? form.value.api_key.trim() : '',
    system_prompt: form.value.system_prompt ? form.value.system_prompt.trim() : '',
  }
  saving.value = true
  try {
    if (editingId.value) {
      const updateData = { ...cleanForm }
      if (!updateData.api_key) delete updateData.api_key
      await updateProvider(editingId.value, updateData)
      ElMessage.success('已更新')
    } else {
      if (!form.value.api_key) {
        ElMessage.warning('新增API需要填写Key')
        saving.value = false
        return
      }
      await createProvider(form.value)
      ElMessage.success('已添加')
    }
    showAdd.value = false
    editingId.value = null
    form.value = { name: '', model_name: '', base_url: '', api_key: '', system_prompt: '' }
    loadProviders()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

const doTest = async () => {
  if (!form.value.api_key || !form.value.base_url || !form.value.model_name) {
    ElMessage.warning('请先填写完整信息')
    return
  }
  testing.value = true
  try {
    const cleanForm = {
      ...form.value,
      name: form.value.name.trim(),
      model_name: form.value.model_name.trim(),
      base_url: form.value.base_url.trim(),
      api_key: form.value.api_key ? form.value.api_key.trim() : '',
    }
    const { data } = await testProvider(cleanForm)
    if (data.success) {
      ElMessage.success(`连接成功！模型回复: ${data.response}`)
    } else {
      ElMessage.error(`连接失败: ${data.error}`)
    }
  } catch (e) {
    ElMessage.error('测试失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    testing.value = false
  }
}

const doActivate = async (id) => {
  try {
    await activateProvider(id)
    ElMessage.success('已激活')
    loadProviders()
  } catch {
    ElMessage.error('激活失败')
  }
}

const doDelete = async (id) => {
  try {
    await ElMessageBox.confirm('确认删除此API配置？', '警告', { type: 'warning' })
    await deleteProvider(id)
    ElMessage.success('已删除')
    loadProviders()
  } catch {}
}

const loadProviders = async () => {
  try {
    const { data } = await getProviders()
    providers.value = data
  } catch {}
}

onMounted(loadProviders)
</script>
